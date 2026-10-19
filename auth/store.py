"""
store.py
========
Usuarios y sesiones, persistentes. El `user_id` que esto genera es
EXACTAMENTE el mismo tipo de valor que ya esperan credentials_vault,
agent_runtime y todo lo demás — no hace falta tocar ningún otro
paquete, auth solo produce el user_id de forma verificada en vez de
confiar en que alguien lo mande a mano.
"""

from __future__ import annotations
import sqlite3
import secrets
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS failed_logins (
    email TEXT NOT NULL,
    attempted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_failed_logins_email ON failed_logins(email);
"""


def _hash_token(token: str) -> str:
    """Se guarda el hash del token de sesión, no el token: si se filtra el
    archivo .db, los tokens de sesiones activas no se pueden reutilizar.
    SHA-256 sin sal alcanza porque el token ya es aleatorio de 256 bits
    (no es una contraseña humana que se pueda adivinar por diccionario)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class EmailAlreadyExistsError(RuntimeError):
    pass


class UserNotFoundError(RuntimeError):
    pass


@dataclass
class UserRecord:
    user_id: str
    email: str
    password_hash: str
    created_at: datetime


class AuthStore:
    def __init__(self, db_path: str = "auth.db"):
        # check_same_thread=False: mismo motivo que en credentials_vault/registry/positions
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    def create_user(self, email: str, password_hash: str) -> str:
        email = email.strip().lower()
        existing = self._conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            raise EmailAlreadyExistsError(email)
        user_id = f"user_{secrets.token_hex(8)}"
        self._conn.execute(
            "INSERT INTO users (user_id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email, password_hash, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        return user_id

    def get_user_by_email(self, email: str) -> UserRecord:
        row = self._conn.execute(
            "SELECT user_id, email, password_hash, created_at FROM users WHERE email=?",
            (email.strip().lower(),),
        ).fetchone()
        if row is None:
            raise UserNotFoundError(email)
        return UserRecord(user_id=row[0], email=row[1], password_hash=row[2],
                           created_at=datetime.fromisoformat(row[3]))

    def get_user_by_id(self, user_id: str) -> UserRecord:
        row = self._conn.execute(
            "SELECT user_id, email, password_hash, created_at FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise UserNotFoundError(user_id)
        return UserRecord(user_id=row[0], email=row[1], password_hash=row[2],
                           created_at=datetime.fromisoformat(row[3]))

    # ------------------------------------------------------------------
    def create_session(self, user_id: str, ttl_hours: float = 24 * 14) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        self._conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (_hash_token(token), user_id, now.isoformat(), (now + timedelta(hours=ttl_hours)).isoformat()),
        )
        self._conn.commit()
        return token

    def get_session_user_id(self, token: str) -> str | None:
        row = self._conn.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token_hash=?", (_hash_token(token),)
        ).fetchone()
        if row is None:
            return None
        user_id, expires_at = row
        if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
            return None  # vencida — no se borra acá, delete_expired_sessions() se encarga aparte
        return user_id

    def delete_session(self, token: str) -> None:
        self._conn.execute("DELETE FROM sessions WHERE token_hash=?", (_hash_token(token),))
        self._conn.commit()

    def delete_expired_sessions(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        self._conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # Intentos fallidos de login — se llevan POR STRING DE EMAIL, exista o
    # no la cuenta, a propósito: si solo se contaran para cuentas reales,
    # la respuesta "bloqueado" delataría cuáles existen.
    # ------------------------------------------------------------------
    def record_failed_login(self, email: str, when: datetime | None = None) -> None:
        when = when or datetime.now(timezone.utc)
        self._conn.execute("INSERT INTO failed_logins (email, attempted_at) VALUES (?, ?)",
                            (email.strip().lower(), when.isoformat()))
        # poda barata: un atacante probando emails al azar no debe poder
        # inflar esta tabla para siempre
        prune_before = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        self._conn.execute("DELETE FROM failed_logins WHERE attempted_at < ?", (prune_before,))
        self._conn.commit()

    def count_recent_failed_logins(self, email: str, window_minutes: float) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        rows = self._conn.execute("SELECT attempted_at FROM failed_logins WHERE email=?",
                                   (email.strip().lower(),)).fetchall()
        return sum(1 for (ts,) in rows if datetime.fromisoformat(ts) >= cutoff)

    def clear_failed_logins(self, email: str) -> None:
        self._conn.execute("DELETE FROM failed_logins WHERE email=?", (email.strip().lower(),))
        self._conn.commit()

    def close(self):
        self._conn.close()

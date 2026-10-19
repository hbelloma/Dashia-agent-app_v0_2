"""
registry.py
============
Antes de esto no había ningún lugar donde "vivieran" los agentes entre
una corrida y la siguiente — `run_agent_tick_for_user()` sabe correr UN
agente si le das todos sus datos, pero no hay de dónde sacar "cuáles
son todos los agentes activos ahora mismo, de todos los usuarios". Esto
es ese registro — mismo patrón liviano (SQLite) que credentials_vault y
positions.
"""

from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    equity_usd REAL NOT NULL,
    interval_minutes INTEGER NOT NULL DEFAULT 60,
    active INTEGER NOT NULL DEFAULT 1,
    last_run_at TEXT,
    created_at TEXT NOT NULL
);
"""


@dataclass
class AgentConfig:
    agent_id: str
    user_id: str
    name: str
    source: str
    symbol: str
    exchange: str
    equity_usd: float
    interval_minutes: int
    active: bool
    last_run_at: datetime | None
    created_at: datetime


class AgentNotFoundError(RuntimeError):
    pass


class AgentRegistry:
    def __init__(self, db_path: str = "agents.db"):
        # check_same_thread=False: ver la misma nota en credentials_vault/store.py
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def register_agent(self, agent_id: str, user_id: str, name: str, source: str,
                        symbol: str, exchange: str, equity_usd: float,
                        interval_minutes: int = 60, active: bool = True) -> None:
        self._conn.execute(
            """INSERT INTO agents (agent_id, user_id, name, source, symbol, exchange,
                   equity_usd, interval_minutes, active, last_run_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
               ON CONFLICT(agent_id) DO UPDATE SET
                   name=excluded.name, source=excluded.source, symbol=excluded.symbol,
                   exchange=excluded.exchange, equity_usd=excluded.equity_usd,
                   interval_minutes=excluded.interval_minutes, active=excluded.active""",
            (agent_id, user_id, name, source, symbol, exchange, equity_usd,
             interval_minutes, int(active), datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def set_active(self, agent_id: str, active: bool) -> None:
        self._conn.execute("UPDATE agents SET active=? WHERE agent_id=?", (int(active), agent_id))
        self._conn.commit()

    def mark_run(self, agent_id: str, when: datetime) -> None:
        self._conn.execute("UPDATE agents SET last_run_at=? WHERE agent_id=?",
                            (when.isoformat(), agent_id))
        self._conn.commit()

    def get_agent(self, agent_id: str) -> AgentConfig:
        row = self._conn.execute(
            """SELECT agent_id, user_id, name, source, symbol, exchange, equity_usd,
                      interval_minutes, active, last_run_at, created_at
               FROM agents WHERE agent_id=?""", (agent_id,)
        ).fetchone()
        if row is None:
            raise AgentNotFoundError(agent_id)
        return self._row_to_config(row)

    def list_active_agents(self) -> list[AgentConfig]:
        rows = self._conn.execute(
            """SELECT agent_id, user_id, name, source, symbol, exchange, equity_usd,
                      interval_minutes, active, last_run_at, created_at
               FROM agents WHERE active=1"""
        ).fetchall()
        return [self._row_to_config(r) for r in rows]

    def list_agents_for_user(self, user_id: str) -> list[AgentConfig]:
        rows = self._conn.execute(
            """SELECT agent_id, user_id, name, source, symbol, exchange, equity_usd,
                      interval_minutes, active, last_run_at, created_at
               FROM agents WHERE user_id=?""", (user_id,)
        ).fetchall()
        return [self._row_to_config(r) for r in rows]

    def delete_agent(self, agent_id: str) -> None:
        self._conn.execute("DELETE FROM agents WHERE agent_id=?", (agent_id,))
        self._conn.commit()

    def _row_to_config(self, row) -> AgentConfig:
        (agent_id, user_id, name, source, symbol, exchange, equity_usd,
         interval_minutes, active, last_run_at, created_at) = row
        return AgentConfig(
            agent_id=agent_id, user_id=user_id, name=name, source=source, symbol=symbol,
            exchange=exchange, equity_usd=equity_usd, interval_minutes=interval_minutes,
            active=bool(active),
            last_run_at=datetime.fromisoformat(last_run_at) if last_run_at else None,
            created_at=datetime.fromisoformat(created_at),
        )

    def close(self):
        self._conn.close()

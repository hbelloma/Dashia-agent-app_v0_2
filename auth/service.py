"""
service.py
==========
La API que usaría un endpoint real del backend (/signup, /login,
/logout, y el middleware que verifica cada request). El user_id que
devuelve sign_up()/log_in() es el mismo que ya espera
credentials_vault, agent_runtime, etc. — nada de eso cambia.

Dos defensas que NO estaban en la primera versión y se agregaron al
verificar con una medición real (ver auth/README.md):

  1. Igualar el tiempo de respuesta: antes, un email inexistente
     respondía en ~0 ms y uno existente con contraseña mala en ~126 ms
     (el costo de scrypt) — suficiente para enumerar qué cuentas existen
     cronometrando el login, aunque el mensaje de error fuera idéntico.
  2. Bloqueo temporal tras varios intentos fallidos: el costo de scrypt
     encarece cada intento, pero no frena a un atacante paciente.
"""

from __future__ import annotations
import logging

from .store import AuthStore, EmailAlreadyExistsError, UserNotFoundError
from .passwords import hash_password, verify_password, WeakPasswordError

log = logging.getLogger("auth.service")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 15


class InvalidCredentialsError(RuntimeError):
    """Mensaje deliberadamente genérico — no revela si falló el email o la
    contraseña, para no ayudar a alguien a enumerar qué emails existen."""


class AccountLockedError(InvalidCredentialsError):
    """Demasiados intentos fallidos recientes para ese email. Subclase de
    InvalidCredentialsError: quien ya atrapaba a la padre sigue funcionando,
    y quien quiera mostrar un mensaje específico puede atrapar esta primero."""


class AuthService:
    def __init__(self, store: AuthStore, max_failed_attempts: int = MAX_FAILED_ATTEMPTS,
                 lockout_window_minutes: float = LOCKOUT_WINDOW_MINUTES):
        self.store = store
        self.max_failed_attempts = max_failed_attempts
        self.lockout_window_minutes = lockout_window_minutes
        # Hash falso, calculado una sola vez al iniciar, para que un login con
        # email inexistente haga el mismo trabajo (un scrypt) que uno con
        # email existente y contraseña mala.
        self._dummy_hash = hash_password("relleno-para-igualar-tiempos-1")

    def sign_up(self, email: str, password: str) -> tuple[str, str]:
        """Devuelve (user_id, session_token) — registra Y deja logueado de una.

        Límite conocido: registrarse con un email ya usado lanza
        EmailAlreadyExistsError, o sea que este endpoint SÍ revela si un email
        tiene cuenta. Es el compromiso habitual; cerrarlo del todo requiere un
        flujo de verificación por email, que no existe todavía (ver README)."""
        password_hash = hash_password(password)  # lanza WeakPasswordError si es muy corta
        user_id = self.store.create_user(email, password_hash)
        token = self.store.create_session(user_id)
        log.info("Usuario nuevo registrado: %s", user_id)
        return user_id, token

    def log_in(self, email: str, password: str) -> tuple[str, str]:
        if self.store.count_recent_failed_logins(email, self.lockout_window_minutes) >= self.max_failed_attempts:
            # Cuenta existente o no, la respuesta es la misma: los intentos se
            # cuentan por string de email, así este mensaje no delata nada.
            raise AccountLockedError("Demasiados intentos fallidos. Intentá de nuevo en unos minutos.")

        try:
            user = self.store.get_user_by_email(email)
            stored_hash = user.password_hash
        except UserNotFoundError:
            user = None
            stored_hash = self._dummy_hash

        password_ok = verify_password(password, stored_hash)  # siempre se calcula, exista o no

        if user is None or not password_ok:
            self.store.record_failed_login(email)
            raise InvalidCredentialsError("Email o contraseña incorrectos")

        self.store.clear_failed_logins(email)
        token = self.store.create_session(user.user_id)
        return user.user_id, token

    def verify_session(self, token: str) -> str:
        """Devuelve el user_id si la sesión es válida, o lanza — esto es
        lo que protegería cada endpoint real que necesite saber quién llama."""
        user_id = self.store.get_session_user_id(token)
        if user_id is None:
            raise InvalidCredentialsError("Sesión inválida o vencida")
        return user_id

    def log_out(self, token: str) -> None:
        self.store.delete_session(token)

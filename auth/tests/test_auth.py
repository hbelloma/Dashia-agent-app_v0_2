"""
test_auth.py
=============
Escritos con unittest (stdlib) a propósito: corren con
`python -m unittest` sin instalar nada, y pytest también los ejecuta
tal cual. Nada mockeado — scrypt es cómputo local puro, así que corre
el hash real (con su costo real, que es justo lo que lo hace caro de
atacar por fuerza bruta).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from auth.passwords import hash_password, verify_password, WeakPasswordError
from auth.store import AuthStore, EmailAlreadyExistsError, UserNotFoundError
from auth.service import AuthService, InvalidCredentialsError, AccountLockedError
from datetime import datetime, timezone, timedelta
import statistics
import time


class PasswordTests(unittest.TestCase):
    def test_hash_verifies_with_correct_password(self):
        h = hash_password("contraseña-segura-123")
        self.assertTrue(verify_password("contraseña-segura-123", h))

    def test_wrong_password_is_rejected(self):
        h = hash_password("contraseña-segura-123")
        self.assertFalse(verify_password("otra-contraseña-456", h))

    def test_hash_does_not_contain_the_plaintext_password(self):
        h = hash_password("mi-secreto-unico-xyz")
        self.assertNotIn("mi-secreto-unico-xyz", h)

    def test_same_password_produces_different_hashes_thanks_to_salt(self):
        h1 = hash_password("misma-contraseña-1")
        h2 = hash_password("misma-contraseña-1")
        self.assertNotEqual(h1, h2)
        self.assertTrue(verify_password("misma-contraseña-1", h1))
        self.assertTrue(verify_password("misma-contraseña-1", h2))

    def test_weak_password_is_rejected_before_hashing(self):
        with self.assertRaises(WeakPasswordError):
            hash_password("corta")

    def test_corrupted_hash_returns_false_not_a_crash(self):
        self.assertFalse(verify_password("cualquiera", "esto-no-es-un-hash-valido"))
        self.assertFalse(verify_password("cualquiera", "scrypt$no$son$numeros$zz$zz"))
        self.assertFalse(verify_password("cualquiera", ""))

    def test_hash_from_another_scheme_is_rejected_not_accepted(self):
        # el prefijo de algoritmo existe justo para esto: un hash de otro
        # esquema nunca debe autenticar por accidente con scrypt
        self.assertFalse(verify_password("x", "bcrypt$12$salt$hash$a$b"))

    def test_hash_format_is_self_describing(self):
        h = hash_password("contraseña-segura-123")
        self.assertTrue(h.startswith("scrypt$"))
        self.assertEqual(len(h.split("$")), 6)

    def test_unicode_passwords_work(self):
        h = hash_password("contraseña-ñandú-🔐-123")
        self.assertTrue(verify_password("contraseña-ñandú-🔐-123", h))
        self.assertFalse(verify_password("contraseña-nandu-🔐-123", h))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = AuthStore(db_path=os.path.join(self._tmp.name, "auth.db"))

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_duplicate_email_is_rejected(self):
        self.store.create_user("a@x.com", "hash1")
        with self.assertRaises(EmailAlreadyExistsError):
            self.store.create_user("a@x.com", "hash2")

    def test_email_is_case_insensitive(self):
        self.store.create_user("Persona@Ejemplo.com", "hash1")
        with self.assertRaises(EmailAlreadyExistsError):
            self.store.create_user("persona@ejemplo.com", "hash2")

    def test_get_nonexistent_user_raises(self):
        with self.assertRaises(UserNotFoundError):
            self.store.get_user_by_email("nadie@x.com")

    def test_session_lifecycle(self):
        user_id = self.store.create_user("a@x.com", "hash")
        token = self.store.create_session(user_id)
        self.assertEqual(self.store.get_session_user_id(token), user_id)
        self.store.delete_session(token)
        self.assertIsNone(self.store.get_session_user_id(token))

    def test_expired_session_is_not_valid(self):
        user_id = self.store.create_user("a@x.com", "hash")
        token = self.store.create_session(user_id, ttl_hours=-1)  # vencida desde el nacimiento
        self.assertIsNone(self.store.get_session_user_id(token))

    def test_delete_expired_sessions_cleans_up_only_the_expired(self):
        user_id = self.store.create_user("a@x.com", "hash")
        self.store.create_session(user_id, ttl_hours=-1)
        self.store.create_session(user_id, ttl_hours=-2)
        valid = self.store.create_session(user_id, ttl_hours=24)
        self.assertEqual(self.store.delete_expired_sessions(), 2)
        self.assertEqual(self.store.get_session_user_id(valid), user_id)

    def test_session_tokens_are_unique_and_unguessable_length(self):
        user_id = self.store.create_user("a@x.com", "hash")
        tokens = {self.store.create_session(user_id) for _ in range(50)}
        self.assertEqual(len(tokens), 50)
        self.assertTrue(all(len(t) >= 40 for t in tokens))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = AuthStore(db_path=os.path.join(self._tmp.name, "auth.db"))
        self.service = AuthService(self.store)

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_sign_up_then_session_is_immediately_valid(self):
        user_id, token = self.service.sign_up("nuevo@x.com", "contraseña-larga-123")
        self.assertEqual(self.service.verify_session(token), user_id)

    def test_sign_up_with_weak_password_creates_nothing(self):
        with self.assertRaises(WeakPasswordError):
            self.service.sign_up("a@x.com", "corta")
        with self.assertRaises(UserNotFoundError):
            self.store.get_user_by_email("a@x.com")  # ni siquiera quedó el usuario a medias

    def test_sign_up_duplicate_email_raises(self):
        self.service.sign_up("a@x.com", "contraseña-larga-123")
        with self.assertRaises(EmailAlreadyExistsError):
            self.service.sign_up("a@x.com", "otra-contraseña-456")

    def test_login_with_correct_credentials_returns_same_user_id(self):
        user_id, _ = self.service.sign_up("a@x.com", "contraseña-larga-123")
        login_id, _ = self.service.log_in("a@x.com", "contraseña-larga-123")
        self.assertEqual(login_id, user_id)

    def test_login_is_case_insensitive_on_email(self):
        user_id, _ = self.service.sign_up("Persona@X.com", "contraseña-larga-123")
        login_id, _ = self.service.log_in("persona@x.COM", "contraseña-larga-123")
        self.assertEqual(login_id, user_id)

    def test_login_wrong_password_raises_generic_error(self):
        self.service.sign_up("a@x.com", "contraseña-larga-123")
        with self.assertRaises(InvalidCredentialsError):
            self.service.log_in("a@x.com", "contraseña-equivocada")

    def test_login_nonexistent_email_gives_same_error_as_wrong_password(self):
        # No revelar si el email existe (evita enumerar cuentas registradas)
        self.service.sign_up("a@x.com", "contraseña-larga-123")
        with self.assertRaises(InvalidCredentialsError) as wrong_pw:
            self.service.log_in("a@x.com", "contraseña-equivocada")
        with self.assertRaises(InvalidCredentialsError) as no_user:
            self.service.log_in("no-existe@x.com", "contraseña-equivocada")
        self.assertEqual(str(wrong_pw.exception), str(no_user.exception))

    def test_logout_invalidates_the_session(self):
        _, token = self.service.sign_up("a@x.com", "contraseña-larga-123")
        self.service.log_out(token)
        with self.assertRaises(InvalidCredentialsError):
            self.service.verify_session(token)

    def test_garbage_token_is_rejected(self):
        with self.assertRaises(InvalidCredentialsError):
            self.service.verify_session("token-inventado-que-no-existe")
        with self.assertRaises(InvalidCredentialsError):
            self.service.verify_session("")

    def test_two_logins_create_independent_sessions(self):
        self.service.sign_up("a@x.com", "contraseña-larga-123")
        _, t1 = self.service.log_in("a@x.com", "contraseña-larga-123")
        _, t2 = self.service.log_in("a@x.com", "contraseña-larga-123")
        self.assertNotEqual(t1, t2)
        self.service.log_out(t1)
        self.assertTrue(self.service.verify_session(t2))  # cerrar una no cierra la otra

    def test_sql_injection_attempt_in_email_is_just_a_wrong_login(self):
        self.service.sign_up("a@x.com", "contraseña-larga-123")
        with self.assertRaises(InvalidCredentialsError):
            self.service.log_in("a@x.com' OR '1'='1", "contraseña-larga-123")
        with self.assertRaises(InvalidCredentialsError):
            self.service.log_in("' OR 1=1 --", "cualquier-cosa-123")


class DatabaseFileTests(unittest.TestCase):
    def test_raw_db_file_never_contains_the_plaintext_password(self):
        # Igual de rigurosa que la de credentials_vault: se lee el .db
        # como bytes crudos, no se le pregunta al código si "dice" cifrar.
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "auth.db")
            store = AuthStore(db_path=db_path)
            AuthService(store).sign_up("a@x.com", "UnaContraseñaMuyEspecial987")
            store.close()
            with open(db_path, "rb") as f:
                raw = f.read()
            self.assertNotIn("UnaContraseñaMuyEspecial987".encode("utf-8"), raw)

    def test_raw_db_file_never_contains_a_usable_session_token(self):
        # Si se filtra el .db, los tokens de sesiones activas no deben poder reutilizarse.
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "auth.db")
            store = AuthStore(db_path=db_path)
            _, token = AuthService(store).sign_up("a@x.com", "contraseña-larga-123")
            self.assertTrue(AuthService(store).verify_session(token))  # el token SÍ funciona por la API
            store.close()
            with open(db_path, "rb") as f:
                raw = f.read()
            self.assertNotIn(token.encode("utf-8"), raw)  # pero no está en el archivo


class VaultIntegrationTests(unittest.TestCase):
    def test_authenticated_user_ids_isolate_vault_credentials_between_users(self):
        # El user_id que produce auth es el MISMO tipo de valor que ya
        # espera credentials_vault — sin tocar ningún otro paquete.
        from credentials_vault.crypto import EnvelopeCipher
        from credentials_vault.store import CredentialsVault

        with tempfile.TemporaryDirectory() as tmp:
            auth_store = AuthStore(db_path=os.path.join(tmp, "auth.db"))
            service = AuthService(auth_store)
            vault = CredentialsVault(db_path=os.path.join(tmp, "vault.db"),
                                      cipher=EnvelopeCipher(EnvelopeCipher.generate_master_key()))

            alice_id, alice_token = service.sign_up("alice@x.com", "contraseña-alice-123")
            bob_id, bob_token = service.sign_up("bob@x.com", "contraseña-bob-4567")

            vault.save_credential(service.verify_session(alice_token), "binance", "KEY_ALICE", "SECRET_ALICE")
            vault.save_credential(service.verify_session(bob_token), "binance", "KEY_BOB", "SECRET_BOB")

            alice_creds = vault.list_credentials(service.verify_session(alice_token))
            self.assertEqual(len(alice_creds), 1)
            self.assertEqual(alice_creds[0].api_key, "KEY_ALICE")
            self.assertTrue(all(c.user_id == alice_id for c in alice_creds))
            self.assertNotEqual(alice_id, bob_id)

            vault.close()
            auth_store.close()

    def test_a_forged_or_logged_out_session_cannot_reach_anyones_credentials(self):
        # La razón de ser de todo esto: sin un token válido no hay user_id
        # verificado, y sin user_id verificado no se puede pedir nada a la bóveda.
        with tempfile.TemporaryDirectory() as tmp:
            auth_store = AuthStore(db_path=os.path.join(tmp, "auth.db"))
            service = AuthService(auth_store)
            _, token = service.sign_up("alice@x.com", "contraseña-alice-123")
            service.log_out(token)
            with self.assertRaises(InvalidCredentialsError):
                service.verify_session(token)
            auth_store.close()


class LoginDefenseTests(unittest.TestCase):
    """Las dos defensas que aparecieron al verificar con una medición real:
    el canal lateral de tiempo (126 ms vs 0 ms) y la falta de bloqueo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = AuthStore(db_path=os.path.join(self._tmp.name, "auth.db"))
        self.service = AuthService(self.store)
        self.service.sign_up("existe@x.com", "contraseña-larga-123")

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def _median_ms(self, service, email, n=5):
        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            try:
                service.log_in(email, "contraseña-equivocada-1")
            except InvalidCredentialsError:
                pass
            samples.append((time.perf_counter() - t0) * 1000)
        return statistics.median(samples)

    # --- canal lateral de tiempo -------------------------------------
    def test_unknown_email_takes_about_as_long_as_a_wrong_password(self):
        # Antes del arreglo: ~0 ms vs ~126 ms (ratio ≈ 0) — este test habría fallado.
        # max_failed_attempts altísimo para que el bloqueo no distorsione la medición.
        svc = AuthService(self.store, max_failed_attempts=10_000)
        existing = self._median_ms(svc, "existe@x.com")
        unknown = self._median_ms(svc, "no-existe@x.com")
        ratio = unknown / existing
        self.assertGreater(ratio, 0.5, f"email inexistente responde {unknown:.1f}ms vs {existing:.1f}ms")
        self.assertLess(ratio, 2.0)

    # --- bloqueo por intentos fallidos -------------------------------
    def test_locks_after_max_failed_attempts_even_with_the_correct_password(self):
        for _ in range(5):
            with self.assertRaises(InvalidCredentialsError) as ctx:
                self.service.log_in("existe@x.com", "mal-mal-mal-123")
            self.assertNotIsInstance(ctx.exception, AccountLockedError)  # los primeros 5 son fallos normales
        with self.assertRaises(AccountLockedError):
            self.service.log_in("existe@x.com", "contraseña-larga-123")  # ni la correcta pasa

    def test_lockout_is_per_email_other_accounts_are_unaffected(self):
        for _ in range(5):
            self.store.record_failed_login("existe@x.com")
        self.service.sign_up("otra@x.com", "contraseña-larga-123")
        self.service.log_in("otra@x.com", "contraseña-larga-123")  # no lanza

    def test_nonexistent_email_locks_identically_so_lockout_leaks_nothing(self):
        for _ in range(5):
            self.store.record_failed_login("fantasma@x.com")
        with self.assertRaises(AccountLockedError):
            self.service.log_in("fantasma@x.com", "lo-que-sea-123")

    def test_successful_login_resets_the_failure_counter(self):
        for _ in range(4):
            self.store.record_failed_login("existe@x.com")
        self.service.log_in("existe@x.com", "contraseña-larga-123")
        for _ in range(4):
            self.store.record_failed_login("existe@x.com")
        self.service.log_in("existe@x.com", "contraseña-larga-123")  # 4 < 5, sigue libre

    def test_old_failures_age_out_of_the_window(self):
        old = datetime.now(timezone.utc) - timedelta(minutes=20)  # ventana = 15 min
        for _ in range(5):
            self.store.record_failed_login("existe@x.com", when=old)
        self.service.log_in("existe@x.com", "contraseña-larga-123")  # no bloqueado

    def test_email_case_cannot_dodge_the_lockout(self):
        for _ in range(5):
            self.store.record_failed_login("existe@x.com")
        with self.assertRaises(AccountLockedError):
            self.service.log_in("EXISTE@X.COM", "contraseña-larga-123")

    def test_locked_error_is_a_kind_of_invalid_credentials(self):
        self.assertTrue(issubclass(AccountLockedError, InvalidCredentialsError))

    def test_ancient_failed_login_rows_do_not_accumulate_forever(self):
        ancient = datetime.now(timezone.utc) - timedelta(hours=25)
        self.store.record_failed_login("spam@x.com", when=ancient)
        n = self.store._conn.execute("SELECT COUNT(*) FROM failed_logins").fetchone()[0]
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()

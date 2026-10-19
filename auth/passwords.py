"""
passwords.py
============
scrypt de la librería estándar de Python (hashlib.scrypt) — un KDF
"memory-hard": cada intento de adivinar una contraseña obliga a usar
bastante memoria, lo que encarece los ataques masivos con GPU/ASIC
(a diferencia de PBKDF2, que solo es lento en CPU).

Nota honesta sobre la decisión: el plan original era bcrypt. El
entorno donde se construyó esto perdió la red y sus paquetes
instalados, y bcrypt no venía con Python. scrypt sí — es una
alternativa técnicamente sólida (no un parche), y además es una
dependencia menos. Si se prefiere bcrypt o argon2id en producción, el
cambio vive solo en este archivo: el hash guardado lleva un prefijo de
algoritmo ("scrypt$...") justamente para poder agregar otro esquema
sin invalidar las cuentas ya creadas.

Formato del hash guardado:
    scrypt$<n>$<r>$<p>$<salt_hex>$<hash_hex>
"""

from __future__ import annotations
import hashlib
import hmac
import secrets


class WeakPasswordError(ValueError):
    pass


MIN_LENGTH = 8

# Parámetros de costo. n=2**15 usa ~32MB por hash y tarda ~100ms en un
# servidor normal — el equilibrio habitual entre "molesto para un
# atacante" y "invisible para un usuario que inicia sesión".
SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
DKLEN = 32
# scrypt necesita ~128*n*r bytes; el límite por defecto de OpenSSL es 32MB
# y justo rozaría con n=2**15, r=8 (=32MB), así que se sube explícito.
MAXMEM = 128 * SCRYPT_N * SCRYPT_R * 2


def validate_password_strength(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise WeakPasswordError(f"La contraseña debe tener al menos {MIN_LENGTH} caracteres")


def hash_password(password: str) -> str:
    validate_password_strength(password)
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
                         p=SCRYPT_P, dklen=DKLEN, maxmem=MAXMEM)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Nunca lanza por un hash corrupto o de otro formato — devuelve False.
    La comparación es de tiempo constante (hmac.compare_digest) para no
    filtrar, por diferencias de milisegundos, cuántos bytes coincidían."""
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
                                    dklen=len(expected), maxmem=128 * n * r * 2)
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError, OverflowError):
        return False

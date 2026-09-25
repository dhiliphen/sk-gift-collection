"""
Password hashing — stdlib only (no new dependency, keeps the PyInstaller
build simple). Replaces the previous unsalted single SHA-256 hash with
salted PBKDF2-HMAC-SHA256, a per-user random salt, and a modern iteration
count.
"""
import hashlib
import hmac
import os

_ITERATIONS = 260_000
_ALGORITHM = "sha256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac(_ALGORITHM, password.encode(), salt, _ITERATIONS)
    return f"{salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, hash_hex = stored_hash.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    derived = hashlib.pbkdf2_hmac(_ALGORITHM, password.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(derived, expected)

"""Tests for app/security.py — password hashing (stdlib PBKDF2-HMAC)."""
from app.security import hash_password, verify_password


def test_hash_password_produces_salt_and_hash():
    hashed = hash_password("correcthorsebatterystaple")
    assert "$" in hashed
    salt_hex, hash_hex = hashed.split("$")
    assert len(salt_hex) == 32  # 16 bytes hex-encoded
    assert len(hash_hex) == 64  # sha256 digest hex-encoded


def test_verify_password_correct():
    hashed = hash_password("mypassword123")
    assert verify_password("mypassword123", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("mypassword123")
    assert verify_password("wrongpassword", hashed) is False


def test_two_hashes_of_same_password_differ():
    """Different random salts must produce different stored hashes."""
    h1 = hash_password("samepassword")
    h2 = hash_password("samepassword")
    assert h1 != h2
    assert verify_password("samepassword", h1)
    assert verify_password("samepassword", h2)


def test_verify_password_rejects_malformed_hash():
    assert verify_password("anything", "not-a-valid-hash") is False
    assert verify_password("anything", "") is False

"""密码哈希：不可逆、加盐、校验。"""
from __future__ import annotations

from app.core.security import hash_password, verify_password


def test_hash_verify_roundtrip():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)


def test_wrong_password_rejected():
    hashed = hash_password("secret123")
    assert not verify_password("secret456", hashed)


def test_salt_makes_hashes_different():
    assert hash_password("secret123") != hash_password("secret123")


def test_invalid_hash_returns_false_not_error():
    assert not verify_password("secret123", "not-a-valid-bcrypt-hash")

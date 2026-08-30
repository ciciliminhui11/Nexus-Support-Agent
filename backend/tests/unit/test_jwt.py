"""JWT：签发 / 过期 / 无效签名。"""
from __future__ import annotations

import datetime

import jwt as pyjwt

from app.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, decode_access_token


def test_create_and_decode():
    token = create_access_token(42, "user", "phone")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "user"
    assert payload["account_type"] == "phone"


def test_invalid_signature_rejected():
    token = create_access_token(42, "user", "phone")
    # 用错误密钥重签
    tampered = pyjwt.encode(
        {"sub": 42, "role": "admin"},
        "wrong-secret-wrong-secret-wrong-secret",
        algorithm=settings.jwt_algorithm,
    )
    try:
        decode_access_token(tampered)
        assert False, "应当抛出 UnauthorizedError"
    except UnauthorizedError:
        pass


def test_expired_token_rejected():
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": 42,
        "role": "user",
        "iat": int((now - datetime.timedelta(hours=25)).timestamp()),
        "exp": int((now - datetime.timedelta(hours=1)).timestamp()),
    }
    token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    try:
        decode_access_token(token)
        assert False, "应当抛出 UnauthorizedError"
    except UnauthorizedError:
        pass

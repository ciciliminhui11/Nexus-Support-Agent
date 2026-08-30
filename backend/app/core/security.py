"""安全核心：密码哈希（bcrypt）与 JWT 签发/校验。

- 密码以不可逆加盐哈希存储（bcrypt），禁止明文落库；
- JWT 无状态令牌，载荷含 sub/role/account_type/iat/exp，不落库；
- 密钥仅存服务端环境变量（`JWT_SECRET`），禁止硬编码。
"""
from __future__ import annotations

import datetime

import bcrypt
import jwt

from app.config import settings
from app.core.exceptions import UnauthorizedError

# bcrypt 输入上限（72 字节）。bcrypt>=5 对超长输入直接抛错，注册时需先校验。
BCRYPT_MAX_BYTES = 72


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, role: str, account_type: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    expire = now + datetime.timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user_id),  # JWT RFC 要求 sub 为字符串，PyJWT>=2.x 强制校验
        "role": role,
        "account_type": account_type,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """验签 + 过期校验；无效/过期统一抛 401。"""
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        raise UnauthorizedError()

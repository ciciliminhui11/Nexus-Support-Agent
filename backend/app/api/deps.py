"""全局鉴权依赖（全站受保护接口统一入口）。

所有受保护路由引用 `get_current_user`；管理员专属接口追加 `require_admin`。
"""
from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError()
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise UnauthorizedError()
    return token


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    """校验 Bearer 令牌有效性与过期，注入当前 User。"""
    token = _extract_token(authorization)
    payload = decode_access_token(token)
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        raise UnauthorizedError()
    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise ForbiddenError()
    return user

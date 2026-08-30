"""角色常量与权限校验依赖。"""
from __future__ import annotations

from app.core.exceptions import ForbiddenError

ROLE_USER = "user"
ROLE_ADMIN = "admin"


def require_role(user_role: str, required: str) -> None:
    if user_role != required:
        raise ForbiddenError()

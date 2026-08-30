"""登录业务：统一失败提示（防枚举）+ 失败防护 + JWT 签发。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.login_guard import login_guard
from app.core.security import create_access_token, verify_password
from app.db.models import User


def login(db: Session, identifier: str, account_type: str, password: str, ip: str) -> dict:
    # 防暴力破解：锁定期内直接拒绝
    login_guard.check(identifier, ip)

    user = db.scalar(
        select(User).where(User.account_identifier == identifier)
    )
    # 统一失败提示，不区分「账号不存在」与「密码错误」，防账号枚举
    if user is None or not verify_password(password, user.password_hash):
        login_guard.record_failure(identifier, ip)
        raise UnauthorizedError(
            code="invalid_credentials", message="手机号/邮箱或密码错误"
        )

    login_guard.record_success(identifier, ip)
    token = create_access_token(user.id, user.role, user.account_type)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_hours * 3600,
        "user": {"user_id": user.id, "role": user.role},
    }

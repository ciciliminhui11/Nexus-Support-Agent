"""注册业务：标识格式校验 + 唯一性 + bcrypt 哈希入库。"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import ConflictError, ValidationError
from app.core.security import BCRYPT_MAX_BYTES, hash_password
from app.db.models import User
from app.services.config_service import get_config_value

EMAIL_RE = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"


def validate_identifier(identifier: str, account_type: str) -> None:
    if account_type == "phone":
        if not re.fullmatch(settings.phone_regex, identifier):
            raise ValidationError(
                code="invalid_identifier", message="手机号或邮箱格式不正确"
            )
    elif account_type == "email":
        if not re.fullmatch(EMAIL_RE, identifier):
            raise ValidationError(
                code="invalid_identifier", message="手机号或邮箱格式不正确"
            )
    else:
        raise ValidationError(
            code="invalid_identifier", message="账号类型仅支持手机号或邮箱"
        )


def validate_password(password: str, min_length: int) -> None:
    if not password.strip():
        raise ValidationError(code="password_too_short", message="密码不能为空或全空白")
    if len(password) < min_length:
        raise ValidationError(
            code="password_too_short", message=f"密码长度不能少于 {min_length} 位"
        )
    # bcrypt 输入上限 72 字节，超出直接拒绝（bcrypt>=5 会抛 ValueError）
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValidationError(
            code="password_too_long", message="密码长度不能超过 72 字节"
        )


def register(db: Session, identifier: str, account_type: str, password: str) -> User:
    validate_identifier(identifier, account_type)
    min_len = int(get_config_value(db, "min_password_length"))
    validate_password(password, min_len)

    existing = db.scalar(
        select(User).where(User.account_identifier == identifier)
    )
    if existing is not None:
        raise ConflictError(code="identifier_taken", message="该手机号/邮箱已被注册")

    user = User(
        account_identifier=identifier,
        account_type=account_type,
        password_hash=hash_password(password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

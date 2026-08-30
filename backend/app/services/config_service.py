"""运行时配置读取。

优先级：`system_config` 表（可热调） > `app/config.py` 的 Settings 默认值。

类型按 Settings 模型字段类型自动转换（int / float / bool / str），
因此 DB 中存字符串即可（init.sql 已预置默认值）。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import SystemConfig


def _coerce(key: str, value: str, default: Any) -> Any:
    # pydantic v2 的字段类型在 model_fields（类属性默认值已被移除），
    # 用 getattr(type(settings), key) 取注解会恒为 None → 所有 DB 覆盖静默失效。
    field = type(settings).model_fields.get(key)
    if field is None:
        return default
    annotation = getattr(field, "annotation", None)
    if annotation is bool:
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if annotation is int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    if annotation is float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    return value


def get_config_value(db: Session, key: str, default: Any = None) -> Any:
    """读取运行时配置：system_config 表优先，未配置回落 Settings 默认值。"""
    if default is None:
        default = getattr(settings, key, None)
    row = db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    ).scalar_one_or_none()
    if row is None:
        return default
    return _coerce(key, row.value, default)


def get_int(db: Session, key: str, default: int = 0) -> int:
    return int(get_config_value(db, key, default))


def get_float(db: Session, key: str, default: float = 0.0) -> float:
    return float(get_config_value(db, key, default))


def get_bool(db: Session, key: str, default: bool = False) -> bool:
    return bool(get_config_value(db, key, default))

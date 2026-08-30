"""每日提问配额查询（003 提供查询展示；001 负责递增计数）。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import UserQuotaDaily
from app.services.config_service import get_config_value


def get_quota(db: Session, user_id: int) -> dict:
    today = date.today()
    row = db.scalar(
        select(UserQuotaDaily).where(
            UserQuotaDaily.user_id == user_id,
            UserQuotaDaily.stat_date == today,
        )
    )
    used = row.count if row is not None else 0
    limit = int(get_config_value(db, "daily_quota_limit", settings.daily_quota_limit))
    return {
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
    }

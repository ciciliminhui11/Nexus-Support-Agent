"""管理员接口：用户额度管理。

提供用户列表（含额度信息）与单用户额度配置。
仅限 admin 角色访问（依赖 require_admin）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.config import settings
from app.db.models import User, UserQuotaDaily
from app.db.session import get_db
from app.services.config_service import get_config_value

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------- Schema ----------

class UserQuotaItem(BaseModel):
    """管理端用户列表项（含额度信息）。"""
    user_id: int
    account_identifier: str
    account_type: str
    role: str
    daily_quota: int | None  # None 表示使用全局默认
    used_today: int
    effective_limit: int  # 实际生效的限额

class UserQuotaListResponse(BaseModel):
    total: int
    items: list[UserQuotaItem]

class SetUserQuotaRequest(BaseModel):
    daily_quota: int | None = Field(default=None, ge=1, le=10000, description="每日提问限额，null 恢复为全局默认")

class SetUserQuotaResponse(BaseModel):
    user_id: int
    daily_quota: int | None
    effective_limit: int

class GlobalQuotaResponse(BaseModel):
    daily_quota_limit: int


# ---------- 端点 ----------

@router.get("/users", response_model=UserQuotaListResponse)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserQuotaListResponse:
    """管理员：获取用户列表及其额度信息。"""
    from datetime import date as _date
    today = _date.today()

    # 全局默认限额
    global_limit = int(get_config_value(db, "daily_quota_limit", settings.daily_quota_limit))

    # 用户总数
    total = db.scalar(select(func.count(User.id))) or 0

    # 分页用户
    offset = (page - 1) * page_size
    users = db.scalars(
        select(User).order_by(User.id).offset(offset).limit(page_size)
    ).all()

    # 批量查当日用量
    user_ids = [u.id for u in users]
    quota_rows = db.execute(
        select(UserQuotaDaily.user_id, UserQuotaDaily.count).where(
            UserQuotaDaily.user_id.in_(user_ids),
            UserQuotaDaily.stat_date == today,
        )
    ).all()
    used_map = dict(quota_rows)

    items = []
    for u in users:
        effective = u.daily_quota if u.daily_quota is not None else global_limit
        items.append(UserQuotaItem(
            user_id=u.id,
            account_identifier=u.account_identifier,
            account_type=u.account_type,
            role=u.role,
            daily_quota=u.daily_quota,
            used_today=used_map.get(u.id, 0),
            effective_limit=effective,
        ))

    return UserQuotaListResponse(total=total, items=items)


@router.put("/users/{user_id}/quota", response_model=SetUserQuotaResponse)
def set_user_quota(
    user_id: int,
    req: SetUserQuotaRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SetUserQuotaResponse:
    """管理员：设置指定用户的每日提问限额。null 恢复为全局默认。"""
    user = db.get(User, user_id)
    if user is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(code="user_not_found", message="用户不存在")

    user.daily_quota = req.daily_quota
    db.commit()
    db.refresh(user)

    global_limit = int(get_config_value(db, "daily_quota_limit", settings.daily_quota_limit))
    effective = user.daily_quota if user.daily_quota is not None else global_limit

    return SetUserQuotaResponse(
        user_id=user.id,
        daily_quota=user.daily_quota,
        effective_limit=effective,
    )


@router.get("/quota/global", response_model=GlobalQuotaResponse)
def get_global_quota(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GlobalQuotaResponse:
    """管理员：获取全局每日提问限额。"""
    limit = int(get_config_value(db, "daily_quota_limit", settings.daily_quota_limit))
    return GlobalQuotaResponse(daily_quota_limit=limit)


@router.put("/quota/global", response_model=GlobalQuotaResponse)
def set_global_quota(
    req: SetUserQuotaRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GlobalQuotaResponse:
    """管理员：设置全局每日提问限额（未自定义额度的用户受此值影响）。"""
    if req.daily_quota is None or req.daily_quota < 1:
        from app.core.exceptions import ValidationError
        raise ValidationError(code="invalid_quota", message="全局限额必须为正整数")

    from app.db.models import SystemConfig
    from sqlalchemy import update as sa_update
    db.execute(
        sa_update(SystemConfig)
        .where(SystemConfig.key == "daily_quota_limit")
        .values(value=str(req.daily_quota))
    )
    db.commit()
    return GlobalQuotaResponse(daily_quota_limit=req.daily_quota)

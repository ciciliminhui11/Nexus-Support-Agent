"""鉴权接口：注册 / 登录 / 当前账号信息与配额。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.services.auth import login as login_service
from app.services.auth import quota as quota_service
from app.services.auth import registration

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    user = registration.register(
        db, req.account_identifier, req.account_type, req.password
    )
    return RegisterResponse(
        user_id=user.id,
        account_identifier=user.account_identifier,
        account_type=user.account_type,
        role=user.role,
        created_at=user.created_at,
    )


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db), request: Request = None) -> dict:
    ip = request.client.host if request is not None and request.client else "unknown"
    return login_service.login(
        db, req.account_identifier, req.account_type, req.password, ip
    )


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    quota = quota_service.get_quota(db, user.id)
    return MeResponse(
        user_id=user.id,
        account_identifier=user.account_identifier,
        account_type=user.account_type,
        role=user.role,
        created_at=user.created_at,
        quota=quota,
    )

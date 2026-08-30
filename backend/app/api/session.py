"""会话接口：创建 / 列表 / 详情。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.models import User
from app.db.session import get_db
from app.schemas.session import (
    MessageItem,
    MessageListResponse,
    SessionDetailResponse,
    SessionItem,
    SessionListResponse,
)
from app.services.config_service import get_config_value
from app.services.session import session_crud
from app.services.session import message_query
from app.config import settings

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("", status_code=201, response_model=SessionItem)
def create_session(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionItem:
    s = session_crud.create_session(db, user.id)
    return SessionItem(session_id=s.id, title=s.title, create_time=s.create_time)


@router.get("/list", response_model=SessionListResponse)
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionListResponse:
    size = page_size or int(
        get_config_value(db, "session_page_size", settings.session_page_size)
    )
    total, items = session_crud.list_sessions(db, user.id, page, size)
    return SessionListResponse(
        total=total,
        items=[SessionItem(session_id=s.id, title=s.title, create_time=s.create_time) for s in items],
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
def session_detail(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionDetailResponse:
    s = session_crud.get_session_for_user(db, session_id, user.id)
    if s is None:
        raise NotFoundError(code="session_not_found", message="会话不存在")
    count = session_crud.count_messages(db, s.id)
    return SessionDetailResponse(
        session_id=s.id,
        title=s.title,
        create_time=s.create_time,
        message_count=count,
    )


@router.get("/{session_id}/messages", response_model=MessageListResponse)
def session_messages(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageListResponse:
    if session_crud.get_session_for_user(db, session_id, user.id) is None:
        raise NotFoundError(code="session_not_found", message="会话不存在")
    size = page_size or int(
        get_config_value(db, "message_page_size", settings.message_page_size)
    )
    total, messages = message_query.list_messages(db, session_id, page, size)
    return MessageListResponse(
        total=total,
        items=[
            MessageItem(
                message_id=m.id,
                role=m.role,
                content=m.content,
                reference_source=m.reference_source,
                intent_label=m.intent_label,
                create_time=m.create_time,
            )
            for m in messages
        ],
    )

"""会话 CRUD：创建（默认标题）/ 列表（owner+倒序）/ 归属校验。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ChatSession, Message
from app.services.config_service import get_config_value


def create_session(db: Session, user_id: int) -> ChatSession:
    title = get_config_value(db, "default_session_title", settings.default_session_title)
    session = ChatSession(user_id=user_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(
    db: Session, user_id: int, page: int = 1, page_size: int = 20
) -> tuple[int, list[ChatSession]]:
    """当前用户会话列表，按创建时间倒序分页。"""
    total = db.scalar(
        select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
    ) or 0
    items = (
        db.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.create_time.desc(), ChatSession.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .all()
    )
    return total, items


def get_session_for_user(db: Session, session_id: int, user_id: int) -> ChatSession | None:
    """按 id + owner 查询；不满足返回 None（调用方转 404，不泄露他人会话存在性）。"""
    return db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )


def count_messages(db: Session, session_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Message).where(Message.session_id == session_id)
    ) or 0


def update_title_if_default(db: Session, session: ChatSession, first_question: str) -> None:
    """首条用户消息后：若标题仍为默认值，更新为「前 N 字符 + …」摘要。"""
    default_title = get_config_value(db, "default_session_title", settings.default_session_title)
    if session.title != default_title:
        return
    max_len = int(get_config_value(db, "session_title_summary_len", settings.session_title_summary_len))
    stripped = first_question.strip()
    title = stripped[:max_len] + ("…" if len(stripped) > max_len else "")
    if title:
        session.title = title
        db.commit()

"""历史消息查询：按时间正序分页；单条消息定位（供反馈模块复用）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Message


def list_messages(
    db: Session, session_id: int, page: int = 1, page_size: int = 20
) -> tuple[int, list[Message]]:
    """会话历史消息，(create_time, id) 复合排序保证稳定有序分页。"""
    total = db.scalar(
        select(func.count()).select_from(Message).where(Message.session_id == session_id)
    ) or 0
    items = (
        db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.create_time.asc(), Message.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .all()
    )
    return total, items


def get_message(db: Session, message_id: int) -> Message | None:
    return db.get(Message, message_id)

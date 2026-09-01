"""历史消息查询：按时间正序分页；单条消息定位（供反馈模块复用）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Message

logger = get_logger(__name__)


def list_messages(
    db: Session, session_id: int, page: int = 1, page_size: int = 20
) -> tuple[int, list[Message]]:
    """会话历史消息，(create_time, id) 复合排序保证稳定有序分页。"""
    logger.debug("list_messages called for session_id=%d, page=%d, page_size=%d", session_id, page, page_size)
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
    logger.debug("list_messages returning %d items for session_id=%d", len(items), session_id)
    return total, items


def get_message(db: Session, message_id: int) -> Message | None:
    return db.get(Message, message_id)

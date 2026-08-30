"""按消息查询反馈：当前用户反馈（mine）+ 全量列表（all，统计基础 FR-005）。

与 submit 共用存在性/归属校验，越权或不存在统一 404。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Feedback
from app.services.feedback.submit import get_owned_message


def list_feedback_for_message(
    db: Session, message_id: int, user_id: int
) -> tuple[Feedback | None, list[Feedback]]:
    """返回 (mine, all)。mine 为当前用户对该消息的反馈（无则 None）。"""
    get_owned_message(db, message_id, user_id)
    items = list(
        db.scalars(
            select(Feedback)
            .where(Feedback.message_id == message_id)
            .order_by(Feedback.id)
        )
    )
    mine = next((f for f in items if f.user_id == user_id), None)
    return mine, items

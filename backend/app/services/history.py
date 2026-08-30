"""最近 N 轮对话历史读取（供 001 RAG 多轮上下文组装）。

取该会话按时间倒序的最后 N 条消息，再翻转回时间正序（最近的在末尾），
返回 `[{role, content}, ...]`。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message


def get_recent_turns(
    db: Session, session_id: int, turns: int = 6
) -> list[dict[str, str]]:
    if turns <= 0:
        return []
    rows = (
        db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.create_time.desc(), Message.id.desc())
            .limit(turns)
        )
        .all()
    )
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows]

"""反馈提交：存在性/归属/角色校验 + 类型/长度校验 + upsert（最后一次为准）。

校验链路（与 specs/005/research.md 一致）：存在 → 归属 → 角色 → 类型/长度。
- 存在性/归属：统一 404 message_not_found，不泄露他人会话消息存在性；
- 角色：仅 AI 回答可反馈，用户消息 400 not_ai_message（归属校验在前，
  保证他人会话的消息一律 404 而非 400）；
- 类型：like/dislike 二选一，缺失或非法 400 invalid_feedback_type；
- 长度：≤ feedback_max_length（可配置，默认 200，恰好等于上限通过），
  纯空白文字视同未填写（置 None）。

upsert 语义：命中 UNIQUE(message_id, user_id) 更新 type/text，否则插入新行。
采用「查改事务」实现（research.md 接受的方案之一）：单用户单消息反馈写入
低频，竞态窗口极小；若需严格并发安全，可换方言专属 ON DUPLICATE KEY
UPDATE / ON CONFLICT（代价是 SQLite/MySQL 双方言分支）。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import BizError, NotFoundError
from app.db.models import ChatSession, Feedback, Message
from app.schemas.feedback import FeedbackSubmitRequest
from app.services.config_service import get_config_value


def get_owned_message(db: Session, message_id: int, user_id: int) -> Message:
    """存在性 → 归属校验。越权与不存在统一 404（供 submit/query 复用）。"""
    msg = db.get(Message, message_id)
    if msg is None:
        raise NotFoundError(code="message_not_found", message="消息不存在")
    sess = db.get(ChatSession, msg.session_id)
    if sess is None or sess.user_id != user_id:
        raise NotFoundError(code="message_not_found", message="消息不存在")
    return msg


def validate_feedback(
    db: Session, request: FeedbackSubmitRequest
) -> tuple[str, str | None]:
    """类型必选 + 文字长度校验。返回规范化后的 (feedback_type, feedback_text)。"""
    ftype = request.feedback_type
    if ftype not in ("like", "dislike"):
        raise BizError(code="invalid_feedback_type", message="必须选择点赞或踩")

    text = request.feedback_text
    if text is not None and not text.strip():
        text = None  # 空白视同未填写
    if text is not None:
        max_len = int(
            get_config_value(db, "feedback_max_length", settings.feedback_max_length)
        )
        if len(text) > max_len:
            raise BizError(
                code="feedback_too_long",
                message=f"文字反馈不能超过 {max_len} 字",
            )
    return ftype, text


def submit_feedback(
    db: Session, message_id: int, user_id: int, request: FeedbackSubmitRequest
) -> tuple[Feedback, bool]:
    """提交 / 覆盖更新反馈。返回 (Feedback, created)。

    created=True 表示新建（API 层回 201），False 表示覆盖更新（200）。
    """
    msg = get_owned_message(db, message_id, user_id)
    if msg.role != "ai":
        raise BizError(code="not_ai_message", message="只能对 AI 回答提交反馈")
    ftype, text = validate_feedback(db, request)

    row = db.scalar(
        select(Feedback).where(
            Feedback.message_id == message_id,
            Feedback.user_id == user_id,
        )
    )
    if row is None:
        row = Feedback(
            message_id=message_id,
            user_id=user_id,
            feedback_type=ftype,
            feedback_text=text,
        )
        db.add(row)
        created = True
    else:
        row.feedback_type = ftype
        row.feedback_text = text
        created = False

    db.commit()
    db.refresh(row)
    return row, created

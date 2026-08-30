"""反馈接口 Pydantic 结构（与 specs/005/contracts/feedback-api.md 一致）。

注意：`feedback_type` 不在 schema 层用 Literal 拦截（那样非法值/缺失会返回
422 而非契约要求的 400 invalid_feedback_type）。类型合法值由业务层校验，
与模块 001「带自定义错误码的校验不进 schema 层」同一约定。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FeedbackSubmitRequest(BaseModel):
    feedback_type: str | None = None  # like | dislike，业务层校验转 400
    feedback_text: str | None = None  # ≤200 字（feedback_max_length，可配置）


class FeedbackSubmitResponse(BaseModel):
    message_id: int
    feedback_type: str
    feedback_text: str | None
    updated_at: datetime


class MineFeedback(BaseModel):
    """当前用户视角（不含 user_id，隐式）。"""

    feedback_type: str
    feedback_text: str | None
    updated_at: datetime


class FeedbackItem(BaseModel):
    """全量列表项（含提交者，供统计/前端展示）。"""

    user_id: int
    feedback_type: str
    feedback_text: str | None
    updated_at: datetime


class FeedbackQueryResponse(BaseModel):
    message_id: int
    mine: MineFeedback | None
    all: list[FeedbackItem]

"""会话/消息接口 Pydantic 结构（与 specs/004/contracts/session-api.md 一致）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    """v1 创建会话无必填参数，标题系统默认生成。"""

    pass


class SessionItem(BaseModel):
    session_id: int
    title: str
    create_time: datetime


class SessionListResponse(BaseModel):
    total: int
    items: list[SessionItem]


class SessionDetailResponse(BaseModel):
    session_id: int
    title: str
    create_time: datetime
    message_count: int


class MessageItem(BaseModel):
    message_id: int
    role: str
    content: str
    reference_source: list[dict] | None
    intent_label: str | None
    create_time: datetime


class MessageListResponse(BaseModel):
    total: int
    items: list[MessageItem]

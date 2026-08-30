"""RAG 问答接口结构（与 specs/001/contracts/chat-stream.md 一致）。

SSE 事件载荷：meta / data / finish / error，线上格式为
`event: <type>\\ndata: <json>\\n\\n`，由 services/rag/sse.py 封装。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: int = Field(ge=1)
    # 空/超长由业务层 validate_question 统一转契约错误码
    # （question_empty / question_too_long，HTTP 400），不在 schema 层拦截成 422
    question: str


class ReferenceSource(BaseModel):
    doc_name: str
    snippet: str


class MetaEvent(BaseModel):
    sources: list[ReferenceSource]


class DataEvent(BaseModel):
    delta: str


class PostcheckResult(BaseModel):
    status: Literal["ok", "review"]


class FinishEvent(BaseModel):
    message_id: int
    postcheck: PostcheckResult


class ErrorEvent(BaseModel):
    code: str
    message: str

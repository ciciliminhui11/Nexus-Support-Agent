"""链路埋点查询接口 Pydantic 结构（008）。

list 返回聚合概览（轻量：不含 question/detail 全文，FR-009）；detail 按 seq
返回单条 trace 全部 span（含 detail 全文）。字段命名对齐 `trace_event` 表。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TraceSummaryItem(BaseModel):
    """聚合概览行（list 用，轻量不含 question/detail）。"""

    trace_id: str
    trace_type: str
    start_time: datetime
    span_count: int
    has_error: bool
    doc_id: int | None = None
    session_id: int | None = None


class TraceListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TraceSummaryItem]


class TraceSpan(BaseModel):
    seq: int
    stage: str
    status: str
    start_at: datetime
    duration_ms: int | None
    detail: dict[str, Any] | None
    error: str | None


class TraceDetailResponse(BaseModel):
    trace_id: str
    trace_type: str
    spans: list[TraceSpan]

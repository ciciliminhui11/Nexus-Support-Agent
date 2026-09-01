"""链路埋点查询接口（仅管理员）：`GET /api/trace/list`、`GET /api/trace/detail`。

008 FR-005/FR-009：历史回溯定位问题；list 轻量聚合（按 trace_id GROUP BY），
detail 按 seq 还原单条 trace 全部 span（含 detail 全文）。查询直连追加式
`trace_event` 表，无写路径；普通用户访问返回 403。
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select, or_
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.exceptions import NotFoundError
from app.db.models import TraceEvent, User
from app.db.session import get_db
from app.schemas.trace import (
    TraceDetailResponse,
    TraceListResponse,
    TraceSpan,
    TraceSummaryItem,
)
from app.services.tracing.events import STAGE_META, STATUS_ERROR

router = APIRouter(prefix="/api/trace", tags=["trace"])


@router.get("/list", response_model=TraceListResponse)
def list_traces(
    trace_type: str | None = Query(default=None, description="ingest | chat"),
    doc_id: int | None = Query(default=None),
    session_id: int | None = Query(default=None),
    status: str | None = Query(default=None, description="trace 级状态 ok/error"),
    time_from: datetime | None = Query(default=None),
    time_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TraceListResponse:
    """按 trace_id 聚合的概览列表（不含 question/detail，轻量）。"""
    stmt = (
        select(
            TraceEvent.trace_id,
            TraceEvent.trace_type,
            func.min(TraceEvent.create_time).label("start_time"),
            func.count(TraceEvent.id).label("span_count"),
            func.max(TraceEvent.doc_id).label("doc_id"),
            func.max(TraceEvent.session_id).label("session_id"),
            func.sum(case((TraceEvent.status == STATUS_ERROR, 1), else_=0)).label(
                "error_count"
            ),
        )
        .group_by(TraceEvent.trace_id, TraceEvent.trace_type)
        .where(or_(TraceEvent.user_id.is_(None), TraceEvent.user_id == user.id))
    )

    if trace_type:
        stmt = stmt.where(TraceEvent.trace_type == trace_type)
    if doc_id is not None:
        stmt = stmt.where(TraceEvent.doc_id == doc_id)
    if session_id is not None:
        stmt = stmt.where(TraceEvent.session_id == session_id)
    if time_from is not None:
        stmt = stmt.where(TraceEvent.create_time >= time_from)
    if time_to is not None:
        stmt = stmt.where(TraceEvent.create_time <= time_to)
    if status:
        # trace 级状态存在 meta 行（seq=0）的 status 字段；子查询取 trace_id，
        # 避免过滤 meta 行导致 span_count 只数到 meta 一行。
        sub = select(TraceEvent.trace_id).where(
            TraceEvent.stage == STAGE_META, TraceEvent.status == status
        )
        stmt = stmt.where(TraceEvent.trace_id.in_(sub))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(func.min(TraceEvent.create_time).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        TraceSummaryItem(
            trace_id=r.trace_id,
            trace_type=r.trace_type,
            start_time=r.start_time,
            span_count=r.span_count,
            has_error=(r.error_count or 0) > 0,
            doc_id=r.doc_id,
            session_id=r.session_id,
        )
        for r in rows
    ]
    return TraceListResponse(
        total=total, page=page, page_size=page_size, items=items
    )


@router.get("/detail", response_model=TraceDetailResponse)
def detail_trace(
    trace_id: str = Query(..., description="链路 trace_id"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TraceDetailResponse:
    """按 seq 还原单条 trace 全部 span；trace_id 不存在返回 404。"""
    rows = (
        db.execute(
            select(TraceEvent)
            .where(TraceEvent.trace_id == trace_id)
            .where(or_(TraceEvent.user_id.is_(None), TraceEvent.user_id == user.id))
            .order_by(TraceEvent.seq)
        )
        .scalars()
        .all()
    )
    if not rows:
        raise NotFoundError(code="trace_not_found", message="trace 不存在")
    return TraceDetailResponse(
        trace_id=trace_id,
        trace_type=rows[0].trace_type,
        spans=[
            TraceSpan(
                seq=r.seq,
                stage=r.stage,
                status=r.status,
                start_at=r.start_at,
                duration_ms=r.duration_ms,
                detail=r.detail,
                error=r.error,
            )
            for r in rows
        ],
    )

"""反馈接口：提交/覆盖更新 + 按消息查询（均需鉴权）+ 管理端反馈列表。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.models import Feedback, User
from app.db.session import get_db
from app.schemas.feedback import (
    FeedbackItem,
    FeedbackListItem,
    FeedbackListResponse,
    FeedbackQueryResponse,
    FeedbackSubmitRequest,
    FeedbackSubmitResponse,
    MineFeedback,
)
from app.services.feedback import query as feedback_query
from app.services.feedback import submit as feedback_submit

router = APIRouter(prefix="/api/message", tags=["feedback"])


def _to_item(f: Feedback) -> FeedbackItem:
    return FeedbackItem(
        user_id=f.user_id,
        feedback_type=f.feedback_type,
        feedback_text=f.feedback_text,
        updated_at=f.update_time,
    )


@router.post("/{message_id}/feedback", response_model=FeedbackSubmitResponse)
def submit_feedback(
    message_id: int,
    body: FeedbackSubmitRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackSubmitResponse:
    """提交/覆盖反馈。新建 201，覆盖更新 200（契约要求动态状态码）。"""
    row, created = feedback_submit.submit_feedback(db, message_id, user.id, body)
    response.status_code = 201 if created else 200
    return FeedbackSubmitResponse(
        message_id=message_id,
        feedback_type=row.feedback_type,
        feedback_text=row.feedback_text,
        updated_at=row.update_time,
    )


@router.get("/{message_id}/feedback", response_model=FeedbackQueryResponse)
def get_feedback(
    message_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackQueryResponse:
    mine, items = feedback_query.list_feedback_for_message(db, message_id, user.id)
    return FeedbackQueryResponse(
        message_id=message_id,
        mine=(
            MineFeedback(
                feedback_type=mine.feedback_type,
                feedback_text=mine.feedback_text,
                updated_at=mine.update_time,
            )
            if mine is not None
            else None
        ),
        all=[_to_item(f) for f in items],
    )


@router.get("/admin/feedback/list", response_model=FeedbackListResponse)
def list_all_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feedback_type: str | None = Query(None),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FeedbackListResponse:
    """管理端反馈列表（需管理员权限）。"""
    from app.db.models import Message

    query = db.query(Feedback).join(Message, Feedback.message_id == Message.id)

    if feedback_type:
        query = query.filter(Feedback.feedback_type == feedback_type)

    total = query.count()
    rows = (
        query.add_columns(Message.content)
        .order_by(Feedback.update_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: list[FeedbackListItem] = []
    for f, content in rows:
        summary = content[:100] + ("..." if len(content) > 100 else "")
        items.append(
            FeedbackListItem(
                feedback_id=f.id,
                message_id=f.message_id,
                user_id=f.user_id,
                feedback_type=f.feedback_type,
                feedback_text=f.feedback_text,
                message_content=summary,
                updated_at=f.update_time,
            )
        )

    return FeedbackListResponse(total=total, items=items)

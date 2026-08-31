"""反馈 upsert：同一 (message_id, user_id) 覆盖更新，以最后一次为准（FR-006）。"""
from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError
from app.db.models import Feedback, Message
from app.schemas.feedback import FeedbackSubmitRequest
from app.services.feedback import submit as fb
from app.services.session.session_crud import create_session


def _ai_message(db, user_id):
    sess = create_session(db, user_id)
    msg = Message(session_id=sess.id, role="ai", content="回答内容")
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def test_upsert_updates_last_wins(db, make_user):
    user = make_user()
    msg = _ai_message(db, user.id)

    row1, created1 = fb.submit_feedback(
        db, msg.id, user.id, FeedbackSubmitRequest(feedback_type="dislike",
                                                   feedback_text="第一次踩")
    )
    assert created1 is True
    create_time = row1.create_time

    row2, created2 = fb.submit_feedback(
        db, msg.id, user.id, FeedbackSubmitRequest(feedback_type="like",
                                                   feedback_text="改为赞")
    )
    assert created2 is False
    assert row2.id == row1.id, "应复用同一条记录而非新增"
    assert row2.feedback_type == "like"
    assert row2.feedback_text == "改为赞"
    assert row2.create_time == create_time, "首次提交时间不变"
    assert row2.update_time >= row2.create_time

    # 库中仅一条反馈
    rows = db.query(Feedback).filter(Feedback.message_id == msg.id).all()
    assert len(rows) == 1


def test_upsert_cross_user_rejected(db, make_user):
    """越权反馈：他人会话中的消息 MUST 被拒绝（FR-009 / SC-006）。"""
    user1 = make_user(identifier="13800138000")
    user2 = make_user(identifier="13900139000")
    sess = create_session(db, user1.id)
    msg = Message(session_id=sess.id, role="ai", content="回答内容")
    db.add(msg)
    db.commit()
    db.refresh(msg)

    fb.submit_feedback(db, msg.id, user1.id,
                       FeedbackSubmitRequest(feedback_type="like"))

    with pytest.raises(NotFoundError) as exc:
        fb.submit_feedback(db, msg.id, user2.id,
                           FeedbackSubmitRequest(feedback_type="dislike"))
    assert exc.value.code == "message_not_found"

    # 他人反馈未写入，仅保留本人那条
    rows = db.query(Feedback).filter(Feedback.message_id == msg.id).all()
    assert len(rows) == 1
    assert rows[0].user_id == user1.id

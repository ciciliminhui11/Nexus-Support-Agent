"""反馈校验：类型必选/非法、文字长度边界、角色断言、不存在消息。"""
from __future__ import annotations

import pytest

from app.core.exceptions import BizError, NotFoundError
from app.db.models import Message
from app.schemas.feedback import FeedbackSubmitRequest
from app.services.feedback import submit as fb
from app.services.session.session_crud import create_session


def _ai_message(db, user_id, role="ai"):
    sess = create_session(db, user_id)
    msg = Message(session_id=sess.id, role=role, content="回答内容")
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def test_missing_type_rejected(db, make_user):
    user = make_user()
    msg = _ai_message(db, user.id)
    with pytest.raises(BizError) as e:
        fb.submit_feedback(db, msg.id, user.id, FeedbackSubmitRequest())
    assert e.value.code == "invalid_feedback_type"


def test_invalid_type_rejected(db, make_user):
    user = make_user()
    msg = _ai_message(db, user.id)
    req = FeedbackSubmitRequest(feedback_type="hate")
    with pytest.raises(BizError) as e:
        fb.submit_feedback(db, msg.id, user.id, req)
    assert e.value.code == "invalid_feedback_type"


@pytest.mark.parametrize("length,ok", [(199, True), (200, True), (201, False)])
def test_text_length_boundaries(db, make_user, length, ok):
    user = make_user()
    msg = _ai_message(db, user.id)
    req = FeedbackSubmitRequest(feedback_type="like", feedback_text="文" * length)
    if ok:
        row, created = fb.submit_feedback(db, msg.id, user.id, req)
        assert len(row.feedback_text) == length
        assert created is True
    else:
        with pytest.raises(BizError) as e:
            fb.submit_feedback(db, msg.id, user.id, req)
        assert e.value.code == "feedback_too_long"


def test_whitespace_text_stored_as_none(db, make_user):
    user = make_user()
    msg = _ai_message(db, user.id)
    req = FeedbackSubmitRequest(feedback_type="dislike", feedback_text="   \t  ")
    row, _ = fb.submit_feedback(db, msg.id, user.id, req)
    assert row.feedback_text is None


def test_user_message_rejected(db, make_user):
    user = make_user()
    msg = _ai_message(db, user.id, role="user")
    req = FeedbackSubmitRequest(feedback_type="like")
    with pytest.raises(BizError) as e:
        fb.submit_feedback(db, msg.id, user.id, req)
    assert e.value.code == "not_ai_message"


def test_nonexistent_message_is_404(db, make_user):
    user = make_user()
    with pytest.raises(NotFoundError) as e:
        fb.submit_feedback(db, 999999, user.id, FeedbackSubmitRequest(feedback_type="like"))
    assert e.value.code == "message_not_found"

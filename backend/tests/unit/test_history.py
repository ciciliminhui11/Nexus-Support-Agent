"""最近 N 轮历史读取测试。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.db.models import Message
from app.services.history import get_recent_turns


def test_get_recent_turns_order_and_limit(db, make_user):
    u = make_user()
    from app.services.session import session_crud

    s = session_crud.create_session(db, u.id)
    base = datetime.now()
    for i in range(5):
        db.add(Message(session_id=s.id, role="user", content=f"q{i}",
                       create_time=base + timedelta(seconds=i * 2)))
        db.add(Message(session_id=s.id, role="ai", content=f"a{i}",
                       create_time=base + timedelta(seconds=i * 2 + 1)))
    db.commit()

    turns = get_recent_turns(db, s.id, turns=4)
    # 按 data-model 契约：LIMIT N（最近 N 条消息）再倒序 → 最近 4 条为 q3/a3/q4/a4
    assert [t["content"] for t in turns] == ["q3", "a3", "q4", "a4"]
    assert turns[0]["role"] == "user"


def test_empty_session_returns_empty(db, make_user):
    u = make_user()
    from app.services.session import session_crud

    s = session_crud.create_session(db, u.id)
    assert get_recent_turns(db, s.id, turns=6) == []

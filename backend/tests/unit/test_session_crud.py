"""会话 CRUD 单元测试：创建默认标题、列表 owner 过滤、归属校验。"""
from __future__ import annotations

from app.db.models import Message
from app.services.session import session_crud


def test_create_session_default_title(db, make_user):
    u = make_user()
    s = session_crud.create_session(db, u.id)
    assert s.title == "新会话"
    assert s.user_id == u.id


def test_list_sessions_only_owner_and_desc(db, make_user):
    u1 = make_user(identifier="13800138000")
    u2 = make_user(identifier="13900139000")
    s1 = session_crud.create_session(db, u1.id)
    s2 = session_crud.create_session(db, u1.id)
    session_crud.create_session(db, u2.id)

    total, items = session_crud.list_sessions(db, u1.id, 1, 20)
    assert total == 2
    # 倒序：后创建的在前
    assert [s.id for s in items] == [s2.id, s1.id]


def test_get_session_for_user_ownership(db, make_user):
    u1 = make_user(identifier="13800138000")
    u2 = make_user(identifier="13900139000")
    s = session_crud.create_session(db, u1.id)
    assert session_crud.get_session_for_user(db, s.id, u1.id) is not None
    assert session_crud.get_session_for_user(db, s.id, u2.id) is None  # 越权


def test_update_title_if_default(db, make_user):
    u = make_user()
    s = session_crud.create_session(db, u.id)
    session_crud.update_title_if_default(db, s, "本产品的退货政策是什么？可以详细说明一下吗？")
    assert s.title.startswith("本产品的退货政策是什么？")
    assert s.title.endswith("…")


def test_update_title_keeps_custom(db, make_user):
    u = make_user()
    s = session_crud.create_session(db, u.id)
    s.title = "自定义标题"
    db.commit()
    session_crud.update_title_if_default(db, s, "新问题内容很长很长很长很长很长很长很长很长")
    assert s.title == "自定义标题"

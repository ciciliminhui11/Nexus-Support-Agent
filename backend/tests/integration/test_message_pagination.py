"""004 消息分页集成测试（T021）：page_size 上限 100、同秒写入稳定排序不重不漏。"""
from __future__ import annotations

from datetime import datetime

from app.db.models import ChatSession, Message
from app.services.session.session_crud import create_session


def _messages(client, headers, session_id, page=1, page_size=20):
    resp = client.get(
        f"/api/session/{session_id}/messages",
        params={"page": page, "page_size": page_size},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


def _insert_messages(db, session_id, role="ai", count=5, ts=None):
    ts = ts or datetime(2026, 8, 1, 12, 0, 0)
    for i in range(count):
        db.add(
            Message(
                session_id=session_id,
                role=role,
                content=f"消息-{i}",
                create_time=ts,  # 全部同一时间戳 → 校验 (create_time, id) 稳定排序
            )
        )
    db.commit()


def test_page_size_cap_100_enforced(client, db, auth_headers):
    headers, user = auth_headers()
    sess = create_session(db, user.id)
    _insert_messages(db, sess.id, count=150)

    # 上限内 page_size=100 → 200；首页 100 条
    body = _messages(client, headers, sess.id, page=1, page_size=100)
    assert body["total"] == 150
    assert len(body["items"]) == 100
    # 超过上限 101 → 422 参数校验失败
    resp = client.get(
        f"/api/session/{sess.id}/messages",
        params={"page": 1, "page_size": 101},
        headers=headers,
    )
    assert resp.status_code == 422


def test_same_second_messages_stable_order_no_dup(client, db, auth_headers):
    """同一秒内并发写入的消息按 (create_time, id) 稳定排序，翻页不重不漏。"""
    headers, user = auth_headers()
    sess = create_session(db, user.id)
    # 同一时间戳写 25 条（超过单页 20），id 递增
    _insert_messages(db, sess.id, count=25, ts=datetime(2026, 8, 1, 12, 0, 0))

    page1 = _messages(client, headers, sess.id, page=1, page_size=20)
    page2 = _messages(client, headers, sess.id, page=2, page_size=20)

    assert page1["total"] == 25
    assert len(page1["items"]) == 20
    assert len(page2["items"]) == 5

    ids = [m["message_id"] for m in page1["items"] + page2["items"]]
    # 不重、不漏
    assert len(ids) == len(set(ids)) == 25
    # 同一 create_time → 按 id 升序
    assert ids == sorted(ids)
    # 内容顺序与写入顺序一致（id 单调）
    contents = [m["content"] for m in page1["items"] + page2["items"]]
    assert contents == [f"消息-{i}" for i in range(25)]


def test_empty_session_pagination(client, db, auth_headers):
    headers, user = auth_headers()
    sess = create_session(db, user.id)
    body = _messages(client, headers, sess.id, page=1, page_size=20)
    assert body["total"] == 0
    assert body["items"] == []


def test_foreign_session_messages_404(client, db, auth_headers):
    """他人会话的消息列表不可见（归属校验 → 404，不泄露存在性）。"""
    headers, user = auth_headers()
    other = ChatSession(user_id=user.id, title="自己的")
    db.add(other)
    db.commit()
    db.refresh(other)
    other_headers, _ = auth_headers(identifier="13900139000")
    resp = client.get(
        f"/api/session/{other.id}/messages", params={}, headers=other_headers
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "session_not_found"

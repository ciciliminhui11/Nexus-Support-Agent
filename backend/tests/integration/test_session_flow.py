"""会话/消息 API 集成测试：创建/列表/详情/分页/数据隔离。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.db.models import Message


def test_create_session(client, auth_headers):
    headers, user = auth_headers()
    r = client.post("/api/session", headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["session_id"] > 0
    assert body["title"] == "新会话"


def test_session_list_paginated(client, auth_headers):
    headers, user = auth_headers()
    ids = [
        client.post("/api/session", headers=headers).json()["session_id"]
        for _ in range(3)
    ]
    r = client.get("/api/session/list?page=1&page_size=2", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    # 倒序：最后创建的在前
    assert body["items"][0]["session_id"] == ids[2]


def test_session_detail_with_message_count(client, auth_headers, db):
    headers, user = auth_headers()
    sid = client.post("/api/session", headers=headers).json()["session_id"]
    db.add(Message(session_id=sid, role="user", content="hi"))
    db.add(Message(session_id=sid, role="ai", content="hello"))
    db.commit()

    r = client.get(f"/api/session/{sid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["message_count"] == 2


def test_session_messages_ordered_and_paginated(client, auth_headers, db):
    headers, user = auth_headers()
    sid = client.post("/api/session", headers=headers).json()["session_id"]
    base = datetime.now()
    for i in range(5):
        db.add(Message(session_id=sid, role="user", content=f"q{i}",
                       create_time=base + timedelta(seconds=i * 2)))
        db.add(Message(session_id=sid, role="ai", content=f"a{i}",
                       create_time=base + timedelta(seconds=i * 2 + 1)))
    db.commit()

    r = client.get(f"/api/session/{sid}/messages?page=1&page_size=3", headers=headers)
    body = r.json()
    assert body["total"] == 10
    assert len(body["items"]) == 3
    # 时间正序：q0(0), a0(1), q1(2)
    assert body["items"][0]["content"] == "q0"
    assert body["items"][0]["role"] == "user"
    assert body["items"][2]["content"] == "q1"

    r2 = client.get(f"/api/session/{sid}/messages?page=2&page_size=3", headers=headers)
    # 第 2 页：a1(3), q2(4), a2(5)
    assert r2.json()["items"][0]["content"] == "a1"


def test_cross_user_access_denied(client, auth_headers):
    headers1, user1 = auth_headers(identifier="13800138000")
    headers2, user2 = auth_headers(identifier="13900139000")
    sid = client.post("/api/session", headers=headers1).json()["session_id"]

    # 他人访问 → 404 session_not_found（不泄露存在性）
    r = client.get(f"/api/session/{sid}", headers=headers2)
    assert r.status_code == 404
    assert r.json()["code"] == "session_not_found"

    r = client.get(f"/api/session/{sid}/messages", headers=headers2)
    assert r.status_code == 404


def test_unauthenticated_rejected(client):
    assert client.post("/api/session").status_code == 401
    assert client.get("/api/session/list").status_code == 401


def test_empty_session_messages_ok(client, auth_headers):
    headers, user = auth_headers()
    sid = client.post("/api/session", headers=headers).json()["session_id"]
    r = client.get(f"/api/session/{sid}/messages", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"total": 0, "items": []}

"""反馈端到端链路（宪法关键链路）：提交 → 覆盖更新 → 越权隔离 → 查询 + 校验边界。"""
from __future__ import annotations

from app.db.models import Message, SystemConfig


def _seed_ai_message(client, auth_headers, db, role="ai"):
    headers, user = auth_headers()
    sid = client.post("/api/session", headers=headers).json()["session_id"]
    msg = Message(session_id=sid, role=role, content="7 天无理由退货。")
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return headers, user, msg


def test_submit_like_and_query(client, auth_headers, db):
    headers, user, msg = _seed_ai_message(client, auth_headers, db)

    r = client.post(f"/api/message/{msg.id}/feedback", headers=headers,
                    json={"feedback_type": "like"})
    assert r.status_code == 201
    body = r.json()
    assert body["message_id"] == msg.id
    assert body["feedback_type"] == "like"
    assert body["feedback_text"] is None
    assert body["updated_at"]

    r = client.get(f"/api/message/{msg.id}/feedback", headers=headers)
    assert r.status_code == 200
    g = r.json()
    assert g["mine"]["feedback_type"] == "like"
    assert len(g["all"]) == 1
    assert g["all"][0]["user_id"] == user.id


def test_submit_with_text_and_overwrite(client, auth_headers, db):
    headers, user, msg = _seed_ai_message(client, auth_headers, db)

    r1 = client.post(f"/api/message/{msg.id}/feedback", headers=headers,
                     json={"feedback_type": "dislike",
                           "feedback_text": "没有解释运费承担方"})
    assert r1.status_code == 201

    r2 = client.post(f"/api/message/{msg.id}/feedback", headers=headers,
                     json={"feedback_type": "like", "feedback_text": ""})
    assert r2.status_code == 200, "覆盖更新返回 200"
    assert r2.json()["feedback_type"] == "like"
    assert r2.json()["feedback_text"] is None, "空白文字视同未填写"

    g = client.get(f"/api/message/{msg.id}/feedback", headers=headers).json()
    assert g["mine"]["feedback_type"] == "like"
    assert len(g["all"]) == 1, "重复提交只保留一条记录"


def test_cross_user_message_rejected(client, auth_headers, db):
    headers1, _, msg = _seed_ai_message(client, auth_headers, db)
    headers2, _ = auth_headers(identifier="13900139000")

    r = client.post(f"/api/message/{msg.id}/feedback", headers=headers2,
                    json={"feedback_type": "like"})
    assert r.status_code == 404
    assert r.json()["code"] == "message_not_found", "越权不泄露存在性"
    assert client.get(f"/api/message/{msg.id}/feedback", headers=headers2).status_code == 404


def test_user_message_is_400(client, auth_headers, db):
    headers, user, msg = _seed_ai_message(client, auth_headers, db, role="user")
    r = client.post(f"/api/message/{msg.id}/feedback", headers=headers,
                    json={"feedback_type": "like"})
    assert r.status_code == 400
    assert r.json()["code"] == "not_ai_message"


def test_nonexistent_message_404(client, auth_headers):
    headers, _ = auth_headers()
    r = client.post("/api/message/999999/feedback", headers=headers,
                    json={"feedback_type": "like"})
    assert r.status_code == 404
    assert r.json()["code"] == "message_not_found"


def test_invalid_type_and_too_long(client, auth_headers, db):
    headers, _, msg = _seed_ai_message(client, auth_headers, db)

    r = client.post(f"/api/message/{msg.id}/feedback", headers=headers,
                    json={"feedback_type": "hate"})
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_feedback_type"

    r = client.post(f"/api/message/{msg.id}/feedback", headers=headers,
                    json={})  # 未选类型
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_feedback_type"

    r = client.post(f"/api/message/{msg.id}/feedback", headers=headers,
                    json={"feedback_type": "like", "feedback_text": "文" * 201})
    assert r.status_code == 400
    assert r.json()["code"] == "feedback_too_long"


def test_runtime_config_overrides_length(client, auth_headers, db):
    """FR-007 可配置：system_config 覆盖默认 200。"""
    headers, _, msg = _seed_ai_message(client, auth_headers, db)
    db.add(SystemConfig(key="feedback_max_length", value="5"))
    db.commit()

    r = client.post(f"/api/message/{msg.id}/feedback", headers=headers,
                    json={"feedback_type": "like", "feedback_text": "五个字五"})
    assert r.status_code == 201

    r = client.post(f"/api/message/{msg.id}/feedback", headers=headers,
                    json={"feedback_type": "like", "feedback_text": "六个字六个字"})
    assert r.status_code == 400
    assert r.json()["code"] == "feedback_too_long"


def test_unauthenticated_rejected(client):
    r = client.post("/api/message/1/feedback", json={"feedback_type": "like"})
    assert r.status_code == 401
    assert client.get("/api/message/1/feedback").status_code == 401

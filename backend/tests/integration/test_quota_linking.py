"""003 配额联动集成测试（T029）：聊天消耗配额 → /api/auth/me 展示 used/remaining。

配额递增发生在 chat 端点同步段（校验 + 原子 UPDATE），空检索兜底不调 LLM；
`/api/auth/me` 走独立查询会话，验证计数已提交可见。跨日重置：昨日计数不计入今日。
"""
from __future__ import annotations

from datetime import date, timedelta

from app.db.models import UserQuotaDaily
from app.services.session.session_crud import create_session


def _ask(client, headers, sess, question: str) -> None:
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"session_id": sess.id, "question": question},
        headers=headers,
    ) as r:
        assert r.status_code == 200


def _quota(client, headers) -> dict:
    body = client.get("/api/auth/me", headers=headers).json()
    return body["quota"]


def test_chat_consumes_quota_visible_in_me(client, db, auth_headers, fake_embedding):
    headers, user = auth_headers()
    sess = create_session(db, user.id)
    assert _quota(client, headers)["used"] == 0
    _ask(client, headers, sess, "今天天气怎么样")
    _ask(client, headers, sess, "明天天气怎么样")
    quota = _quota(client, headers)
    assert quota["used"] == 2
    assert quota["remaining"] == quota["limit"] - 2
    assert quota["remaining"] >= 0


def test_quota_resets_across_days(client, db, auth_headers, fake_embedding):
    headers, user = auth_headers()
    # 昨日已有 9 次计数 → 今日 /me 应为 0（跨日重置）
    db.add(
        UserQuotaDaily(
            user_id=user.id, stat_date=date.today() - timedelta(days=1), count=9
        )
    )
    db.commit()
    assert _quota(client, headers)["used"] == 0
    sess = create_session(db, user.id)
    _ask(client, headers, sess, "今天天气怎么样")
    assert _quota(client, headers)["used"] == 1


def test_quota_limiting_hits_429(client, db, auth_headers, fake_embedding, monkeypatch):
    """联动闭环：达到上限后再次提问 → 429 quota_exceeded（配额未再递增）。"""
    headers, user = auth_headers()
    monkeypatch.setattr("app.config.settings.daily_quota_limit", 1)
    db.add(
        UserQuotaDaily(user_id=user.id, stat_date=date.today(), count=1)
    )
    db.commit()
    sess = create_session(db, user.id)
    resp = client.post(
        "/api/chat/stream",
        json={"session_id": sess.id, "question": "今天天气怎么样"},
        headers=headers,
    )
    assert resp.status_code == 429
    assert resp.json()["code"] == "quota_exceeded"
    # 拒绝的提问不产生新消息，配额保持 1
    assert _quota(client, headers)["used"] == 1

"""006 意图识别 × 001 聊天链路集成测试。

覆盖：闲聊/投诉/澄清短路（不检索不调用 LLM）、intent_label 落库、
after_sale→rag_qa 正常链路、unknown→默认链路。
"""
from __future__ import annotations

import json

import pytest

from app.config import settings
from app.db.models import Message
from app.intent.schema import IntentCategory
from app.intent.small_model.threshold import make_clarify_question
from app.services.rag import sse
from app.services.session.session_crud import create_session


def _parse_sse(stream_response):
    events = []
    for line in stream_response.iter_lines():
        if line.startswith("event: "):
            events.append({"event": line[len("event: ") :].strip(), "data": None})
        elif line.startswith("data: ") and events and events[-1]["data"] is None:
            events[-1]["data"] = json.loads(line[len("data: ") :].strip())
    return events


def _session_headers(auth_headers, db):
    headers, user = auth_headers()
    sess = create_session(db, user.id)
    return headers, sess


def _messages(db, session_id):
    return (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.id)
        .all()
    )


def _stream(client, headers, sess, question):
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"session_id": sess.id, "question": question},
        headers=headers,
    ) as r:
        return r.status_code, _parse_sse(r)


def test_complaint_short_circuit(client, db, auth_headers):
    headers, sess = _session_headers(auth_headers, db)
    status, events = _stream(client, headers, sess, "我要投诉你们的服务质量")
    assert status == 200
    assert [e["event"] for e in events] == ["data", "finish"]
    assert events[0]["data"]["delta"] == settings.intent_complaint_reply
    msgs = _messages(db, sess.id)
    assert msgs[0].intent_label == "投诉"
    assert msgs[1].content == settings.intent_complaint_reply
    assert msgs[1].reference_source == []


def test_small_talk_short_circuit(client, db, auth_headers):
    headers, sess = _session_headers(auth_headers, db)
    status, events = _stream(client, headers, sess, "你好")
    assert status == 200
    assert events[0]["data"]["delta"] == settings.intent_small_talk_reply
    msgs = _messages(db, sess.id)
    assert msgs[0].intent_label == "闲聊"


def test_after_sale_routes_to_rag(client, db, auth_headers, fake_embedding):
    """after_sale → rag_qa：不短路，走检索；intent_label=售后。"""
    headers, sess = _session_headers(auth_headers, db)
    status, events = _stream(client, headers, sess, "我要退货")
    assert status == 200
    assert events[-1]["event"] == "finish" or events[-1]["event"] == "data"
    msgs = _messages(db, sess.id)
    assert msgs[0].intent_label == "售后"
    # 无知识库 → 空检索兜底话术，仍走正常链路（未短路）
    assert events[-1]["event"] == "finish"
    assert msgs[1].role == "ai"


def test_clarify_reply_with_mocked_small_model(
    client, db, auth_headers, monkeypatch
):
    """中段置信度 → 澄清反问（不检索、不调 LLM）。"""
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(
        "app.intent.service.classify_small",
        lambda q: (IntentCategory.product_consult, 0.7),
    )
    headers, sess = _session_headers(auth_headers, db)
    status, events = _stream(client, headers, sess, "能退吗")
    assert status == 200
    assert [e["event"] for e in events] == ["data", "finish"]
    expected = make_clarify_question(IntentCategory.product_consult)
    assert events[0]["data"]["delta"] == expected
    msgs = _messages(db, sess.id)
    assert msgs[0].intent_label == "产品咨询"
    assert msgs[1].content == expected


def test_unknown_default_path_with_mocked_models(
    client, db, auth_headers, monkeypatch
):
    """小模型与兜底均无结果 → unknown → 默认链路（不阻断，走空检索兜底）。"""
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr("app.intent.service.classify_small", lambda q: None)
    monkeypatch.setattr("app.intent.service.classify_fallback", lambda q: None)
    headers, sess = _session_headers(auth_headers, db)
    status, events = _stream(client, headers, sess, "今天天气怎么样")
    assert status == 200
    assert [e["event"] for e in events] == ["data", "finish"]
    assert events[0]["data"]["delta"] == sse.FALLBACK_TEXT
    msgs = _messages(db, sess.id)
    assert msgs[0].intent_label == "未识别"


@pytest.mark.parametrize(
    "query,label",
    [
        ("我要投诉你们的服务质量", "投诉"),
        ("你好", "闲聊"),
        ("我要退货", "售后"),
    ],
)
def test_intent_label_persisted_for_rule_hits(client, db, auth_headers, query, label):
    headers, sess = _session_headers(auth_headers, db)
    _stream(client, headers, sess, query)
    msgs = _messages(db, sess.id)
    assert msgs[0].intent_label == label

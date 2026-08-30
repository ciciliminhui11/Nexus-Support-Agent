"""RAG 流式问答完整链路集成测试（宪法要求的关键链路测试）。

用真实 Chroma（EphemeralClient）+ 内存 SQLite + 伪 embedding + 假 LLM 流，
覆盖：正常流式（meta/data/finish）、引用来源、消息持久化、空检索兜底、
LLM 超时 error 事件、前置校验（超长/越权/配额）。
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from app.db.models import KnowledgeDoc, Message, UserQuotaDaily
from app.services.knowledge.splitter import make_snippet, split_text
from app.services.rag import llm as llm_service
from app.services.rag import retriever
from app.services.rag import sse
from app.services.session.session_crud import create_session
from app.vector_store import chroma

# 伪 embedding 按整段 CJK 做精确 token 匹配，故文档需逐字包含测试问题的关键短语
DOC_TEXT = (
    "本产品的退货政策是什么？退货政策是什么？"
    "本产品支持 7 天无理由退货，退货请联系客服提供订单号，退货时限为 7 天。"
)

# 伪 embedding 是稀疏关键词向量：文档 token 越多余弦越被摊薄（≈1/√n）。
# 0.55 是面向 bge-m3 稠密向量的校准基线，此处放宽到 0.1 只为验证链路而非校准阈值。
@pytest.fixture(autouse=True)
def _permissive_threshold(monkeypatch):
    monkeypatch.setattr("app.config.settings.rag_similarity_threshold", 0.1)


def _seed_ready_doc(db, fake_embedding, text=DOC_TEXT, doc_name="FAQ.md") -> KnowledgeDoc:
    doc = KnowledgeDoc(doc_name=doc_name, file_path="unused", status="就绪")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    chunks = split_text(text, 500, 80)
    embeds = fake_embedding.embed(chunks)
    records = [
        {"chunk_index": i, "text": t, "snippet": make_snippet(t), "embedding": e}
        for i, (t, e) in enumerate(zip(chunks, embeds))
    ]
    chroma.add_chunks(doc.id, records)
    return doc


def _parse_sse(stream_response):
    """把 SSE 行流解析为 [{"event": str, "data": dict}, ...]。"""
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
    return headers, user, sess


def _session_messages(db, session_id):
    return (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.id)
        .all()
    )


def test_normal_stream_with_sources(client, db, auth_headers, fake_embedding, monkeypatch):
    headers, user, sess = _session_headers(auth_headers, db)
    _seed_ready_doc(db, fake_embedding)

    async def fake_stream(messages):
        for tok in ["根据知识库", "，本产品支持", " 7 天无理由退货。"]:
            yield tok

    monkeypatch.setattr("app.api.chat.llm_service.stream_chat", fake_stream)

    with client.stream(
        "POST", "/api/chat/stream",
        json={"session_id": sess.id, "question": "本产品的退货政策是什么？"},
        headers=headers,
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse(r)

    # 事件序列：meta → data×3 → finish
    assert events[0]["event"] == "meta"
    assert events[0]["data"]["sources"], "应有引用来源"
    assert events[0]["data"]["sources"][0]["doc_name"] == "FAQ.md"
    deltas = [e for e in events if e["event"] == "data"]
    assert len(deltas) == 3
    assert "".join(e["data"]["delta"] for e in deltas) == "根据知识库，本产品支持 7 天无理由退货。"
    assert events[-1]["event"] == "finish"
    assert events[-1]["data"]["postcheck"]["status"] == "ok"

    # 持久化：user + ai 两条，ai 带引用来源
    msgs = _session_messages(db, sess.id)
    assert [m.role for m in msgs] == ["user", "ai"]
    assert msgs[1].reference_source and msgs[1].reference_source[0]["doc_name"] == "FAQ.md"
    assert events[-1]["data"]["message_id"] == msgs[1].id


def test_empty_retrieval_fallback_without_llm(client, db, auth_headers, fake_embedding, monkeypatch):
    headers, _, sess = _session_headers(auth_headers, db)
    _seed_ready_doc(db, fake_embedding)

    called = {"n": 0}

    async def fake_stream(messages):
        called["n"] += 1
        yield "不应调用"

    monkeypatch.setattr("app.api.chat.llm_service.stream_chat", fake_stream)

    with client.stream(
        "POST", "/api/chat/stream",
        json={"session_id": sess.id, "question": "今天的天气怎么样"},
        headers=headers,
    ) as r:
        events = _parse_sse(r)

    assert called["n"] == 0, "空检索不得调用 LLM"
    assert [e["event"] for e in events] == ["data", "finish"]
    assert events[0]["data"]["delta"] == sse.FALLBACK_TEXT

    msgs = _session_messages(db, sess.id)
    assert msgs[1].role == "ai"
    assert msgs[1].reference_source == []


def test_llm_timeout_emits_error(client, db, auth_headers, fake_embedding, monkeypatch):
    headers, _, sess = _session_headers(auth_headers, db)
    _seed_ready_doc(db, fake_embedding)

    async def boom(messages):
        raise llm_service.LLMTimeoutError()
        yield  # 不可达；无 yield 则是协程而非 async generator，无法被 async for 迭代

    monkeypatch.setattr("app.api.chat.llm_service.stream_chat", boom)

    with client.stream(
        "POST", "/api/chat/stream",
        json={"session_id": sess.id, "question": "退货政策是什么？"},
        headers=headers,
    ) as r:
        events = _parse_sse(r)

    assert events[0]["event"] == "meta"
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "llm_timeout"
    assert all(e["event"] != "finish" for e in events)

    msgs = _session_messages(db, sess.id)
    assert msgs[1].role == "ai"
    assert "超时" in msgs[1].content


def test_question_too_long_is_400(client, auth_headers):
    headers, _ = auth_headers()
    resp = client.post(
        "/api/chat/stream",
        json={"session_id": 1, "question": "问" * 501},
        headers=headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "question_too_long"


def test_foreign_session_is_403(client, db, auth_headers):
    headers, user = auth_headers()
    other = create_session(db, user.id)  # 属于同一用户 → 需构造他人会话
    # 再造一个用户，其会话对当前 user 不可见
    from app.db.models import User
    from app.core.security import hash_password

    other_user = User(
        account_identifier="13900139000",
        account_type="phone",
        password_hash=hash_password("secret123"),
    )
    db.add(other_user)
    db.commit()
    foreign_session = create_session(db, other_user.id)

    resp = client.post(
        "/api/chat/stream",
        json={"session_id": foreign_session.id, "question": "退货政策是什么？"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "session_forbidden"


def test_quota_exceeded_is_429(client, db, auth_headers, fake_embedding, monkeypatch):
    headers, user, sess = _session_headers(auth_headers, db)
    _seed_ready_doc(db, fake_embedding)
    # 当日已用 1 次，配额上限 1
    monkeypatch.setattr("app.config.settings.daily_quota_limit", 1)
    db.add(UserQuotaDaily(user_id=user.id, stat_date=date.today(), count=1))
    db.commit()

    resp = client.post(
        "/api/chat/stream",
        json={"session_id": sess.id, "question": "退货政策是什么？"},
        headers=headers,
    )
    assert resp.status_code == 429
    assert resp.json()["code"] == "quota_exceeded"


# ---------- 混合检索（向量 + BM25 + RRF + Reranker） ----------

# 伪 embedding 按整段 CJK 精确匹配，「退货政策如何办理」与 DOC_TEXT 无同 run
# → 向量路被 0.1 阈值滤掉；jieba 显著词「退货/政策」与 DOC_TEXT 共享 → BM25 路命中。
def test_hybrid_bm25_only_keyword_hit(client, db, auth_headers, fake_embedding, monkeypatch):
    headers, _, sess = _session_headers(auth_headers, db)
    _seed_ready_doc(db, fake_embedding)

    called = {"n": 0}

    async def fake_stream(messages):
        called["n"] += 1
        yield "根据知识库，退货政策如下。"

    monkeypatch.setattr("app.api.chat.llm_service.stream_chat", fake_stream)

    with client.stream(
        "POST", "/api/chat/stream",
        json={"session_id": sess.id, "question": "退货政策如何办理"},
        headers=headers,
    ) as r:
        events = _parse_sse(r)

    assert called["n"] == 1, "BM25 关键词命中应调用 LLM"
    assert events[0]["event"] == "meta"
    assert events[0]["data"]["sources"][0]["doc_name"] == "FAQ.md"


class _PromoteDeliveryReranker:
    """假精排器：把含「配送」的片段打到最前（验证重排覆盖融合序）。"""

    def rerank(self, query, texts):
        return [1.0 if "配送" in t else 0.0 for t in texts]


DELIVERY_TEXT = "配送时效：下单后三个工作日内发货，偏远地区除外。"


def test_fake_reranker_reorders_meta_sources(client, db, auth_headers, fake_embedding, monkeypatch):
    headers, _, sess = _session_headers(auth_headers, db)
    _seed_ready_doc(db, fake_embedding, text=DOC_TEXT, doc_name="FAQ.md")
    _seed_ready_doc(db, fake_embedding, text=DELIVERY_TEXT, doc_name="配送.md")
    monkeypatch.setattr(retriever, "get_reranker", lambda: _PromoteDeliveryReranker())

    async def fake_stream(messages):
        yield "相关说明如下。"

    monkeypatch.setattr("app.api.chat.llm_service.stream_chat", fake_stream)

    with client.stream(
        "POST", "/api/chat/stream",
        json={"session_id": sess.id, "question": "退货政策与配送时效"},
        headers=headers,
    ) as r:
        events = _parse_sse(r)

    assert events[0]["event"] == "meta"
    sources = [s["doc_name"] for s in events[0]["data"]["sources"]]
    assert sources[0] == "配送.md", "Reranker 精排应把配送片段排到最前"

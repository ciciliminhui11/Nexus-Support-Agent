"""008 chat 链路埋点集成测试（T014，FR-002）。

一次正常流式问答、一次意图短路问答、一次 LLM 异常问答，独立验证 chat 链路
各分支的 span 序列与 detail。假 LLM 流 + 伪 embedding + 真 Chroma。
"""
from __future__ import annotations

import pytest

from app.db.models import KnowledgeDoc, TraceEvent
from app.services.knowledge.splitter import make_snippet, split_text
from app.services.rag import llm as llm_service
from app.services.session.session_crud import create_session
from app.vector_store import chroma

DOC_TEXT = (
    "本产品的退货政策是什么？退货政策是什么？"
    "本产品支持 7 天无理由退货，退货请联系客服提供订单号，退货时限为 7 天。"
)


@pytest.fixture(autouse=True)
def _permissive_threshold(monkeypatch):
    monkeypatch.setattr("app.config.settings.rag_similarity_threshold", 0.1)


def _seed_ready_doc(db, fake_embedding, text=DOC_TEXT, doc_name="FAQ.md"):
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


def _session(db, auth_headers):
    headers, user = auth_headers()
    sess = create_session(db, user.id)
    return headers, sess


def _trace_rows(db, session_id):
    return (
        db.query(TraceEvent)
        .filter(TraceEvent.session_id == session_id)
        .order_by(TraceEvent.seq)
        .all()
    )


def _ask(client, headers, sess, question) -> list[str]:
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"session_id": sess.id, "question": question},
        headers=headers,
    ) as r:
        assert r.status_code == 200
        events: list[str] = []
        for line in r.iter_lines():
            if line.startswith("event: "):
                events.append(line[len("event: ") :].strip())
        return events


def test_normal_chat_trace(
    client, db, auth_headers, trace_flush, fake_embedding, monkeypatch
):
    """正常流式问答：≥6 条 span，intent 记录来源层/置信度，llm_stream 记首 token。"""
    headers, sess = _session(db, auth_headers)
    _seed_ready_doc(db, fake_embedding)

    async def fake_stream(messages):
        for tok in ["根据知识库", "，本产品支持", " 7 天无理由退货。"]:
            yield tok

    monkeypatch.setattr("app.api.chat.llm_service.stream_chat", fake_stream)
    events = _ask(client, headers, sess, "本产品的退货政策是什么？")
    assert events[-1] == "finish"
    assert trace_flush() >= 1

    rows = _trace_rows(db, sess.id)
    stages = [r.stage for r in rows]
    for stage in (
        "preflight",
        "intent",
        "retrieve",
        "prompt",
        "llm_stream",
        "postcheck",
        "finish",
    ):
        assert stage in stages, f"缺少阶段 {stage}"

    meta = rows[0]
    assert meta.status == "ok"
    assert meta.detail["question"] == "本产品的退货政策是什么？"

    intent = next(r for r in rows if r.stage == "intent")
    assert intent.status == "ok"
    assert intent.detail["layer"] in ("rule", "small_model", "fallback", "unknown")
    assert intent.detail["confidence"] is not None

    retrieve = next(r for r in rows if r.stage == "retrieve")
    assert retrieve.detail["ready_docs"] == 1
    assert retrieve.detail["vector_after_threshold"] >= 1
    assert retrieve.detail["sources"], "retrieve 应记录命中文档"

    llm = next(r for r in rows if r.stage == "llm_stream")
    assert llm.status == "ok"
    assert "first_token_ms" in llm.detail
    assert llm.detail["char_count"] == len("根据知识库，本产品支持 7 天无理由退货。")
    assert llm.detail["backend"] == "deepseek"


def test_short_circuit_trace(client, db, auth_headers, trace_flush):
    """意图短路：short_circuit span，不出现 retrieve/llm_stream。"""
    headers, sess = _session(db, auth_headers)
    events = _ask(client, headers, sess, "我要投诉你们的服务质量")
    assert events == ["data", "finish"]
    assert trace_flush() >= 1

    rows = _trace_rows(db, sess.id)
    stages = [r.stage for r in rows]
    assert "short_circuit" in stages
    assert "retrieve" not in stages
    assert "llm_stream" not in stages
    assert "finish" in stages
    short = next(r for r in rows if r.stage == "short_circuit")
    assert short.detail["handler"] == "complaint"
    assert rows[0].status == "ok"


def test_empty_retrieval_trace(client, db, auth_headers, trace_flush):
    """空检索兜底：empty_retrieval span，不调用 LLM。"""
    headers, sess = _session(db, auth_headers)
    events = _ask(client, headers, sess, "这个产品怎么用？")
    assert events == ["data", "finish"]
    assert trace_flush() >= 1

    rows = _trace_rows(db, sess.id)
    stages = [r.stage for r in rows]
    assert "empty_retrieval" in stages
    assert "llm_stream" not in stages
    empty = next(r for r in rows if r.stage == "empty_retrieval")
    assert empty.status == "ok"
    assert rows[0].status == "ok"


def test_llm_error_trace(
    client, db, auth_headers, trace_flush, fake_embedding, monkeypatch
):
    """LLM 超时：llm_stream span 记 error_code，trace 整体 error。"""
    headers, sess = _session(db, auth_headers)
    _seed_ready_doc(db, fake_embedding)

    async def boom(messages):
        yield ""  # 使函数成为 async 生成器；首次迭代前抛错
        raise llm_service.LLMTimeoutError()

    monkeypatch.setattr("app.api.chat.llm_service.stream_chat", boom)
    events = _ask(client, headers, sess, "本产品的退货政策是什么？")
    assert events[-1] == "error"
    assert trace_flush() >= 1

    rows = _trace_rows(db, sess.id)
    llm = next(r for r in rows if r.stage == "llm_stream")
    assert llm.status == "error"
    assert llm.detail["error_code"] == "llm_timeout"
    finish = next(r for r in rows if r.stage == "finish")
    assert finish.detail["status"] == "error"
    assert rows[0].status == "error"
    assert rows[0].error == "llm_timeout"

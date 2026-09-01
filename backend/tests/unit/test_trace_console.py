"""008 控制台链路块渲染单测。"""
from __future__ import annotations

from app.services.tracing.console import render_trace_block
from app.services.tracing.tracer import Tracer


def _sample_events():
    t = Tracer("chat", session_id=7, user_id=3, question="退货政策")
    with t.span("intent") as d:
        d.update(layer="rule", intent="product_consult", confidence=1.0)
    with t.span("retrieve") as d:
        d.update(
            ready_docs=2,
            vector_after_threshold=3,
            bm25_hits=5,
            candidate_pool=6,
            reranker="noop",
        )
        d["sources"] = [{"doc": "FAQ.md", "score": 0.83}, {"doc": "配送.md", "score": 0.61}]
    # 手工拼事件（不 finish，避免依赖 collector）
    events = [
        {
            "stage": "meta",
            "status": "ok",
            "seq": 0,
            "duration_ms": None,
            "detail": {"question": "退货政策", "trace_status": "ok"},
        },
        {
            "stage": "intent",
            "status": "ok",
            "seq": 1,
            "duration_ms": 1,
            "detail": {"layer": "rule", "intent": "product_consult", "confidence": 1.0},
        },
        {
            "stage": "retrieve",
            "status": "ok",
            "seq": 2,
            "duration_ms": 12,
            "detail": {
                "ready_docs": 2,
                "vector_after_threshold": 3,
                "bm25_hits": 5,
                "candidate_pool": 6,
                "reranker": "noop",
                "sources": [{"doc": "FAQ.md", "score": 0.83}, {"doc": "配送.md", "score": 0.61}],
            },
        },
    ]
    return t, events


def test_block_contains_key_info():
    t, events = _sample_events()
    block = render_trace_block(t, events)
    assert f"trace_id={t.trace_id[:12]}" in block
    assert "[chat]" in block
    assert "session_id=7" in block
    assert "intent" in block
    assert "layer=rule" in block
    assert "retrieve" in block
    assert "12ms" in block
    assert "FAQ.md(0.83)" in block
    assert "└─ end" in block


def test_block_skips_meta_and_shows_error():
    t = Tracer("ingest", doc_id=5)
    events = [
        {"stage": "meta", "status": "error", "seq": 0, "duration_ms": None,
         "detail": {"trace_status": "error"}, "error": "parse failed"},
        {"stage": "doc_parse", "status": "error", "seq": 1, "duration_ms": 3,
         "detail": {"chars": 0}, "error": "parse failed"},
    ]
    block = render_trace_block(t, events)
    assert "meta" not in block.splitlines()[1]  # meta 行被跳过
    assert "error=parse failed" in block
    assert "doc_parse" in block

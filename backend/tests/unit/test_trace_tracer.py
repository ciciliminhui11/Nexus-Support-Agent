"""008 Tracer 单测：span 计时 / 异常 / finish 幂等 / 短路 / 截断。"""
from __future__ import annotations

import pytest

from app.services.tracing.collector import collector
from app.services.tracing.events import QUESTION_MAX_CHARS, STATUS_ERROR, STATUS_OK
from app.services.tracing.tracer import Tracer


def test_span_records_timing_and_status():
    t = Tracer("chat", session_id=1, user_id=1, question="退货政策")
    with t.span("intent") as d:
        d["layer"] = "rule"
    with t.span("retrieve"):
        pass
    t.finish()
    events = collector.drain()
    stages = [e["stage"] for e in events]
    assert stages == ["meta", "intent", "retrieve"]
    intent = events[1]
    assert intent["status"] == STATUS_OK
    assert intent["detail"] == {"layer": "rule"}
    assert intent["duration_ms"] is not None and intent["duration_ms"] >= 0
    assert intent["seq"] == 1
    # meta 行 seq=0，携带关联 id 与 question
    meta = events[0]
    assert meta["seq"] == 0
    assert meta["session_id"] == 1
    assert meta["user_id"] == 1
    assert meta["detail"]["question"] == "退货政策"


def test_span_exception_marks_error_and_reraises():
    t = Tracer("chat", session_id=1)
    with pytest.raises(ValueError):
        with t.span("intent"):
            raise ValueError("boom")
    t.finish(status="error", error="boom")
    events = collector.drain()
    intent = events[1]
    assert intent["status"] == STATUS_ERROR
    assert "boom" in intent["error"]
    assert events[0]["status"] == "error"
    assert events[0]["error"] == "boom"


def test_mark_span_error_marks_caught_exception():
    """业务内捕获异常后显式标 span error（FR-008 LLM 错误路径）。"""
    t = Tracer("chat", session_id=1)
    with t.span("llm_stream") as detail:
        detail["error_code"] = "llm_timeout"
        t.mark_span_error("llm_stream", error="llm_timeout")  # 异常已在业务内捕获
    t.finish(status="error", error="llm_timeout")
    events = collector.drain()
    llm = next(e for e in events if e["stage"] == "llm_stream")
    assert llm["status"] == STATUS_ERROR
    assert llm["error"] == "llm_timeout"
    assert llm["detail"]["error_code"] == "llm_timeout"
    # 即使 span 正常退出，显式调用 mark_span_error 也标 error（业务主动标记）
    t2 = Tracer("chat", session_id=1)
    with t2.span("llm_stream"):
        pass
    t2.mark_span_error("llm_stream", error="x")
    t2.finish()
    events2 = collector.drain()
    llm2 = next(e for e in events2 if e["stage"] == "llm_stream")
    assert llm2["status"] == STATUS_ERROR
    assert llm2["error"] == "x"


def test_finish_idempotent():
    t = Tracer("ingest", doc_id=5)
    with t.span("doc_parse"):
        pass
    t.finish()
    t.finish()  # 第二次调用无效果
    events = collector.drain()
    assert len(events) == 2  # meta + doc_parse，仅一份


def test_disabled_trace_zero_collection(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "trace_enabled", False)
    t = Tracer("chat", session_id=1)
    with t.span("intent"):
        pass
    t.finish()
    assert collector.pending() == 0
    assert not t.enabled


def test_question_truncated():
    long_q = "很" * (QUESTION_MAX_CHARS + 100)
    t = Tracer("chat", session_id=1, question=long_q)
    t.finish()
    events = collector.drain()
    assert len(events[0]["detail"]["question"]) == QUESTION_MAX_CHARS


def test_invalid_trace_type_raises():
    with pytest.raises(ValueError):
        Tracer("bogus")

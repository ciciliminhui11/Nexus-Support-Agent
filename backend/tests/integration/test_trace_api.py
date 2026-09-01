"""008 查询 API 集成测试（T009）：权限 / list 聚合过滤 / detail 还原 / 404。

用 Tracer 直接生成链路事件（不经业务端点，纯测查询层），再经 `trace_flush(db)`
显式落库到测试库（后台 flush 已在 conftest 关闭）。
"""
from __future__ import annotations

from app.services.tracing.tracer import Tracer


def _emit_chat_trace(doc_id: int = None) -> str:
    """生成一条完整 chat 链路：preflight/intent/retrieve/llm_stream/finish。"""
    tracer = Tracer("chat", session_id=10, user_id=2, question="如何退款")
    with tracer.span("preflight"):
        pass
    with tracer.span("intent") as detail:
        detail["layer"] = "rule"
        detail["intent"] = "after_sale"
        detail["confidence"] = 1.0
    with tracer.span("retrieve") as detail:
        detail["ready_docs"] = 3
        detail["vector_after_threshold"] = 2
        detail["sources"] = [{"doc": "售后指南", "score": 0.88}]
        if doc_id:
            detail["doc_id"] = doc_id
    with tracer.span("llm_stream") as detail:
        detail["backend"] = "deepseek"
        detail["first_token_ms"] = 320
        detail["char_count"] = 120
    tracer.finish(status="ok")
    return tracer.trace_id


def test_list_denied_for_normal_user(client, db, auth_headers, trace_flush):
    headers, _ = auth_headers()  # 默认 role=user
    _emit_chat_trace()
    trace_flush()
    resp = client.get("/api/trace/list", headers=headers)
    assert resp.status_code == 403


def test_list_admin_aggregates_and_filters(client, db, auth_headers, trace_flush):
    headers, _ = auth_headers(role="admin")
    t1 = _emit_chat_trace()
    t2 = _emit_chat_trace()
    trace_flush()

    resp = client.get("/api/trace/list", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["items"][0]["trace_id"] in (t1, t2)
    item = body["items"][0]
    assert item["trace_type"] == "chat"
    assert item["span_count"] == 5  # meta + preflight/intent/retrieve/llm_stream
    assert item["has_error"] is False
    assert item["session_id"] == 10
    # 聚合项轻量：不含 detail/question
    assert "detail" not in item
    assert "question" not in item

    # 按 trace_type 过滤
    resp = client.get("/api/trace/list?trace_type=ingest", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    # 分页
    resp = client.get("/api/trace/list?page=1&page_size=1", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


def test_detail_restores_spans_and_404(client, db, auth_headers, trace_flush):
    headers, _ = auth_headers(role="admin")
    t1 = _emit_chat_trace()
    trace_flush()

    resp = client.get(f"/api/trace/detail?trace_id={t1}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["trace_id"] == t1
    assert body["trace_type"] == "chat"
    stages = [s["stage"] for s in body["spans"]]
    assert stages == ["meta", "preflight", "intent", "retrieve", "llm_stream"]
    # meta 行携带上下文（question 截断）
    meta = body["spans"][0]
    assert meta["detail"]["question"] == "如何退款"
    assert meta["seq"] == 0
    intent = body["spans"][2]
    assert intent["detail"]["layer"] == "rule"
    assert intent["detail"]["confidence"] == 1.0

    resp = client.get("/api/trace/detail?trace_id=no-such-trace", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "trace_not_found"


def test_detail_denied_for_normal_user(client, db, auth_headers, trace_flush):
    headers, _ = auth_headers()
    t1 = _emit_chat_trace()
    trace_flush()
    resp = client.get(f"/api/trace/detail?trace_id={t1}", headers=headers)
    assert resp.status_code == 403


def test_list_marks_error_trace(client, db, auth_headers, trace_flush):
    """含 error span 的 trace 在 list 中 has_error=true。"""
    headers, _ = auth_headers(role="admin")
    tracer = Tracer("chat", session_id=11, user_id=2, question="测试")
    try:
        with tracer.span("llm_stream"):
            raise RuntimeError("connect failed")
    except RuntimeError:
        pass  # span 内异常标 error 后上抛，业务侧捕获
    tracer.finish(status="error", error="connect failed")
    trace_flush()

    resp = client.get("/api/trace/list", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["items"][0]["has_error"] is True

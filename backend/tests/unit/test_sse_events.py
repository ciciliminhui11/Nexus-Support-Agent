"""SSE 事件封装：两行线上格式 + 各事件载荷（FR-009）。"""
from __future__ import annotations

import json

from app.services.rag import sse


def test_format_sse_two_lines():
    out = sse.format_sse("data", {"delta": "你好"})
    assert out == 'event: data\ndata: {"delta": "你好"}\n\n'


def test_meta_event_carries_sources():
    out = sse.sse_meta([{"doc_name": "FAQ.md", "snippet": "退货时限 7 天"}])
    assert out.startswith("event: meta\n")
    payload = json.loads(out.split("data: ", 1)[1].strip())
    assert payload["sources"][0]["doc_name"] == "FAQ.md"


def test_data_finish_error_payloads():
    data = json.loads(sse.sse_data("增量").split("data: ", 1)[1].strip())
    assert data == {"delta": "增量"}

    fin = json.loads(sse.sse_finish(42, {"status": "review"}).split("data: ", 1)[1].strip())
    assert fin == {"message_id": 42, "postcheck": {"status": "review"}}

    err = json.loads(sse.sse_error("llm_timeout", "回答生成超时").split("data: ", 1)[1].strip())
    assert err == {"code": "llm_timeout", "message": "回答生成超时"}

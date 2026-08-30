"""SSE 事件封装（FR-009）。

线上格式：`event: <type>\\ndata: <json>\\n\\n` 两行 + 空行。
事件序列约束：meta 至多一次且必在首个 data 之前；finish / error 互斥且为最后事件。
"""
from __future__ import annotations

import json


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_meta(sources: list[dict]) -> str:
    return format_sse("meta", {"sources": sources})


def sse_data(delta: str) -> str:
    return format_sse("data", {"delta": delta})


def sse_finish(message_id: int, postcheck: dict) -> str:
    return format_sse("finish", {"message_id": message_id, "postcheck": postcheck})


def sse_error(code: str, message: str) -> str:
    return format_sse("error", {"code": code, "message": message})


FALLBACK_TEXT = "抱歉，知识库中没有找到相关信息，请换个方式提问或者联系人工客服。"

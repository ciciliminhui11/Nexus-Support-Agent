"""LLM 流式调用：异步 httpx 逐块产出 token（FR-007 / FR-010）。

后端可插拔（settings.llm_backend）：
- `ollama`（默认）：POST /api/chat，NDJSON 行流；
- `deepseek`（OpenAI 兼容）：POST /chat/completions，SSE 行流。

异常映射：超时 → LLMTimeoutError；HTTP 429 → LLMRateLimitError；
其余网络/服务错误 → LLMConnectionError。由 api/chat.py 统一转 SSE `error` 事件。

超时策略：整体上限 `llm_timeout_seconds`，单次读取等待 `llm_first_token_timeout`
（同时覆盖首 token 等待与后续 chunk 间隔），满足 SC-001/SC-005。
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx

from app.config import settings


class LLMTimeoutError(Exception):
    """LLM 超时（首 token 或整体超限）。"""


class LLMRateLimitError(Exception):
    """LLM 服务限流（HTTP 429）。"""


class LLMConnectionError(Exception):
    """LLM 服务不可用 / 网络错误 / 非预期状态。"""


def _http_error_to_exc(exc: httpx.HTTPError) -> Exception:
    if isinstance(exc, httpx.TimeoutException):
        return LLMTimeoutError(message=exc)  # type: ignore[arg-type]
    return LLMConnectionError(message=exc)  # type: ignore[arg-type]


async def stream_chat(messages: list[dict]) -> AsyncGenerator[str, None]:
    """按 settings.llm_backend 分发的流式生成器。"""
    if settings.llm_backend == "deepseek":
        async for delta in _stream_deepseek(messages):
            yield delta
    else:
        async for delta in _stream_ollama(messages):
            yield delta


async def _stream_ollama(messages: list[dict]) -> AsyncGenerator[str, None]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {"model": settings.ollama_chat_model, "messages": messages, "stream": True}
    timeout = httpx.Timeout(
        timeout=settings.llm_timeout_seconds,
        read=settings.llm_first_token_timeout,
    )
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code == 429:
                    raise LLMRateLimitError()
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = httpx._types._json_loads(line)
                    except Exception:
                        continue
                    delta = data.get("message", {}).get("content", "")
                    if delta:
                        yield delta
                    if data.get("done"):
                        break
    except httpx.HTTPError as exc:
        raise _http_error_to_exc(exc)


async def _stream_deepseek(messages: list[dict]) -> AsyncGenerator[str, None]:
    base = settings.deepseek_base_url.rstrip("/") or "https://api.deepseek.com"
    url = f"{base}/chat/completions"
    payload = {
        "model": settings.deepseek_small_model,
        "messages": messages,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}
    timeout = httpx.Timeout(
        timeout=settings.llm_timeout_seconds,
        read=settings.llm_first_token_timeout,
    )
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code == 429:
                    raise LLMRateLimitError()
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[len("data:") :].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        data = httpx._types._json_loads(raw)
                    except Exception:
                        continue
                    delta = (
                        data.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content", "")
                    )
                    if delta:
                        yield delta
    except httpx.HTTPError as exc:
        raise _http_error_to_exc(exc)

"""006 模型 HTTP 调用单测（httpx.MockTransport 注入，不触真实网络）。"""
from __future__ import annotations

import httpx
import pytest

from app.config import settings
from app.intent.schema import IntentCategory
from app.intent.small_model.client import classify_small, post_chat_completion
from app.services.rag.llm import (
    LLMConnectionError,
    LLMRateLimitError,
    LLMTimeoutError,
)


def _make_transport(handler):
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """禁掉 429 重试退避 sleep，加速用例。"""
    monkeypatch.setattr("app.intent.small_model.client.time.sleep", lambda *a: None)


@pytest.fixture(autouse=True)
def _has_key(monkeypatch):
    # 小模型层独立凭据（SMALL_MODEL_*）；deepseek_api_key 供直接调用 post_chat_completion 的用例
    monkeypatch.setattr(settings, "small_model_name", "test-small-model")
    monkeypatch.setattr(settings, "small_model_api_key", "test-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")


def _ok_json(**overrides):
    payload = {
        "choices": [{"message": {"content": '{"intent": "after_sale", "confidence": 0.9}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    payload.update(overrides)
    return payload


def test_post_success_returns_json(monkeypatch):
    monkeypatch.setattr(settings, "intent_llm_max_retries", 0)

    def handler(request):
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json=_ok_json())

    data = post_chat_completion(
        [{"role": "user", "content": "hi"}],
        transport=_make_transport(handler),
    )
    assert data["choices"][0]["message"]["content"]


def test_429_retry_then_success(monkeypatch):
    monkeypatch.setattr(settings, "intent_llm_max_retries", 2)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=_ok_json())

    data = post_chat_completion([], transport=_make_transport(handler))
    assert calls["n"] == 2
    assert data["choices"]


def test_429_exhausted_raises_rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "intent_llm_max_retries", 0)

    def handler(request):
        return httpx.Response(429)

    with pytest.raises(LLMRateLimitError):
        post_chat_completion([], transport=_make_transport(handler))


def test_http_5xx_raises_connection(monkeypatch):
    monkeypatch.setattr(settings, "intent_llm_max_retries", 0)

    def handler(request):
        return httpx.Response(500, text="boom")

    with pytest.raises(LLMConnectionError):
        post_chat_completion([], transport=_make_transport(handler))


def test_timeout_raises_timeout(monkeypatch):
    monkeypatch.setattr(settings, "intent_llm_max_retries", 0)

    def handler(request):
        raise httpx.ReadTimeout("timeout")

    with pytest.raises(LLMTimeoutError):
        post_chat_completion([], transport=_make_transport(handler))


def test_empty_key_short_circuits(monkeypatch):
    # 显式传空 api_key（小模型层路径）：即使 deepseek_api_key 有值也绝不复用，必须短路
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    with pytest.raises(LLMConnectionError):
        post_chat_completion(
            [],
            api_key="",
            transport=_make_transport(lambda r: httpx.Response(200)),
        )


def test_deepseek_default_key_used_when_no_explicit_api_key():
    # 未显式传 api_key（兜底层路径）→ 回落 deepseek_api_key
    def handler(request):
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json=_ok_json())

    data = post_chat_completion([], transport=_make_transport(handler))
    assert data["choices"]


def test_classify_small_parses_json():
    def handler(request):
        return httpx.Response(200, json=_ok_json())

    result = classify_small("能退货吗", transport=_make_transport(handler))
    assert result == (IntentCategory.after_sale, 0.9)


def test_classify_small_http_error_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "intent_llm_max_retries", 0)

    def handler(request):
        return httpx.Response(500)

    assert classify_small("能退货吗", transport=_make_transport(handler)) is None


def test_classify_small_rate_limited_propagates(monkeypatch):
    monkeypatch.setattr(settings, "intent_llm_max_retries", 0)

    def handler(request):
        return httpx.Response(429)

    with pytest.raises(LLMRateLimitError):
        classify_small("能退货吗", transport=_make_transport(handler))

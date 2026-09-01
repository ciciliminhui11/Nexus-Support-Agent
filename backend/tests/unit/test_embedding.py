"""Embedding 批次有限重试 + openai_compat 后端 HTTP 行为（FR-011 增强）。"""
from __future__ import annotations

import json

import httpx
import pytest

from app.core.exceptions import LLMError
from app.services import embedding


class _FlakyOnce:
    """首次调用抛瞬时错误，之后成功。"""

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        if self.calls == 1:
            raise LLMError(message="瞬时网络超时")
        return [[1.0, 0.0, 0.0] for _ in texts]


class _AlwaysFail:
    def embed(self, texts):
        raise LLMError(message="Embedding 服务中断")


def test_retry_succeeds_after_transient_failure(monkeypatch):
    monkeypatch.setattr(embedding.settings, "embedding_retry_times", 2)
    monkeypatch.setattr(embedding.settings, "embedding_retry_backoff_seconds", 0.0)
    client = _FlakyOnce()

    result = embedding.embed_texts(client, ["a", "b"], batch_size=2)

    assert client.calls == 2  # 首次失败 + 1 次重试成功
    assert len(result) == 2


def test_retry_exhausted_reraises(monkeypatch):
    monkeypatch.setattr(embedding.settings, "embedding_retry_times", 2)
    monkeypatch.setattr(embedding.settings, "embedding_retry_backoff_seconds", 0.0)

    with pytest.raises(LLMError):
        embedding.embed_texts(_AlwaysFail(), ["a"], batch_size=1)


def test_retry_only_on_llm_error(monkeypatch):
    """非 LLMError（如本地模型加载 TypeError）不应被吞掉重试。"""
    monkeypatch.setattr(embedding.settings, "embedding_retry_times", 2)

    class _Boom:
        def embed(self, texts):
            raise ValueError("本地模型维度错误")

    with pytest.raises(ValueError):
        embedding.embed_texts(_Boom(), ["a"], batch_size=1)


# ---------- openai_compat 后端（OpenAI 兼容 /embeddings，如 SiliconFlow） ----------

def _make_client(transport: httpx.MockTransport, api_key: str = "test-key"):
    return embedding.OpenAIBackendEmbeddingClient(
        "https://api.siliconflow.cn/v1",
        "BAAI/bge-m3",
        api_key,
        transport=transport,
    )


def _embed_ok(items):
    return httpx.Response(
        200,
        json={"object": "list", "data": items, "model": "BAAI/bge-m3"},
    )


def test_openai_compat_embed_parses_and_orders_by_index():
    """请求形态正确，且响应 data 按 index 排序还原入参顺序。"""
    def handler(request):
        assert request.url.path == "/v1/embeddings"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "BAAI/bge-m3"
        assert body["input"] == ["a", "b"]
        return _embed_ok([
            {"object": "embedding", "index": 1, "embedding": [1.0, 0.0]},
            {"object": "embedding", "index": 0, "embedding": [0.0, 1.0]},
        ])

    vecs = _make_client(httpx.MockTransport(handler)).embed(["a", "b"])

    assert vecs == [[0.0, 1.0], [1.0, 0.0]]


def test_openai_compat_missing_key_raises_clear_error():
    with pytest.raises(LLMError, match="EMBEDDING_API_KEY"):
        _make_client(
            httpx.MockTransport(lambda r: httpx.Response(200)), api_key=""
        ).embed(["a"])


def test_openai_compat_http_error_wrapped_as_llm_error():
    def handler(request):
        return httpx.Response(502, json={"error": "bad gateway"})

    with pytest.raises(LLMError, match="Embedding 服务不可用"):
        _make_client(httpx.MockTransport(handler)).embed(["a"])


def test_openai_compat_transient_failure_retried_by_embed_texts(monkeypatch):
    """经 embed_texts 走有限重试：首次 502 → 重试成功。"""
    monkeypatch.setattr(embedding.settings, "embedding_retry_times", 2)
    monkeypatch.setattr(embedding.settings, "embedding_retry_backoff_seconds", 0.0)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(502, json={"error": "bad gateway"})
        return _embed_ok(
            [{"object": "embedding", "index": 0, "embedding": [0.5, 0.5]}]
        )

    client = _make_client(httpx.MockTransport(handler))

    assert embedding.embed_texts(client, ["a"], batch_size=1) == [[0.5, 0.5]]
    assert calls["n"] == 2

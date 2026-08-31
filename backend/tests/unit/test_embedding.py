"""Embedding 批次有限重试：瞬时网络失败后重试成功 / 重试耗尽上抛（FR-011 增强）。"""
from __future__ import annotations

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

"""Reranker 模块单元测试：Noop 保序、可插拔决议、懒加载、降级。"""
from __future__ import annotations

import sys
import types

import pytest

from app.config import settings
from app.services.rag import reranker


@pytest.fixture(autouse=True)
def _reset():
    reranker.reset_reranker()
    yield
    reranker.reset_reranker()


def _patch_find_spec(monkeypatch, present: bool):
    """用 find_spec 结果控制是否「安装」了 sentence-transformers。"""
    monkeypatch.setattr(
        reranker.importlib.util, "find_spec", lambda name: None if not present else object()
    )


def _inject_fake_sentence_transformers(monkeypatch, cross_encoder_cls):
    """向 sys.modules 注入假 sentence_transformers 模块（CrossEncoder 桩）。"""
    mod = types.ModuleType("sentence_transformers")
    mod.CrossEncoder = cross_encoder_cls
    monkeypatch.setitem(sys.modules, "sentence_transformers", mod)


def test_noop_preserves_order():
    r = reranker.NoopReranker()
    scores = r.rerank("q", ["a", "b", "c"])
    assert scores == [3.0, 2.0, 1.0]
    ordered = [t for _, t in sorted(zip(scores, ["a", "b", "c"]), reverse=True)]
    assert ordered == ["a", "b", "c"]


def test_get_reranker_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(settings, "rag_reranker_enabled", False)
    assert isinstance(reranker.get_reranker(), reranker.NoopReranker)


def test_get_reranker_when_st_missing_is_noop(monkeypatch):
    _patch_find_spec(monkeypatch, present=False)
    assert isinstance(reranker.get_reranker(), reranker.NoopReranker)


def test_get_reranker_when_st_present_is_crossencoder(monkeypatch):
    _patch_find_spec(monkeypatch, present=True)
    r = reranker.get_reranker()
    assert isinstance(r, reranker.CrossEncoderReranker)
    assert r.model_name == settings.rag_reranker_model


def test_crossencoder_lazy_load_uses_fake_module(monkeypatch):
    class FakeCrossEncoder:
        def __init__(self, model_name):
            self.model_name = model_name

        def predict(self, pairs):
            return [0.9 if "a" in pair[1] else 0.1 for pair in pairs]

    _inject_fake_sentence_transformers(monkeypatch, FakeCrossEncoder)
    r = reranker.CrossEncoderReranker("fake-model")
    assert r.rerank("q", ["a", "b"]) == [0.9, 0.1]
    assert r._model is not None  # 懒加载已触发


def test_crossencoder_construction_does_not_import(monkeypatch):
    """构造 CrossEncoderReranker 不应触发 sentence_transformers 导入。

    用差分断言而非 `not in sys.modules`：即使 lifespan 预热等场景已先导入过
    sentence_transformers（真实环境已安装时会发生），仍精确验证「构造」本身
    不新增任何 ST 模块（懒加载只在 _load()/rerank() 时发生）。
    """
    _patch_find_spec(monkeypatch, present=True)
    before = set(sys.modules)
    reranker.CrossEncoderReranker("fake-model")
    newly_imported = {
        m
        for m in set(sys.modules) - before
        if m == "sentence_transformers" or m.startswith("sentence_transformers.")
    }
    assert newly_imported == set()


def test_warmup_failure_sets_noop(monkeypatch):
    class FailingCrossEncoder:
        def __init__(self, model_name):
            raise RuntimeError("no model weights")

    _patch_find_spec(monkeypatch, present=True)
    _inject_fake_sentence_transformers(monkeypatch, FailingCrossEncoder)
    reranker.warmup()  # 应吞掉异常
    assert isinstance(reranker.get_reranker(), reranker.NoopReranker)


def test_reset_reranker_clears_cache(monkeypatch):
    _patch_find_spec(monkeypatch, present=False)
    assert isinstance(reranker.get_reranker(), reranker.NoopReranker)
    assert reranker._reranker_cache is not None
    reranker.reset_reranker()
    assert reranker._reranker_cache is None
    assert reranker._reranker_attempted is False

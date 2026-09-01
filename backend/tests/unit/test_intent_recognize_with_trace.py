"""008 意图公共溯源单测（T012，FR-006）：`recognize_with_trace` 返回溯源。

复用既有 `_recognize_with_trace`，返回 `(IntentResult, IntentTrace)`；外层
永不抛异常兜底与 `recognize()` 同款纪律。`recognize()` 行为不受影响。
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.intent.rules.engine import RuleEngine
from app.intent.schema import IntentCategory, SourceLayer
from app.intent.service import IntentTrace, recognize, recognize_with_trace

ENGINE = RuleEngine(
    keywords={
        "投诉": IntentCategory.complaint,
        "退货": IntentCategory.after_sale,
    },
    patterns={
        IntentCategory.complaint: ["我要投诉(?P<subject>.+)"],
    },
    negative_samples={},
)


@pytest.fixture(autouse=True)
def _real_rule_engine(monkeypatch):
    monkeypatch.setattr("app.intent.service.get_rule_engine", lambda: ENGINE)


@pytest.fixture(autouse=True)
def _model_enabled(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")


@pytest.fixture(autouse=True)
def _no_model_call(monkeypatch):
    monkeypatch.setattr("app.intent.service.classify_small", lambda q: None)
    monkeypatch.setattr("app.intent.service.classify_fallback", lambda q: None)


def test_rule_layer_trace(db):
    result, trace = recognize_with_trace(db, "我要投诉你们的服务")
    assert result.intent is IntentCategory.complaint
    assert result.source_layer is SourceLayer.rule
    assert trace.rule == {"intent": "complaint", "matched": ["投诉"]}
    assert trace.normalized_query == "我要投诉你们的服务"


def test_unknown_trace_on_empty_query(db):
    result, trace = recognize_with_trace(db, "  ")
    assert result.intent is IntentCategory.unknown
    assert trace.rule is None
    assert trace.small_model is None
    assert trace.fallback is None


def test_recognize_unchanged_returns_same_result(db):
    """公共 recognize() 行为与 recognize_with_trace 的 result 一致。"""
    r1 = recognize(db, "我要投诉你们的服务")
    r2, _ = recognize_with_trace(db, "我要投诉你们的服务")
    assert r1.intent is r2.intent
    assert r1.source_layer is r2.source_layer


def test_unexpected_error_degrades_unknown(db, monkeypatch):
    """内层意外异常：recognize_with_trace 降级 unknown 且 error 记录原因。"""

    def _boom(db, query):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("app.intent.service._recognize_with_trace", _boom)
    result, trace = recognize_with_trace(db, "任何问题")
    assert result.intent is IntentCategory.unknown
    assert result.source_layer is SourceLayer.unknown
    assert trace.error == "unexpected_error"
    assert isinstance(trace, IntentTrace)

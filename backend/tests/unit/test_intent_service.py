"""006 三层漏斗服务单测：注入确定性规则引擎 + mock 双模型，验证各分支与降级。"""
from __future__ import annotations

import pytest

from app.config import settings
from app.intent.rules.engine import RuleEngine
from app.intent.schema import IntentCategory, SourceLayer
from app.intent.service import debug_recognize, recognize
from app.services.rag.llm import LLMRateLimitError

ENGINE = RuleEngine(
    keywords={
        "投诉": IntentCategory.complaint,
        "退货": IntentCategory.after_sale,
    },
    patterns={
        IntentCategory.complaint: ["我要投诉(?P<subject>.+)"],
    },
    negative_samples={
        IntentCategory.complaint: ["投诉咨询中心"],
        IntentCategory.after_sale: ["退货政策"],
    },
)


@pytest.fixture(autouse=True)
def _real_rule_engine(monkeypatch):
    """注入确定性规则引擎（不依赖 yaml 配置）。"""
    monkeypatch.setattr("app.intent.service.get_rule_engine", lambda: ENGINE)


@pytest.fixture(autouse=True)
def _model_enabled(monkeypatch):
    """服务层模型路径需要非空密钥（mock 双模型前提下）。"""
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")


@pytest.fixture(autouse=True)
def _no_model_call(monkeypatch):
    """默认 mock 双模型返回 None，避免误触真实 API。"""
    monkeypatch.setattr("app.intent.service.classify_small", lambda q: None)
    monkeypatch.setattr("app.intent.service.classify_fallback", lambda q: None)


def test_empty_query_is_unknown(db):
    result = recognize(db, "")
    assert result.intent is IntentCategory.unknown
    assert result.source_layer is SourceLayer.unknown


def test_pure_punctuation_is_unknown(db):
    result = recognize(db, "！！！，，")
    assert result.intent is IntentCategory.unknown


def test_intent_disabled_is_unknown(db, monkeypatch):
    monkeypatch.setattr(settings, "intent_enabled", False)
    result = recognize(db, "我要投诉你们的服务质量")
    assert result.intent is IntentCategory.unknown
    assert debug_recognize(db, "我要投诉你们的服务质量")["error"] == "intent_disabled"


def test_rule_hit_short_circuits_without_models(db, monkeypatch):
    called = {"n": 0}

    def boom(q):
        called["n"] += 1
        raise AssertionError("规则层命中不得调用模型")

    monkeypatch.setattr("app.intent.service.classify_small", boom)
    result = recognize(db, "我要投诉你们的服务质量")
    assert result.intent is IntentCategory.complaint
    assert result.source_layer is SourceLayer.rule
    assert result.confidence == 1.0
    assert called["n"] == 0


def test_rule_suppressed_by_negative_sample_falls_to_model(db, monkeypatch):
    # 规则层「退货」被负样本「退货政策」抑制 → 交模型层（模型预测不被反向校准拒绝）
    monkeypatch.setattr(
        "app.intent.service.classify_small", lambda q: (IntentCategory.product_consult, 0.95)
    )
    result = recognize(db, "退货政策是什么")
    assert result.intent is IntentCategory.product_consult
    assert result.source_layer is SourceLayer.small_model


def test_no_api_key_degrades_unknown(db, monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")

    def boom(q):
        raise AssertionError("无密钥不得调用模型")

    monkeypatch.setattr("app.intent.service.classify_small", boom)
    result = recognize(db, "今天天气怎么样")  # 规则层未命中
    assert result.intent is IntentCategory.unknown
    assert debug_recognize(db, "今天天气怎么样")["error"] == "no_api_key"


def test_small_model_high_confidence_outputs(db, monkeypatch):
    monkeypatch.setattr(
        "app.intent.service.classify_small", lambda q: (IntentCategory.after_sale, 0.95)
    )

    def boom(q):
        raise AssertionError("高阈值不应调用兜底")

    monkeypatch.setattr("app.intent.service.classify_fallback", boom)
    result = recognize(db, "这个能退款吗")  # 「退款」不在规则层关键词内 → 走模型层
    assert result.intent is IntentCategory.after_sale
    assert result.source_layer is SourceLayer.small_model
    assert result.confidence == 0.95


def test_small_model_middle_band_outputs_clarify(db, monkeypatch):
    calls = {"n": 0}

    def small(q):
        calls["n"] += 1
        return (IntentCategory.product_consult, 0.7)  # 首判与重判都中段

    monkeypatch.setattr("app.intent.service.classify_small", small)
    monkeypatch.setattr(
        "app.intent.service.classify_fallback", lambda q: (_ for _ in ()).throw(AssertionError("中段不应流转兜底"))
    )
    result = recognize(db, "能退吗")
    assert result.intent is IntentCategory.product_consult
    assert result.source_layer is SourceLayer.small_model
    assert result.clarification_question and "确认" in result.clarification_question
    assert calls["n"] == 2  # 首判 + clarify_retry(1) 次重判


def test_small_model_low_confidence_falls_to_fallback(db, monkeypatch):
    monkeypatch.setattr(
        "app.intent.service.classify_small", lambda q: (IntentCategory.product_consult, 0.3)
    )
    monkeypatch.setattr(
        "app.intent.service.classify_fallback", lambda q: (IntentCategory.after_sale, 0.85)
    )
    result = recognize(db, "这个具体怎么弄")
    assert result.intent is IntentCategory.after_sale
    assert result.source_layer is SourceLayer.fallback


def test_reverse_calibrate_rejects_prediction(db, monkeypatch):
    monkeypatch.setattr(
        "app.intent.service.classify_small", lambda q: (IntentCategory.complaint, 0.95)
    )
    monkeypatch.setattr(
        "app.intent.service.classify_fallback", lambda q: (IntentCategory.product_consult, 0.9)
    )
    result = recognize(db, "投诉咨询中心电话多少")  # 负样本「投诉咨询中心」命中
    assert result.intent is IntentCategory.product_consult
    assert result.source_layer is SourceLayer.fallback
    trace = debug_recognize(db, "投诉咨询中心电话多少")
    assert trace["small_model_layer"]["reversed"] is True


def test_small_model_rate_limited_degrades_unknown(db, monkeypatch):
    monkeypatch.setattr(
        "app.intent.service.classify_small", lambda q: (_ for _ in ()).throw(LLMRateLimitError())
    )
    monkeypatch.setattr(
        "app.intent.service.classify_fallback",
        lambda q: (_ for _ in ()).throw(AssertionError("限流不应流转兜底")),
    )
    result = recognize(db, "这个能退款吗")  # 规则层未命中 → 走模型层
    assert result.intent is IntentCategory.unknown
    assert debug_recognize(db, "这个能退款吗")["error"] == "small_model_rate_limited"


def test_fallback_failure_degrades_unknown(db, monkeypatch):
    monkeypatch.setattr(
        "app.intent.service.classify_small", lambda q: (IntentCategory.product_consult, 0.3)
    )
    result = recognize(db, "这个具体怎么弄")
    assert result.intent is IntentCategory.unknown
    assert debug_recognize(db, "这个具体怎么弄")["error"] == "fallback_failed"


def test_recognize_never_raises(db, monkeypatch):
    def boom(q):
        raise RuntimeError("任意异常都必须被吞掉")

    monkeypatch.setattr("app.intent.service.classify_small", boom)
    monkeypatch.setattr("app.intent.service.classify_fallback", boom)
    result = recognize(db, "今天天气怎么样")  # 规则层未命中 → 走模型层
    assert result.intent is IntentCategory.unknown
    assert debug_recognize(db, "今天天气怎么样")["error"] == "unexpected_error"


def test_debug_recognize_shape(db):
    trace = debug_recognize(db, "我要投诉你们的服务质量")
    assert trace["rule_layer"]["intent"] == "complaint"
    assert trace["final"]["intent"] == "complaint"
    assert trace["final"]["source_layer"] == "rule"
    assert trace["normalized_query"]

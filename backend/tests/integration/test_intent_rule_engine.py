"""006 规则层集成测试：加载真实配置 yaml，验证 v1 基线词库/模板/负样本。"""
from __future__ import annotations

from app.intent.config_loader import (
    get_keywords,
    get_negative_samples,
    get_patterns,
    reload_intent_config,
)
from app.intent.normalize import normalize
from app.intent.rules.engine import get_rule_engine, reload_rule_engine
from app.intent.schema import IntentCategory


def _match(query: str):
    reload_rule_engine()
    reload_intent_config()
    return get_rule_engine().match(normalize(query))


def test_v1_keyword_baseline_loaded():
    reload_intent_config()
    keywords = get_keywords()
    assert keywords["投诉"] is IntentCategory.complaint
    assert keywords["退货"] is IntentCategory.after_sale
    assert keywords["你好"] is IntentCategory.small_talk
    assert keywords["价格"] is IntentCategory.product_consult


def test_v1_pattern_baseline_loaded():
    reload_intent_config()
    patterns = get_patterns()
    assert any("退款" in t for t in patterns[IntentCategory.after_sale])
    assert IntentCategory.complaint in patterns


def test_v1_negative_samples_loaded():
    reload_intent_config()
    negative = get_negative_samples()
    assert "投诉咨询中心" in negative[IntentCategory.complaint]
    assert "退货政策" in negative[IntentCategory.after_sale]


def test_acceptance_scenario_complaint_keyword_hit():
    # 验收场景 1：词库含「投诉」，直接命中不调用模型
    intent, matched = _match("我要投诉你们的服务质量")
    assert intent is IntentCategory.complaint
    assert matched


def test_compound_negative_suppressed():
    # 「投诉」出现在「投诉咨询中心」复合词中 → 被负样本抑制
    intent, _ = _match("投诉咨询中心电话多少")
    assert intent is None
    # 「投诉电话多少」同样是反例
    intent2, _ = _match("投诉电话多少")
    assert intent2 is None


def test_policy_inquiry_not_after_sale():
    # 「退货政策是什么」是咨询政策而非办理退换货 → 不命中 after_sale
    intent, _ = _match("退货政策是什么")
    assert intent is None


def test_pattern_after_sale_hit():
    intent, _ = _match("帮我查询退款")
    assert intent is IntentCategory.after_sale


def test_pattern_complaint_hit():
    intent, _ = _match("我要投诉你们的服务")
    assert intent is IntentCategory.complaint


def test_small_talk_hit():
    intent, _ = _match("你好")
    assert intent is IntentCategory.small_talk

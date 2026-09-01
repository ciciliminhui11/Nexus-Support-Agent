"""006 句式模板匹配单测（FR-004）：pyparsing.Regex 命名分组。"""
from __future__ import annotations

from app.intent.rules.template_patterns import TemplateMatcher
from app.intent.schema import IntentCategory

PATTERNS = {
    IntentCategory.after_sale: ["帮我查询(?P<subject>退款|退货|订单)"],
    IntentCategory.product_consult: ["帮我查一下(?P<subject>功能|价格)"],
    IntentCategory.complaint: ["我要投诉(?P<subject>.+)"],
}


def _matcher():
    return TemplateMatcher(PATTERNS)


def test_after_sale_pattern_hit():
    intent, matched = _matcher().match("帮我查询退款政策")
    assert intent is IntentCategory.after_sale
    assert matched and "帮我查询" in matched[0]


def test_complaint_pattern_with_group():
    intent, matched = _matcher().match("我要投诉你们的服务")
    assert intent is IntentCategory.complaint
    assert matched


def test_no_match_returns_none():
    intent, matched = _matcher().match("今天天气怎么样")
    assert intent is None
    assert matched == []


def test_cross_intent_conflict_returns_none():
    # 「帮我查询退款」命中 after_sale；「帮我查一下功能」命中 product_consult
    matcher = TemplateMatcher(
        {
            IntentCategory.after_sale: ["帮我查询(?P<subject>.+)"],
            IntentCategory.product_consult: ["帮我查一下(?P<subject>.+)"],
        }
    )
    # 文本只含一条模板 → 不冲突
    intent, _ = matcher.match("帮我查询退款政策")
    assert intent is IntentCategory.after_sale
    # 文本同时命中两条 → 冲突交模型层
    intent2, matched2 = matcher.match("帮我查询退款帮我查一下功能")
    assert intent2 is None
    assert len(matched2) == 2


def test_same_intent_multiple_templates_ok():
    matcher = TemplateMatcher(
        {
            IntentCategory.after_sale: [
                "帮我查询(?P<subject>.+)",
                "帮我看看(?P<subject>.+)",
            ]
        }
    )
    intent, matched = matcher.match("帮我查询退款帮我看看换货")
    assert intent is IntentCategory.after_sale
    assert len(matched) == 2


def test_invalid_template_skipped():
    matcher = TemplateMatcher({IntentCategory.after_sale: ["(未闭合", "有效模板(?P<x>.+)"]})
    intent, matched = matcher.match("有效模板abc")
    assert intent is IntentCategory.after_sale
    assert matched

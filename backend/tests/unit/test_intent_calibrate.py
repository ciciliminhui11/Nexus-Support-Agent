"""006 反向校准单测（FR-007）：负样本子串/正则匹配拦截。"""
from __future__ import annotations

from app.intent.schema import IntentCategory
from app.intent.small_model.calibrate import reverse_calibrate

NEGATIVE = {
    IntentCategory.complaint: ["投诉咨询中心", "re:投诉(电话|热线)"],
    IntentCategory.after_sale: ["退货政策"],
}


def test_substring_hit_rejects():
    assert reverse_calibrate("投诉咨询中心的电话", IntentCategory.complaint, NEGATIVE) is True


def test_regex_hit_rejects():
    assert reverse_calibrate("投诉电话是多少", IntentCategory.complaint, NEGATIVE) is True


def test_no_hit_allows():
    assert reverse_calibrate("我要投诉你们的服务", IntentCategory.complaint, NEGATIVE) is False


def test_intent_without_samples_allows():
    assert reverse_calibrate("你好", IntentCategory.small_talk, NEGATIVE) is False


def test_invalid_regex_ignored():
    bad = {IntentCategory.complaint: ["re:(未闭合"]}
    assert reverse_calibrate("x", IntentCategory.complaint, bad) is False

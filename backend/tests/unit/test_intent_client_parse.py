"""006 模型 JSON 输出解析单测：非法/越界/unknown → None。"""
from __future__ import annotations

from app.intent.schema import IntentCategory
from app.intent.small_model.client import _parse_intent_json


def test_valid_json():
    result = _parse_intent_json('{"intent": "after_sale", "confidence": 0.92}')
    assert result == (IntentCategory.after_sale, 0.92)


def test_invalid_json_returns_none():
    assert _parse_intent_json("自由文本闲聊") is None
    assert _parse_intent_json("") is None


def test_unknown_intent_rejected():
    assert _parse_intent_json('{"intent": "unknown", "confidence": 0.5}') is None


def test_unknown_enum_value_rejected():
    assert _parse_intent_json('{"intent": "foo", "confidence": 0.5}') is None


def test_confidence_out_of_range_rejected():
    assert _parse_intent_json('{"intent": "complaint", "confidence": 1.5}') is None
    assert _parse_intent_json('{"intent": "complaint", "confidence": -0.1}') is None


def test_confidence_non_numeric_rejected():
    assert _parse_intent_json('{"intent": "complaint", "confidence": "高"}') is None


def test_non_dict_json_rejected():
    assert _parse_intent_json('[1, 2, 3]') is None

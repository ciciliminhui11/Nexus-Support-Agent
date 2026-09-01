"""006 双阈值三分带单测（FR-008）。"""
from __future__ import annotations

from app.intent.schema import IntentCategory
from app.intent.small_model.threshold import decide, make_clarify_question


def test_decide_high():
    assert decide(0.95, high=0.9, low=0.6) == "high"
    assert decide(0.9, high=0.9, low=0.6) == "high"


def test_decide_middle():
    assert decide(0.7, high=0.9, low=0.6) == "middle"
    assert decide(0.6, high=0.9, low=0.6) == "middle"


def test_decide_low():
    assert decide(0.3, high=0.9, low=0.6) == "low"
    assert decide(0.0, high=0.9, low=0.6) == "low"


def test_make_clarify_question_for_rag_intents():
    q = make_clarify_question(IntentCategory.product_consult)
    assert "确认" in q and "售后" in q
    q2 = make_clarify_question(IntentCategory.after_sale)
    assert "产品咨询" in q2


def test_make_clarify_question_fallback():
    q = make_clarify_question(IntentCategory.small_talk)
    assert q and "描述" in q

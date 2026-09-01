"""006 文本归一化单测（FR-001）：全角/符号/繁简/形近。"""
from __future__ import annotations

import pytest

from app.intent.normalize import normalize


def test_fullwidth_to_halfwidth():
    # 全角字母数字→半角；全角符号随后按「去符号」规则一并去除
    assert normalize("ＡＢＣ１２３！") == "ABC123"


def test_removes_spaces_and_punctuation():
    assert normalize("你好， 世界！") == "你好世界"
    assert normalize("I want 退款!!") == "Iwant退款"


def test_removes_symbols_and_emoji():
    assert normalize("太差了😡") == "太差了"


def test_traditional_to_simplified():
    assert normalize("售後服務") == "售后服务"
    assert normalize("退貨退款") == "退货退款"


def test_lookalike_corrections():
    assert normalize("投拆") == "投诉"
    assert normalize("资询") == "咨询"


def test_chain_normalization():
    # 全角 + 繁体 + 符号混合
    assert normalize("Ｈｅｌｌｏ，我想咨詢一下產品退貨") == "Hello我想咨询一下产品退货"


def test_empty_and_whitespace():
    assert normalize("") == ""
    assert normalize("   \t\n") == ""


def test_pure_emoji_becomes_empty():
    assert normalize("😄🎉") == ""

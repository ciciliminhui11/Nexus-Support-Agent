"""006 AC 关键词匹配单测（FR-002/FR-003）：最长匹配 + 词边界。"""
from __future__ import annotations

from app.intent.rules.ac_automaton import AcKeywordMatcher
from app.intent.schema import IntentCategory

KW = {
    "投诉": IntentCategory.complaint,
    "退货": IntentCategory.after_sale,
    "退款": IntentCategory.after_sale,
    "投诉电话": IntentCategory.complaint,
}


def _matcher():
    return AcKeywordMatcher(KW)


def test_hit_returns_intent_and_matched():
    intent, matched = _matcher().match("我要投诉你们的服务质量")
    assert intent is IntentCategory.complaint
    assert "投诉" in matched


def test_cjk_neighbor_pass():
    # 「投诉」前后为 CJK 相邻，放行（验收场景 1）
    intent, _ = _matcher().match("我要投诉你们")
    assert intent is IntentCategory.complaint


def test_ascii_alnum_neighbor_rejected():
    # 相邻为 ASCII 字母/数字 → 视为嵌入子串，拒绝
    intent, matched = _matcher().match("abc投诉123")
    assert intent is None
    assert matched == []  # 全被边界校验拒绝


def test_longest_match_wins():
    # 「投诉电话」比「投诉」长 → 取更长命中（较长词决定意图）
    intent, matched = _matcher().match("我要投诉电话投诉你们")
    assert intent is IntentCategory.complaint
    assert "投诉电话" in matched


def test_equal_length_conflict_returns_none():
    # 投诉(complaint) 与 退货/退款(after_sale) 等长命中 → 冲突交模型层
    intent, matched = _matcher().match("投诉并退货")
    assert intent is None
    assert matched


def test_no_hit_returns_none():
    intent, matched = _matcher().match("今天天气怎么样")
    assert intent is None
    assert matched == []

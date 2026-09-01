"""AC 自动机多模式串匹配（FR-002 / FR-003）。

使用已装的 `ahocorasick`（import 名）Automaton：
- `iter_long` 逐位置产出最长命中；
- 多命中按长度降序取更长者；等长跨意图视为冲突 → 返回 None（交模型层裁决）；
- 词边界薄校验：命中串相邻字符为 ASCII 字母/数字才拒绝，CJK 相邻放行
  （保留「我要投诉你们…」这类 CJK 相邻命中；「投诉咨询中心」这类复合词由
  负样本抑制兜住，见 engine.py / calibrate.py）。
"""
from __future__ import annotations

from ahocorasick import Automaton

from ..schema import IntentCategory


def _valid_boundary(text: str, start: int, end: int) -> bool:
    """词边界薄校验：命中串相邻为 ASCII 字母/数字时拒绝。"""
    if start > 0 and text[start - 1].isascii() and text[start - 1].isalnum():
        return False
    if end < len(text) and text[end].isascii() and text[end].isalnum():
        return False
    return True


class AcKeywordMatcher:
    """AC 关键词匹配器（词 → 意图）。"""

    def __init__(self, keyword_map: dict[str, IntentCategory]) -> None:
        self._aut = Automaton()
        for word, intent in keyword_map.items():
            if word:
                self._aut.add_word(word, (word, intent))
        self._aut.make_automaton()

    def match(self, text: str) -> tuple[IntentCategory | None, list[str]]:
        """返回 (意图 | None, 命中的关键词列表)。None 表示无有效命中或冲突。"""
        candidates: list[tuple[str, IntentCategory]] = []
        for end_index, (word, intent) in self._aut.iter_long(text):
            start = end_index - len(word) + 1
            if _valid_boundary(text, start, end_index + 1):
                candidates.append((word, intent))
        if not candidates:
            return None, []
        matched_words = sorted({w for w, _ in candidates}, key=len, reverse=True)
        longest = len(matched_words[0])
        intents = {intent for w, intent in candidates if len(w) == longest}
        if len(intents) != 1:
            # 等长多意图冲突（FR-002 冲突裁决）：不阻断，交模型层
            return None, matched_words
        return intents.pop(), matched_words

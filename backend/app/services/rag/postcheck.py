"""输出后来源校验（FR-013 / research §11）：启发式幻觉检出。

对 LLM 完整输出按句子切分；对长度 ≥ 阈值的长断言，计算其与全部知识片段
的字符二元组重叠率。重叠率过低视为「超出知识库范围」，标记 status=review
（经 finish 事件 postcheck 字段提示前端），不阻断回答。
"""
from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"[。！？!?；;\n]")
_MIN_SENTENCE = 20  # 长断言才值得判定
_MIN_OVERLAP = 0.1  # 二元组重叠率下限


def _bigrams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}


def postcheck(answer: str, chunks: list[dict]) -> dict:
    """返回 {"status": "ok" | "review"}。chunks 为空视为 ok（兜底场景无需校验）。"""
    if not answer or not chunks:
        return {"status": "ok"}

    corpus: set[str] = set()
    for c in chunks:
        corpus |= _bigrams(c["text"])
    if not corpus:
        return {"status": "ok"}

    for sentence in _SENTENCE_SPLIT.split(answer):
        s = sentence.strip()
        if len(s) < _MIN_SENTENCE:
            continue
        sb = _bigrams(s)
        if not sb:
            continue
        overlap = len(sb & corpus) / len(sb)
        if overlap < _MIN_OVERLAP:
            return {"status": "review"}
    return {"status": "ok"}

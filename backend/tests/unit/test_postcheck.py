"""输出后来源校验（FR-013）：长断言与知识片段的重叠率判定。"""
from __future__ import annotations

from app.services.rag.postcheck import postcheck

_CHUNKS = [
    {"doc_name": "FAQ.md", "text": "本产品支持 7 天无理由退货，退货请联系客服提供订单号。"}
]


def test_answer_within_knowledge_is_ok():
    assert postcheck("本产品支持 7 天无理由退货。", _CHUNKS) == {"status": "ok"}


def test_answer_with_unrelated_long_claim_is_review():
    # 20 字以上长断言，与知识片段无重叠 → 标记待人工核实
    answer = "天空是蓝色的，月亮上住着嫦娥，独角兽每天都会飞过大海。"
    assert postcheck(answer, _CHUNKS) == {"status": "review"}


def test_empty_answer_or_no_chunks_is_ok():
    assert postcheck("", _CHUNKS) == {"status": "ok"}
    assert postcheck("随便说说", []) == {"status": "ok"}

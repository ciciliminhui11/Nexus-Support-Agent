"""Prompt 组装：编号来源注入（FR-006）与上下文预算截断（FR-011）。"""
from __future__ import annotations

from app.services.rag import prompt as p


def _chunks(n=2, text="退货时限为 7 天"):
    return [
        {"doc_name": f"FAQ{i}.md", "snippet": "片段" + str(i), "text": text, "doc_id": i}
        for i in range(1, n + 1)
    ]


def test_format_chunks_numbers_sources():
    out = p.format_chunks(_chunks(2, "退货"))
    assert "【1】来源：FAQ1.md｜片段：片段1\n退货" in out
    assert "【2】来源：FAQ2.md｜片段：片段2\n退货" in out


def test_build_messages_structure():
    history = [{"role": "user", "content": "前一个问题"}, {"role": "ai", "content": "前一个回答"}]
    msgs = p.build_messages("现在的问题", history, _chunks(), max_tokens=6000)
    assert msgs[0]["role"] == "system"
    assert "【1】来源" in msgs[0]["content"]
    assert msgs[1:] == [
        {"role": "user", "content": "前一个问题"},
        {"role": "ai", "content": "前一个回答"},
        {"role": "user", "content": "现在的问题"},
    ]


def test_no_chunks_keeps_plain_system():
    msgs = p.build_messages("q", [], [], max_tokens=6000)
    assert msgs[0]["content"] == p.SYSTEM_PROMPT


def test_truncation_drops_earliest_history_first():
    # 预算只够「系统+知识+问题」，历史放不下 → 丢历史、保留知识（FR-011 降级①）
    chunks = _chunks(1, text="知" * 100)
    history = [{"role": "user", "content": "历" * 100}]
    msgs = p.build_messages("问" * 10, history, chunks, max_tokens=100)
    # 历史被丢弃，但知识片段保留
    assert len(msgs) == 2
    assert "【1】来源" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "问" * 10


def test_truncation_reduces_chunks_before_losing_all_knowledge():
    # 极小 budget：历史已被丢光仍超 → 从末尾减知识片段，系统提示不含任何编号
    chunks = _chunks(3, text="片" * 50)
    msgs = p.build_messages("问" * 5, [], chunks, max_tokens=20)
    assert "【1】" not in msgs[0]["content"]

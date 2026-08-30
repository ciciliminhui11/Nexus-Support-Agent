"""BM25 模块单元测试：分词、显著词闸门、打分排序、降级。"""
from __future__ import annotations

import pytest

from app.services.rag import bm25


def test_tokenize_chinese_keeps_words_and_single_chars():
    toks = bm25.tokenize("今天的天气怎么样")
    assert "今天" in toks
    assert "天气" in toks
    assert "怎么样" in toks
    assert "的" in toks  # 单字保留用于打分


def test_significant_tokens_filters_single_chars():
    toks = bm25.tokenize("今天的天气怎么样")
    sig = bm25.significant_tokens(toks)
    assert set(sig) == {"今天", "天气", "怎么样"}
    assert "的" not in sig


def test_tokenize_ascii_words():
    toks = bm25.tokenize("RTX 4090 is a GPU")
    assert "rtx" in toks
    assert "4090" in toks
    assert "gpu" in toks
    assert not any(len(t) < 2 for t in toks)


def test_passes_gate_requires_shared_significant_term():
    # 「天气」查询与「退货政策」文档仅共享功能字（的/么/天）→ 闸门不过
    assert not bm25.passes_gate(
        bm25.tokenize("今天的天气怎么样"), bm25.tokenize("退货政策是什么")
    )
    # 共享「的」但不共享显著词 → 不过
    assert not bm25.passes_gate(
        bm25.tokenize("天气的"), bm25.tokenize("产品的")
    )
    # 共享显著词（退货/政策）→ 过
    assert bm25.passes_gate(
        bm25.tokenize("退货政策是什么"), bm25.tokenize("本产品的退货政策")
    )


def test_bm25_ranks_relevant_docs_higher():
    corpus = [
        "退货政策是什么？",              # 与查询最相关
        "本产品支持七天无理由退货",       # 仅共享「退货」
        "今天的天气怎么样",              # 无关，闸门不过
    ]
    index = bm25.BM25Index.build(corpus)
    ranked = index.rank("退货政策是什么")
    assert ranked[0][0] == 0
    idxs = [i for i, _ in ranked]
    assert idxs == [0, 1]  # 天气文档被闸门排除


def test_bm25_gate_excludes_function_word_only_match():
    index = bm25.BM25Index.build(["退货政策是什么"])
    assert index.rank("今天的天气怎么样") == []  # 功能字假阳性被闸门排除


def test_bm25_rank_top_k_limits():
    corpus = ["退货政策A", "退货政策B", "退货政策C"]
    index = bm25.BM25Index.build(corpus)
    assert len(index.rank("退货政策", top_k=2)) == 2


def test_bm25_empty_corpus():
    index = bm25.BM25Index.build([])
    assert index.rank("退货政策") == []


def test_bm25_jieba_unavailable_degrades(monkeypatch):
    monkeypatch.setattr(bm25, "JIEBA_AVAILABLE", False)
    # 中文路关闭：中文 token 不再产生
    assert bm25.tokenize("今天的天气怎么样") == []
    index = bm25.BM25Index.build(["退货政策是什么"])
    assert index.rank("今天的天气怎么样") == []
    # ASCII 路仍可用
    assert "rtx" in bm25.tokenize("RTX 4090 GPU")

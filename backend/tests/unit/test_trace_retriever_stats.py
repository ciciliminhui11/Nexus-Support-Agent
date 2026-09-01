"""008 retriever 召回统计单测（T011，FR-007）：可选 `stats` 就地填充。

含不传 stats 行为完全不变；各阶段计数（就绪文档 / 向量阈值前后 / BM25 /
候选池 / Reranker 状态 / empty）可在不侵入业务的情况下供 trace span 使用。
"""
from __future__ import annotations

import pytest

from app.db.models import KnowledgeDoc
from app.services.knowledge.splitter import make_snippet, split_text
from app.services.rag import bm25
from app.services.rag import retriever
from app.services.rag.reranker import NoopReranker
from app.vector_store import chroma


def _seed(db, fake_embedding, text, doc_name="FAQ.md", status="就绪") -> KnowledgeDoc:
    doc = KnowledgeDoc(doc_name=doc_name, file_path="unused", status=status)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    chunks = split_text(text, 500, 80)
    embeds = fake_embedding.embed(chunks)
    records = [
        {"chunk_index": i, "text": t, "snippet": make_snippet(t), "embedding": e}
        for i, (t, e) in enumerate(zip(chunks, embeds))
    ]
    chroma.add_chunks(doc.id, records)
    return doc


def test_stats_filled_on_normal_hit(db, fake_embedding, monkeypatch):
    """正常命中：各阶段计数与 Reranker 状态正确填充。"""
    _seed(db, fake_embedding, "退货政策是什么？支持7天无理由退货。")
    monkeypatch.setattr(retriever, "get_reranker", lambda: NoopReranker())

    stats: dict = {}
    hits = retriever.retrieve(
        db, "退货政策是什么", fake_embedding,
        top_k=6, threshold=0.1, candidate_k=20, stats=stats,
    )
    assert len(hits) == 1
    assert stats["ready_docs"] == 1
    assert stats["vector_before_threshold"] >= 1
    assert stats["vector_after_threshold"] == 1
    assert stats["bm25_available"] is True
    assert stats["bm25_hits"] >= 1
    assert stats["candidate_pool"] >= 1
    assert stats["reranker"] == "noop"
    assert "empty" not in stats


def test_stats_filled_on_vector_empty_bm25_hit(db, fake_embedding, monkeypatch):
    """向量路全被阈值滤掉，仅 BM25 命中：诊断关键信息可见。"""
    _seed(db, fake_embedding, "退货政策：支持七天无理由退货。")
    monkeypatch.setattr(
        chroma, "query",
        lambda *a, **k: {"ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]},
    )
    stats: dict = {}
    hits = retriever.retrieve(
        db, "退货政策如何办理", fake_embedding,
        top_k=6, threshold=0.1, candidate_k=20, stats=stats,
    )
    assert len(hits) == 1
    assert stats["vector_before_threshold"] == 0
    assert stats["vector_after_threshold"] == 0
    assert stats["bm25_hits"] >= 1
    assert stats.get("empty") is not True


def test_stats_empty_true_when_no_ready_docs(db, fake_embedding):
    stats: dict = {}
    hits = retriever.retrieve(
        db, "退货政策", fake_embedding, top_k=6, threshold=0.1, stats=stats
    )
    assert hits == []
    assert stats["ready_docs"] == 0
    assert stats["empty"] is True


def test_stats_empty_true_when_both_routes_empty(db, fake_embedding, monkeypatch):
    """有就绪文档但两路皆空 → empty=True（空检索兜底分支）。"""
    _seed(db, fake_embedding, "退货政策：支持七天无理由退货。")
    monkeypatch.setattr(bm25, "JIEBA_AVAILABLE", False)
    monkeypatch.setattr(
        chroma, "query",
        lambda *a, **k: {"ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]},
    )
    stats: dict = {}
    hits = retriever.retrieve(
        db, "今天的天气怎么样", fake_embedding,
        top_k=6, threshold=0.1, candidate_k=20, stats=stats,
    )
    assert hits == []
    assert stats["ready_docs"] == 1
    assert stats["empty"] is True


def test_behavior_unchanged_without_stats(db, fake_embedding):
    """不传 stats 时行为完全不变（向后兼容契约）。"""
    _seed(db, fake_embedding, "退货政策是什么？支持7天无理由退货。")
    with_stats: dict = {}
    hits_with = retriever.retrieve(
        db, "退货政策是什么", fake_embedding,
        top_k=6, threshold=0.1, candidate_k=20, stats=with_stats,
    )
    hits_without = retriever.retrieve(
        db, "退货政策是什么", fake_embedding,
        top_k=6, threshold=0.1, candidate_k=20,
    )
    assert [h["chunk_id"] for h in hits_with] == [h["chunk_id"] for h in hits_without]
    assert with_stats["ready_docs"] == 1

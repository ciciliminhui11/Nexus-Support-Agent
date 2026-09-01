"""混合检索 retriever 单元测试：向量路 + BM25 路 + RRF 融合 + Reranker 精排。

用真实 Ephemeral Chroma + 伪 embedding（conftest），验证双路召回、
阈值过滤、空检索兜底、重排与降级。相似度阈值放宽到 0.1 仅为验证链路
（伪 embedding 的校准问题所致）。
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


def _disable_bm25(monkeypatch):
    monkeypatch.setattr(bm25, "JIEBA_AVAILABLE", False)


def test_vector_only_hit_when_bm25_disabled(db, fake_embedding, monkeypatch):
    _seed(db, fake_embedding, "退货政策是什么？支持7天无理由退货。")
    _disable_bm25(monkeypatch)

    hits = retriever.retrieve(
        db, "退货政策是什么", fake_embedding, top_k=6, threshold=0.1, candidate_k=20
    )
    assert len(hits) == 1
    assert hits[0]["distance"] is not None
    assert hits[0]["score"] is not None and hits[0]["score"] > 0
    assert hits[0]["doc_name"] == "FAQ.md"


def test_bm25_only_keyword_hit_when_vector_empty(db, fake_embedding, monkeypatch):
    _seed(db, fake_embedding, "退货政策：支持七天无理由退货。")
    # 向量路清空：模拟相似度全部低于阈值（仅 BM25 命中）
    monkeypatch.setattr(
        chroma, "query",
        lambda *a, **k: {"ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]},
    )

    hits = retriever.retrieve(
        db, "退货政策如何办理", fake_embedding, top_k=6, threshold=0.1, candidate_k=20
    )
    assert len(hits) == 1
    assert hits[0]["distance"] is None  # BM25 独有命中
    assert hits[0]["score"] is not None
    assert hits[0]["bm25_score"] is not None


def test_threshold_filter_returns_empty(db, fake_embedding, monkeypatch):
    _seed(db, fake_embedding, "退货政策是什么？支持7天无理由退货。")
    _disable_bm25(monkeypatch)

    hits = retriever.retrieve(
        db, "今天的天气怎么样", fake_embedding, top_k=6, threshold=0.1, candidate_k=20
    )
    assert hits == []


def test_empty_corpus_returns_empty(db, fake_embedding):
    # 无任何文档
    assert retriever.retrieve(db, "退货政策", fake_embedding, top_k=6, threshold=0.1) == []
    # 只有「处理中」文档（未就绪，不参与检索）
    _seed(db, fake_embedding, "退货政策是什么", status="处理中")
    assert retriever.retrieve(db, "退货政策", fake_embedding, top_k=6, threshold=0.1) == []


def test_rrf_union_ranks_shared_first(db, fake_embedding):
    _seed(db, fake_embedding, "退货政策 支持七天无理由退货", doc_name="FAQ.md")
    _seed(db, fake_embedding, "配送退货 偏远地区除外", doc_name="配送.md")

    hits = retriever.retrieve(
        db, "退货政策", fake_embedding, top_k=6, threshold=0.1, candidate_k=20
    )
    # 双路并集：FAQ 两路皆中排前，配送仅 BM25 命中
    assert [h["doc_name"] for h in hits] == ["FAQ.md", "配送.md"]


class _PromoteDeliveryReranker:
    """假精排器：把含「配送」的片段打到最前。"""

    def rerank(self, query, texts):
        return [1.0 if "配送" in t else 0.0 for t in texts]


def test_fake_reranker_reorders_results(db, fake_embedding, monkeypatch):
    _seed(db, fake_embedding, "退货政策 支持七天无理由退货", doc_name="FAQ.md")
    _seed(db, fake_embedding, "配送退货 偏远地区除外", doc_name="配送.md")
    monkeypatch.setattr(retriever, "get_reranker", lambda: _PromoteDeliveryReranker())

    hits = retriever.retrieve(
        db, "退货政策", fake_embedding, top_k=6, threshold=0.1, candidate_k=20
    )
    assert len(hits) == 2
    assert hits[0]["doc_name"] == "配送.md"  # 精排覆盖融合序


def test_rerank_failure_falls_back_to_fused(db, fake_embedding, monkeypatch):
    _seed(db, fake_embedding, "退货政策 支持七天无理由退货", doc_name="FAQ.md")
    _seed(db, fake_embedding, "配送退货 偏远地区除外", doc_name="配送.md")

    def raising_rr(query, texts):
        raise RuntimeError("模型不可用")

    monkeypatch.setattr(
        retriever, "get_reranker", lambda: type("X", (), {"rerank": raising_rr})()
    )
    hits_bad = retriever.retrieve(
        db, "退货政策", fake_embedding, top_k=6, threshold=0.1, candidate_k=20
    )
    monkeypatch.setattr(retriever, "get_reranker", lambda: NoopReranker())
    hits_noop = retriever.retrieve(
        db, "退货政策", fake_embedding, top_k=6, threshold=0.1, candidate_k=20
    )
    assert len(hits_bad) == 2  # 不崩溃
    assert [h["chunk_id"] for h in hits_bad] == [h["chunk_id"] for h in hits_noop]

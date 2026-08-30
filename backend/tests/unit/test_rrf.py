"""RRF（Reciprocal Rank Fusion）融合排序单元测试。"""
from __future__ import annotations

import pytest

from app.services.rag.retriever import _rrf_fuse


def test_rrf_fuse_shared_docs_first():
    # A 仅向量路 rank1；B 两路皆中；C 仅 BM25 rank2
    fused = _rrf_fuse({"A": 1, "B": 2}, {"B": 1, "C": 2}, k=60)
    assert [cid for cid, _ in fused] == ["B", "A", "C"]
    # B 得两项（1/62 + 1/61），A 仅一项（1/61）→ B 高于 A 的差值为 1/62
    assert fused[0][1] - fused[1][1] == pytest.approx(1 / 62)


def test_rrf_fuse_single_list_preserves_order():
    fused = _rrf_fuse({"A": 1, "B": 2}, {}, k=60)
    assert [cid for cid, _ in fused] == ["A", "B"]


def test_rrf_fuse_empty():
    assert _rrf_fuse({}, {}, k=60) == []


def test_rrf_fuse_score_magnitude():
    fused = _rrf_fuse({"A": 1}, {"A": 2}, k=60)
    assert abs(fused[0][1] - (1 / 61 + 1 / 62)) < 1e-9

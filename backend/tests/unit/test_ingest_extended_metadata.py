"""002 增强元数据/标题注入单测（T013）：写入 Chroma 的文本与元数据核对。"""
from __future__ import annotations

from datetime import datetime

from app.services.knowledge.ingester import ingest_chunks
from app.services.knowledge.splitter import Chunk
from app.vector_store import chroma


def test_ingest_writes_heading_injected_text_and_meta(fake_embedding):
    chunks = [
        Chunk(text="退货政策说明", section="退换货", heading_path="常见问题 > 退换货")
    ]
    n = ingest_chunks(
        1,
        chunks,
        fake_embedding,
        batch_size=16,
        source_file="faq.md",
        category="售后",
        version_date=datetime(2026, 8, 1),
        source_priority=3,
    )
    assert n == 1
    data = chroma.get_collection().get(ids=["1-0"], include=["documents", "metadatas"])
    # 标题注入：父标题/章节标题拼接到文本开头（T013）
    assert data["documents"][0] == "常见问题 > 退换货：退货政策说明"
    meta = data["metadatas"][0]
    assert meta["doc_id"] == 1
    assert meta["chunk_index"] == 0
    assert meta["snippet"]
    assert meta["source_file"] == "faq.md"
    assert meta["section"] == "退换货"
    assert meta["heading_path"] == "常见问题 > 退换货"
    assert meta["category"] == "售后"
    assert meta["version_date"] == "2026-08-01T00:00:00"
    assert meta["source_priority"] == 3


def test_ingest_plain_chunk_backward_compatible(fake_embedding):
    """无章节信息的切片：不加标题注入，扩展元数据缺省即可，不破坏 001 检索。"""
    chunks = [Chunk(text="没有标题的正文")]
    n = ingest_chunks(2, chunks, fake_embedding, batch_size=16)
    assert n == 1
    data = chroma.get_collection().get(ids=["2-0"], include=["documents", "metadatas"])
    assert data["documents"][0] == "没有标题的正文"
    meta = data["metadatas"][0]
    assert meta["doc_id"] == 2
    assert meta["chunk_index"] == 0
    assert "heading_path" not in meta
    assert "section" not in meta
    assert meta["source_priority"] == 0

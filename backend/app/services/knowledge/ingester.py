"""向量化 + 写入 Chroma。

每个切片写入增强元数据（T013）：`doc_id / chunk_index / snippet / source_file /
section / heading_path / category / version_date / source_priority`；
向量化前把章节标题拼接到文本开头（标题注入），让标题语义参与检索。
"""
from __future__ import annotations

import math
from datetime import datetime

from app.services.embedding import EmbeddingClient, embed_texts
from app.services.knowledge.splitter import Chunk, make_snippet
from app.vector_store import chroma


def _inject_heading(chunk: Chunk) -> str:
    """标题注入：把父标题/章节标题拼接到切片文本开头（T013）。"""
    path = chunk.heading_path or chunk.section
    if path:
        return f"{path}：{chunk.text}"
    return chunk.text


def build_records(
    chunks: list[Chunk],
    embeddings: list[list[float]],
    *,
    source_file: str | None = None,
    category: str | None = None,
    version_date: datetime | None = None,
    source_priority: int = 0,
) -> list[dict]:
    records: list[dict] = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        text = _inject_heading(chunk)
        record: dict = {
            "chunk_index": i,
            "text": text,
            "snippet": make_snippet(text),
            "embedding": emb,
            "section": chunk.section,
            "heading_path": chunk.heading_path,
        }
        if source_file is not None:
            record["source_file"] = source_file
        if category is not None:
            record["category"] = category
        if version_date is not None:
            record["version_date"] = version_date.isoformat()
        record["source_priority"] = source_priority
        records.append(record)
    return records


def ingest_chunks(
    doc_id: int,
    chunks: list[Chunk],
    client: EmbeddingClient,
    batch_size: int = 16,
    *,
    source_file: str | None = None,
    category: str | None = None,
    version_date: datetime | None = None,
    source_priority: int = 0,
    stats: dict | None = None,
) -> int:
    """向量化 + 写入 Chroma（标题注入 + 扩展元数据）。返回切片数。

    `stats` 可选就地填充（008 埋点用，FR-001）：batches / dim / vectors，dim
    取实际 embedding 维度；不传则行为完全不变。
    """
    if not chunks:
        return 0
    effective_texts = [_inject_heading(c) for c in chunks]
    embeddings = embed_texts(client, effective_texts, batch_size)
    records = build_records(
        chunks,
        embeddings,
        source_file=source_file,
        category=category,
        version_date=version_date,
        source_priority=source_priority,
    )
    chroma.add_chunks(doc_id, records)
    if stats is not None:
        stats["vectors"] = len(records)
        stats["batches"] = math.ceil(len(chunks) / max(batch_size, 1))
        stats["dim"] = len(embeddings[0]) if embeddings else None
    return len(records)

"""向量化 + 写入 Chroma（含 metadata doc_id / chunk_index / snippet）。"""
from __future__ import annotations

from app.services.embedding import EmbeddingClient, embed_texts
from app.services.knowledge.splitter import make_snippet
from app.vector_store import chroma


def build_records(chunks: list[str], embeddings: list[list[float]]) -> list[dict]:
    return [
        {
            "chunk_index": i,
            "text": text,
            "snippet": make_snippet(text),
            "embedding": emb,
        }
        for i, (text, emb) in enumerate(zip(chunks, embeddings))
    ]


def ingest_chunks(
    doc_id: int,
    chunks: list[str],
    client: EmbeddingClient,
    batch_size: int = 16,
) -> int:
    embeddings = embed_texts(client, chunks, batch_size)
    records = build_records(chunks, embeddings)
    chroma.add_chunks(doc_id, records)
    return len(records)

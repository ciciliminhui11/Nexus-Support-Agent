"""Chroma 向量库封装。

统一收敛 Chroma 细节（collection 管理 / add / delete / query），
供 002 知识库写入、001 RAG 检索共用；便于后续切换生产向量库（Qdrant/Milvus）。

切片 ID 确定性生成：`{doc_id}-{chunk_index}`；
元数据：doc_id（关联 MySQL knowledge_doc.id）、chunk_index、snippet（来源摘要）。
"""
from __future__ import annotations

import chromadb

from app.config import settings

_COLLECTION_NAME = "knowledge_chunks"
_collection = None  # 进程内单例；测试可置 None 重建

# 类型定义：Chroma query 返回结构
QueryResult = dict


def get_collection():
    global _collection
    if _collection is not None:
        return _collection
    if settings.chroma_dir:
        client = chromadb.PersistentClient(path=settings.chroma_dir)
    else:
        client = chromadb.EphemeralClient()
    _collection = client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def reset_collection() -> None:
    """重建单例（测试隔离用）。

    注意：同进程内 `EphemeralClient()` 共享同一份底层数据，仅置 None 并不会
    真正清空 —— 新客户端会重新打开旧数据。必须先清空当前集合，再置 None。
    """
    global _collection
    if _collection is not None:
        try:
            all_ids = _collection.get(limit=10_000_000)["ids"]
            if all_ids:
                _collection.delete(ids=all_ids)
        except Exception:  # noqa: BLE001  空库或类型异常忽略
            pass
    _collection = None


def add_chunks(doc_id: int, records: list[dict]) -> None:
    """records: [{"chunk_index", "text", "snippet", "embedding"}, ...]"""
    if not records:
        return
    get_collection().add(
        ids=[f"{doc_id}-{r['chunk_index']}" for r in records],
        embeddings=[r["embedding"] for r in records],
        documents=[r["text"] for r in records],
        metadatas=[
            {
                "doc_id": doc_id,
                "chunk_index": r["chunk_index"],
                "snippet": r["snippet"],
            }
            for r in records
        ],
    )


def delete_by_doc_id(doc_id: int) -> None:
    try:
        get_collection().delete(where={"doc_id": doc_id})
    except Exception:
        # 无匹配元数据时 Chroma 可能抛空 where 错误，忽略即可
        pass


def clear_all() -> None:
    try:
        get_collection().delete(where={})
    except Exception:
        pass


def query(
    embedding: list[float],
    n_results: int,
    doc_ids: list[int] | None = None,
) -> QueryResult:
    """按向量检索；`doc_ids` 非空时仅在指定文档切片内召回（001 用就绪文档集合）。"""
    where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
    return get_collection().query(
        query_embeddings=[embedding],
        n_results=n_results,
        where=where,
    )


def get_all_documents(doc_ids: list[int] | None = None) -> QueryResult:
    """读取切片全文（BM25 语料），返回 Chroma GetResult（ids/documents/metadatas 对齐）。

    混合检索（001）用 BM25 路在就绪文档切片上建索引打分；语料全量拉取，
    适合笔试 demo 规模，生产可切换持久化索引（ES / 独立 BM25 库）。
    """
    where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
    return get_collection().get(where=where, include=["documents", "metadatas"])

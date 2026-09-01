"""混合检索：Query 向量化 → 向量粗筛 + BM25 召回 → RRF 融合 → Reranker 精排 → top-k。

research §1/§3：两路召回（Chroma 余弦 + jieba/BM25）经 RRF 融合成粗筛候选池
（`rag_candidate_k`，默认 20），再用 CrossEncoder Reranker 精排取最终 `rag_top_k`
送入 LLM；Reranker 缺失/失败回退融合序。无就绪文档或两路皆空 → 空列表（走兜底，
FR-005）。只召回「就绪」文档的切片。

返回结构保持兼容：chunk_id / doc_id / doc_name / snippet / text，另附
`distance`（向量余弦距离，BM25 独有命中为 None）与 `score`（RRF 融合分）。
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import KnowledgeDoc
from app.services.config_service import get_config_value
from app.services.embedding import EmbeddingClient, embed_texts
from app.services.rag import bm25
from app.services.rag.reranker import NoopReranker, get_reranker
from app.vector_store import chroma

logger = logging.getLogger(__name__)


def _ready_doc_ids(db: Session) -> list[int]:
    ids = db.scalars(
        select(KnowledgeDoc.id).where(KnowledgeDoc.status == "就绪")
    ).all()
    return [int(i) for i in ids]


def _doc_names(db: Session, doc_ids: list[int]) -> dict[int, str]:
    if not doc_ids:
        return {}
    rows = db.execute(
        select(KnowledgeDoc.id, KnowledgeDoc.doc_name).where(
            KnowledgeDoc.id.in_(doc_ids)
        )
    ).all()
    return {int(r[0]): r[1] for r in rows}


def _rrf_fuse(
    vector_rank: dict[str, int], bm25_rank: dict[str, int], k: int
) -> list[tuple[str, float]]:
    """RRF（Reciprocal Rank Fusion）：RRF(doc) = Σ 1/(k + rank)，按分降序。

    rank 为 1-based 位置；两路都命中的 doc 得两项 → 排在单路命中之前。
    仅出现在一路中的 doc 也保留（召回率优先，交由 Reranker 精排取舍）。
    """
    scores: dict[str, float] = {}
    for cid, rank in vector_rank.items():
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    for cid, rank in bm25_rank.items():
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def retrieve(
    db: Session,
    question: str,
    client: EmbeddingClient,
    top_k: int | None = None,
    threshold: float | None = None,
    candidate_k: int | None = None,
    stats: dict | None = None,
) -> list[dict]:
    """混合检索命中片段；无就绪文档或两路皆空时返回空列表（走兜底）。

    `stats` 为可选就地填充的召回统计 dict（008 埋点用，FR-007）：ready_docs /
    vector_before_threshold / vector_after_threshold / bm25_available / bm25_hits /
    candidate_pool / reranker(enabled|noop|failed) / empty；不传则行为完全不变。
    """
    top_k = top_k or int(settings.rag_top_k)
    threshold = threshold if threshold is not None else settings.rag_similarity_threshold
    candidate_k = candidate_k or int(settings.rag_candidate_k)
    # 检索参数走 system_config 热调（未配置回落 Settings 默认）
    bm25_top_k = int(get_config_value(db, "rag_bm25_top_k", settings.rag_bm25_top_k))
    rrf_k = int(get_config_value(db, "rag_rrf_k", settings.rag_rrf_k))

    ready_ids = _ready_doc_ids(db)
    if stats is not None:
        stats["ready_docs"] = len(ready_ids)
    if not ready_ids:
        if stats is not None:
            stats["empty"] = True
        return []
    names = _doc_names(db, ready_ids)

    # ---------- 向量路：粗筛 candidate_k → 阈值过滤 ----------
    query_vec = embed_texts(client, [question])[0]
    vres = chroma.query(query_vec, n_results=candidate_k, doc_ids=ready_ids)
    vector_hits: list[dict] = []
    ids = vres.get("ids")[0] if vres.get("ids") else []
    if stats is not None:
        stats["vector_before_threshold"] = len(ids)
    for i, chunk_id in enumerate(ids):
        # Chroma cosine 距离 = 1 - 余弦相似度；阈值是相似度，需换算
        if vres["distances"][0][i] > 1 - threshold:
            continue
        meta = vres["metadatas"][0][i]
        doc_id = int(meta.get("doc_id", 0))
        vector_hits.append(
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "doc_name": names.get(doc_id, "未知来源"),
                "snippet": meta.get("snippet", ""),
                "text": vres["documents"][0][i],
                "distance": vres["distances"][0][i],
                "score": None,
            }
        )
    if stats is not None:
        stats["vector_after_threshold"] = len(vector_hits)
    vector_rank = {h["chunk_id"]: pos for pos, h in enumerate(vector_hits, start=1)}

    # ---------- BM25 路：全量就绪切片建索引 → 显著词闸门 + 打分 → bm25_top_k ----------
    bm25_hits: list[dict] = []
    bm25_rank: dict[str, int] = {}
    if stats is not None:
        stats["bm25_available"] = bool(bm25.JIEBA_AVAILABLE)
    if bm25.JIEBA_AVAILABLE:
        corpus = chroma.get_all_documents(ready_ids)
        c_ids = corpus.get("ids") or []
        if c_ids:
            index = bm25.BM25Index.build(corpus["documents"])
            for idx, bscore in index.rank(question, top_k=bm25_top_k):
                cid = c_ids[idx]
                meta = corpus["metadatas"][idx]
                doc_id = int(meta.get("doc_id", 0))
                bm25_hits.append(
                    {
                        "chunk_id": cid,
                        "doc_id": doc_id,
                        "doc_name": names.get(doc_id, "未知来源"),
                        "snippet": meta.get("snippet", ""),
                        "text": corpus["documents"][idx],
                        "distance": None,
                        "score": None,
                        "bm25_score": round(bscore, 6),
                    }
                )
        bm25_rank = {h["chunk_id"]: pos for pos, h in enumerate(bm25_hits, start=1)}
    if stats is not None:
        stats["bm25_hits"] = len(bm25_hits)

    # ---------- RRF 融合 → 候选池（两路皆空 → 空列表兜底） ----------
    if not vector_rank and not bm25_rank:
        if stats is not None:
            stats["empty"] = True
        return []
    by_id: dict[str, dict] = {}
    for h in vector_hits:
        by_id.setdefault(h["chunk_id"], h)  # 优先向量命中（保留 distance）
    for h in bm25_hits:
        if h["chunk_id"] in by_id:
            by_id[h["chunk_id"]]["bm25_score"] = h.get("bm25_score")
        else:
            by_id[h["chunk_id"]] = h
    fused = _rrf_fuse(vector_rank, bm25_rank, rrf_k)
    rrf_score = dict(fused)
    candidates = [by_id[cid] for cid, _ in fused if cid in by_id][:candidate_k]
    if not candidates:
        if stats is not None:
            stats["empty"] = True
        return []

    # ---------- Reranker 精排 → 最终 top_k ----------
    reranker = get_reranker()
    if isinstance(reranker, NoopReranker):
        ordered = candidates
        if stats is not None:
            stats["reranker"] = "noop"
    else:
        try:
            scores = reranker.rerank(question, [c["text"] for c in candidates])
            ordered = [
                c for c, _ in sorted(
                    zip(candidates, scores), key=lambda x: x[1], reverse=True
                )
            ]
            if stats is not None:
                stats["reranker"] = "enabled"
        except Exception as exc:  # noqa: BLE001  模型加载/推理失败 → 回落融合序
            logger.warning("Reranker 精排失败，回落 RRF 融合序：%s", exc)
            ordered = candidates
            if stats is not None:
                stats["reranker"] = "failed"
    if stats is not None:
        stats["candidate_pool"] = len(candidates)
    final = ordered[:top_k]
    for c in final:
        c["score"] = round(rrf_score.get(c["chunk_id"], 0.0), 6)
    return final

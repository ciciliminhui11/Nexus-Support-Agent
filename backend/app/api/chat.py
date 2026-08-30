"""RAG 流式问答端点：POST /api/chat/stream（SSE）。

编排链路：鉴权 → 长度/配额校验 → 会话归属校验 → 最近 N 轮历史 →
向量检索（无命中走兜底）→ Prompt 组装 → LLM 流式 → SSE 事件序列 →
消息持久化 → 输出后来源校验。

注意：StreamingResponse 的 body 生成器在端点返回后才执行，此时请求级
`db` 会话已关闭，持久化在生成器内自开 `SessionLocal()`（与 002 pipeline 同理）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.exceptions import ForbiddenError
from app.db.models import ChatSession, Message, User
from app.db.session import SessionLocal, get_db
from app.schemas.chat import ChatRequest
from app.services.config_service import get_config_value
from app.services.embedding import get_embedding_client
from app.services.history import get_recent_turns
from app.services.rag import llm as llm_service
from app.services.rag import postcheck as postcheck_service
from app.services.rag import prompt as prompt_service
from app.services.rag import retriever, sse
from app.services.session.session_crud import (
    get_session_for_user,
    update_title_if_default,
)
from app.services.validation import consume_quota, validate_question

router = APIRouter(prefix="/api/chat", tags=["chat"])

LLM_ERROR_TEXT = {
    "llm_timeout": "回答生成超时，请稍后重试",
    "llm_rate_limited": "服务繁忙，请稍后再试",
    "llm_error": "AI 服务暂时不可用，请稍后再试",
}


def _dedupe_sources(chunks: list[dict]) -> list[dict]:
    """来源去重（按 doc_name+snippet），保持召回顺序。"""
    seen: set[tuple[str, str]] = set()
    sources: list[dict] = []
    for c in chunks:
        key = (c["doc_name"], c["snippet"])
        if key not in seen:
            seen.add(key)
            sources.append({"doc_name": c["doc_name"], "snippet": c["snippet"]})
    return sources


@router.post("/stream")
def chat_stream(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    # ---------- 前置校验（非流式，直接 HTTP 错误） ----------
    validate_question(req.question)
    if get_session_for_user(db, req.session_id, user.id) is None:
        raise ForbiddenError(code="session_forbidden", message="无权访问该会话")

    limit = int(get_config_value(db, "daily_quota_limit", settings.daily_quota_limit))
    consume_quota(db, user.id, limit)  # 校验 + 原子递增，达上限抛 429

    context_turns = int(get_config_value(db, "context_turns", settings.context_turns))
    history = get_recent_turns(db, req.session_id, context_turns)

    client = get_embedding_client()
    top_k = int(get_config_value(db, "rag_top_k", settings.rag_top_k))
    threshold = float(
        get_config_value(db, "rag_similarity_threshold", settings.rag_similarity_threshold)
    )
    candidate_k = int(get_config_value(db, "rag_candidate_k", settings.rag_candidate_k))
    # 混合检索：向量(阈值) + BM25(闸门) → RRF 融合 → Reranker 精排 → top_k
    chunks = retriever.retrieve(db, req.question, client, top_k, threshold, candidate_k)
    sources = _dedupe_sources(chunks)
    max_tokens = int(get_config_value(db, "context_max_tokens", settings.context_max_tokens))

    async def event_stream():
        own = SessionLocal()
        try:
            # 持久化用户提问（FR-012）
            user_msg = Message(session_id=req.session_id, role="user", content=req.question)
            own.add(user_msg)
            own.commit()
            own.refresh(user_msg)
            # 首条消息后自动生成会话标题（004 特性）
            if user_msg.id is not None:
                sess = own.get(ChatSession, req.session_id)
                if sess is not None:
                    update_title_if_default(own, sess, req.question)

            # ---------- 空检索兜底（FR-005）：不调用 LLM ----------
            if not chunks:
                fallback = Message(
                    session_id=req.session_id,
                    role="ai",
                    content=sse.FALLBACK_TEXT,
                    reference_source=[],
                )
                own.add(fallback)
                own.commit()
                own.refresh(fallback)
                yield sse.sse_data(sse.FALLBACK_TEXT)
                yield sse.sse_finish(fallback.id, {"status": "ok"})
                return

            # ---------- 有命中：meta → data* → finish ----------
            yield sse.sse_meta(sources)
            messages = prompt_service.build_messages(req.question, history, chunks, max_tokens)

            full = ""
            error_code: str | None = None
            try:
                async for delta in llm_service.stream_chat(messages):
                    full += delta
                    yield sse.sse_data(delta)
            except llm_service.LLMTimeoutError:
                error_code = "llm_timeout"
            except llm_service.LLMRateLimitError:
                error_code = "llm_rate_limited"
            except llm_service.LLMConnectionError:
                error_code = "llm_error"

            if error_code is not None:
                text = LLM_ERROR_TEXT[error_code]
                own.add(Message(session_id=req.session_id, role="ai", content=text, reference_source=sources))
                own.commit()
                yield sse.sse_error(error_code, text)
                return

            if not full:
                text = LLM_ERROR_TEXT["llm_error"]
                own.add(Message(session_id=req.session_id, role="ai", content=text, reference_source=sources))
                own.commit()
                yield sse.sse_error("llm_error", "AI 服务返回内容为空，请稍后再试")
                return

            ai_msg = Message(
                session_id=req.session_id,
                role="ai",
                content=full,
                reference_source=sources,
            )
            own.add(ai_msg)
            own.commit()
            own.refresh(ai_msg)
            yield sse.sse_finish(ai_msg.id, postcheck_service.postcheck(full, chunks))
        except Exception:
            own.rollback()
            yield sse.sse_error("llm_error", LLM_ERROR_TEXT["llm_error"])
        finally:
            own.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

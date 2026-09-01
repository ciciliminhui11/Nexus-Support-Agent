"""RAG 流式问答端点：POST /api/chat/stream（SSE）。

编排链路：鉴权 → 长度/配额校验 → 会话归属校验 → 最近 N 轮历史 →
意图识别（三层漏斗，短路分支）→ 向量检索（无命中走兜底）→ Prompt 组装 →
LLM 流式 → SSE 事件序列 → 消息持久化 → 输出后来源校验。

注意：StreamingResponse 的 body 生成器在端点返回后才执行，此时请求级
`db` 会话已关闭，持久化在生成器内自开 `SessionLocal()`（与 002 pipeline 同理）。

008 埋点（FR-002）：整条 chat 链路各阶段 span（preflight/intent/retrieve/
persist_user/short_circuit/empty_retrieval/prompt/llm_stream/postcheck/finish），
trace_enabled=false 时 Tracer 全程短路，零开销（FR-010）。
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.exceptions import ForbiddenError
from app.db.models import ChatSession, Message, User
from app.db.session import SessionLocal, get_db
from app.intent.router import route_intent
from app.intent.schema import HandlerKey, INTENT_LABEL_CN
from app.intent.service import recognize_with_trace
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
from app.services.tracing.events import (
    ERROR_MAX_CHARS,
    MATCHED_PATTERNS_MAX,
    STAGE_CHAT_FINISH,
    STAGE_EMPTY_RETRIEVAL,
    STAGE_INTENT,
    STAGE_LLM_STREAM,
    STAGE_PERSIST_USER,
    STAGE_POSTCHECK,
    STAGE_PREFLIGHT,
    STAGE_PROMPT,
    STAGE_RETRIEVE,
    STAGE_SHORT_CIRCUIT,
    STATUS_ERROR,
    STATUS_OK,
    TRACE_TYPE_CHAT,
    truncate_list,
)
from app.services.tracing.tracer import Tracer
from app.services.auth.quota import _get_user_limit
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
    tracer = Tracer(
        TRACE_TYPE_CHAT,
        session_id=req.session_id,
        user_id=user.id,
        question=req.question,
    )
    sources: list[dict] = []
    try:
        # ---------- 前置校验（非流式，直接 HTTP 错误） ----------
        with tracer.span(STAGE_PREFLIGHT):
            validate_question(req.question)
            if get_session_for_user(db, req.session_id, user.id) is None:
                raise ForbiddenError(code="session_forbidden", message="无权访问该会话")
            limit = _get_user_limit(db, user.id)
            consume_quota(db, user.id, limit)  # 校验 + 原子递增，达上限抛 429
            context_turns = int(get_config_value(db, "context_turns", settings.context_turns))
            history = get_recent_turns(db, req.session_id, context_turns)

        # ---------- 006 意图识别（三层漏斗，永不抛异常） ----------
        with tracer.span(STAGE_INTENT) as detail:
            intent, intent_trace = recognize_with_trace(db, req.question)
            handler = route_intent(intent)
            detail["layer"] = intent.source_layer.value
            detail["intent"] = intent.intent.value
            detail["confidence"] = round(intent.confidence, 4)
            if intent.matched_patterns:
                detail["matched_patterns"] = truncate_list(
                    intent.matched_patterns, MATCHED_PATTERNS_MAX
                )
            if intent.clarification_question:
                detail["clarification_question"] = intent.clarification_question
            if intent_trace.error:
                detail["error"] = intent_trace.error

        # 意图短路（闲聊/投诉/澄清）不检索不调用 LLM（FR-002/FR-012），
        # 检索仅在走 rag_qa 时才执行。
        if handler in (HandlerKey.small_talk, HandlerKey.complaint, HandlerKey.clarify):
            chunks: list[dict] = []
            sources = []
        else:
            client = get_embedding_client()
            top_k = int(get_config_value(db, "rag_top_k", settings.rag_top_k))
            threshold = float(
                get_config_value(db, "rag_similarity_threshold", settings.rag_similarity_threshold)
            )
            candidate_k = int(get_config_value(db, "rag_candidate_k", settings.rag_candidate_k))
            # ---------- 混合检索（向量阈值 + BM25 闸门 → RRF → Reranker） ----------
            stats: dict = {}
            with tracer.span(STAGE_RETRIEVE) as detail:
                chunks = retriever.retrieve(
                    db, req.question, client, top_k, threshold, candidate_k, stats=stats
                )
                detail.update(stats)
                if chunks:
                    sources = _dedupe_sources(chunks)
                    detail["sources"] = truncate_list(sources, top_k)
        max_tokens = int(get_config_value(db, "context_max_tokens", settings.context_max_tokens))
    except Exception as exc:  # noqa: BLE001  前置段失败 → HTTP 错误照抛，trace 标 error 收尾
        tracer.finish(status=STATUS_ERROR, error=f"preflight: {str(exc)[:ERROR_MAX_CHARS]}")
        raise

    async def event_stream():
        own = SessionLocal()
        try:
            # ---------- 持久化用户提问（FR-012），写入 006 意图标签（FR-011） ----------
            with tracer.span(STAGE_PERSIST_USER):
                user_msg = Message(session_id=req.session_id, role="user", content=req.question)
                user_msg.intent_label = INTENT_LABEL_CN[intent.intent]
                own.add(user_msg)
                own.commit()
                own.refresh(user_msg)
                # 首条消息后自动生成会话标题（004 特性）
                if user_msg.id is not None:
                    sess = own.get(ChatSession, req.session_id)
                    if sess is not None:
                        update_title_if_default(own, sess, req.question)

            # ---------- 006 意图短路（FR-012/SC-007）：闲聊/投诉/澄清不检索 ----------
            if handler in (HandlerKey.small_talk, HandlerKey.complaint, HandlerKey.clarify):
                with tracer.span(STAGE_SHORT_CIRCUIT) as detail:
                    detail["handler"] = handler.value
                    detail["intent"] = intent.intent.value
                    if handler is HandlerKey.small_talk:
                        text = settings.intent_small_talk_reply
                    elif handler is HandlerKey.complaint:
                        text = settings.intent_complaint_reply
                    else:  # clarify
                        text = intent.clarification_question or settings.intent_small_talk_reply
                    ai_msg = Message(
                        session_id=req.session_id,
                        role="ai",
                        content=text,
                        reference_source=[],
                    )
                    own.add(ai_msg)
                    own.commit()
                    own.refresh(ai_msg)
                    yield sse.sse_data(text)
                    yield sse.sse_finish(ai_msg.id, {"status": "ok"})
                with tracer.span(STAGE_CHAT_FINISH) as detail:
                    detail["status"] = "ok"
                    detail["handler"] = handler.value
                tracer.finish(status=STATUS_OK)
                return

            # ---------- 空检索兜底（FR-005）：不调用 LLM ----------
            if not chunks:
                with tracer.span(STAGE_EMPTY_RETRIEVAL):
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
                with tracer.span(STAGE_CHAT_FINISH) as detail:
                    detail["status"] = "ok"
                    detail["fallback"] = True
                tracer.finish(status=STATUS_OK)
                return

            # ---------- 有命中：meta → data* → finish ----------
            yield sse.sse_meta(sources)
            with tracer.span(STAGE_PROMPT) as detail:
                messages = prompt_service.build_messages(req.question, history, chunks, max_tokens)
                detail["messages"] = len(messages)
                detail["context_chars"] = sum(
                    len(m["content"]) for m in messages if isinstance(m.get("content"), str)
                )

            full = ""
            error_code: str | None = None
            llm_start = time.monotonic()
            with tracer.span(STAGE_LLM_STREAM) as detail:
                try:
                    async for delta in llm_service.stream_chat(messages):
                        if full == "" and delta:  # 首个 delta 到达 = 首 token
                            detail["first_token_ms"] = int(
                                (time.monotonic() - llm_start) * 1000
                            )
                        full += delta
                        yield sse.sse_data(delta)
                except llm_service.LLMTimeoutError:
                    error_code = "llm_timeout"
                except llm_service.LLMRateLimitError:
                    error_code = "llm_rate_limited"
                except llm_service.LLMConnectionError:
                    error_code = "llm_error"
                detail["backend"] = settings.llm_backend
                detail["char_count"] = len(full)
                if error_code or not full:
                    # 业务内捕获 LLM 异常 / 流结束但空响应：都属 LLM 层失败，
                    # 显式把 span 标 error 并记录错误码（FR-008）
                    detail["error_code"] = error_code or "llm_error"
                    tracer.mark_span_error(STAGE_LLM_STREAM, error=error_code or "llm_error")

            if error_code is not None:
                text = LLM_ERROR_TEXT[error_code]
                own.add(Message(session_id=req.session_id, role="ai", content=text, reference_source=sources))
                own.commit()
                with tracer.span(STAGE_CHAT_FINISH) as detail:
                    detail["status"] = "error"
                    detail["error_code"] = error_code
                tracer.finish(status=STATUS_ERROR, error=error_code)
                yield sse.sse_error(error_code, text)
                return

            if not full:
                text = LLM_ERROR_TEXT["llm_error"]
                own.add(Message(session_id=req.session_id, role="ai", content=text, reference_source=sources))
                own.commit()
                with tracer.span(STAGE_CHAT_FINISH) as detail:
                    detail["status"] = "error"
                    detail["error_code"] = "llm_error"
                tracer.finish(status=STATUS_ERROR, error="empty_response")
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
            with tracer.span(STAGE_POSTCHECK) as detail:
                pc = postcheck_service.postcheck(full, chunks)
                detail["status"] = pc["status"]
            with tracer.span(STAGE_CHAT_FINISH) as detail:
                detail["status"] = "ok"
                detail["message_id"] = ai_msg.id
                detail["postcheck"] = pc["status"]
            tracer.finish(status=STATUS_OK)
            yield sse.sse_finish(ai_msg.id, pc)
        except Exception:
            own.rollback()
            if not tracer.is_finished():
                tracer.finish(status=STATUS_ERROR, error="unexpected_error")
            yield sse.sse_error("llm_error", LLM_ERROR_TEXT["llm_error"])
        finally:
            if not tracer.is_finished():
                # 兜底：客户端中断/异常路径未 finish 的 trace 标 error，避免丢失链路
                tracer.finish(status=STATUS_ERROR, error="stream_aborted")
            own.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

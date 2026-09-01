"""可读链路块渲染（控制台输出，FR-004）。

`render_trace_block` 为纯函数：输入 tracer 与按 seq 排好的 span 事件列表，
输出一份「阶段顺序 / 耗时 / 状态 / 关键指标」的可读文本块，经 `logger.info`
打印到后端 stdout。
"""
from __future__ import annotations

from typing import Any

from app.services.tracing.events import STAGE_META

# 控制台摘要优先展示的 detail 字段（与埋点明细保持一致，其余字段从 detail 全文查）
_SUMMARY_KEYS = (
    "layer",
    "intent",
    "confidence",
    "chars",
    "chunks",
    "semantic_split",
    "batches",
    "dim",
    "vectors",
    "ready_docs",
    "vector_before_threshold",
    "vector_after_threshold",
    "bm25_available",
    "bm25_hits",
    "candidate_pool",
    "reranker",
    "messages",
    "context_chars",
    "backend",
    "first_token_ms",
    "char_count",
    "error_code",
    "status",
    "handler",
    "message_id",
)


def _summary_of(detail: dict | None) -> str:
    """把 detail 关键字段拼成一行摘要（可读优先，不做完整 JSON 转储）。"""
    if not detail:
        return ""
    parts: list[str] = []
    for key in _SUMMARY_KEYS:
        if key in detail:
            parts.append(f"{key}={detail[key]}")
    return " ".join(parts)


def _format_sources(sources: Any) -> str:
    """sources 列表紧凑格式化：doc_name(score)。兼容 doc/doc_name 两种键。"""
    if not sources:
        return ""
    try:
        items = []
        for s in sources[:6]:  # 控制台仅预览前 6 条
            if isinstance(s, dict):
                name = s.get("doc_name") or s.get("doc") or "?"
                score = s.get("score")
                items.append(f"{name}({score})" if score is not None else name)
            else:
                items.append(str(s))
        return "[" + ", ".join(items) + "]"
    except (TypeError, AttributeError):
        return str(sources)[:200]


def render_trace_block(tracer: Any, events: list[dict]) -> str:
    """渲染完整链路块。`tracer` 提供 trace_id/类型/关联 id，`events` 按 seq 升序。"""
    lines: list[str] = []
    header = (
        f"┌─ [{tracer.trace_type}] trace_id={tracer.trace_id[:12]}… "
        f"doc_id={tracer.doc_id} session_id={tracer.session_id} user_id={tracer.user_id}"
    )
    lines.append(header)
    for ev in events:
        if ev.get("stage") == STAGE_META:
            continue
        dur = ev.get("duration_ms")
        dur_txt = f"{dur}ms" if dur is not None else "-"
        err = f"  error={ev['error']}" if ev.get("error") else ""
        line = f"├─ {ev['stage']:<18} {ev['status']:<6} {dur_txt:>8}{err}"
        summary = _summary_of(ev.get("detail"))
        if summary:
            line += f"  {summary}"
        lines.append(line)
        sources = (ev.get("detail") or {}).get("sources")
        if sources:
            lines.append(f"│   └ sources: {_format_sources(sources)}")
    lines.append("└─ end")
    return "\n".join(lines)

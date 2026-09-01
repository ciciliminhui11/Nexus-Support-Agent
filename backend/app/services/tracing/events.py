"""链路埋点事件定义：trace_type/stage/status 常量与 detail 体积护栏。

008 埋点的 detail 负载统一经本模块护栏（截断/封顶），保证单行 <4KB、
不存密钥与完整敏感内容（FR-009，见 specs/008-observability/research.md §6）。
"""
from __future__ import annotations

# ---------- trace_type ----------
TRACE_TYPE_INGEST = "ingest"
TRACE_TYPE_CHAT = "chat"

# ---------- status ----------
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

# ---------- stage：通用 ----------
STAGE_META = "meta"  # seq=0，携带 question/doc_name 上下文

# ---------- stage：ingest 链路（002） ----------
STAGE_DOC_LOAD = "doc_load"
STAGE_DOC_PARSE = "doc_parse"
STAGE_DOC_SPLIT = "doc_split"
STAGE_DOC_EMBED_INGEST = "doc_embed_ingest"
STAGE_DOC_ROLLBACK = "doc_rollback"
STAGE_DOC_STATUS = "doc_status"

# ---------- stage：chat 链路（001/006） ----------
STAGE_PREFLIGHT = "preflight"
STAGE_INTENT = "intent"
STAGE_RETRIEVE = "retrieve"
STAGE_PERSIST_USER = "persist_user"
STAGE_SHORT_CIRCUIT = "short_circuit"
STAGE_EMPTY_RETRIEVAL = "empty_retrieval"
STAGE_PROMPT = "prompt"
STAGE_LLM_STREAM = "llm_stream"
STAGE_POSTCHECK = "postcheck"
STAGE_CHAT_FINISH = "finish"

# ---------- detail 体积护栏（research §6） ----------
QUESTION_MAX_CHARS = 200  # question 截断
ERROR_MAX_CHARS = 200  # span 级错误消息截断
ERROR_DB_MAX_CHARS = 500  # trace_event.error 列上限
MATCHED_PATTERNS_MAX = 10  # 意图命中模式列表上限


def truncate_text(value: str | None, cap: int) -> str | None:
    """截断字符串到 cap 字符（None 原样返回）。"""
    if value is None:
        return None
    return value if len(value) <= cap else value[:cap]


def truncate_list(value: list | None, cap: int) -> list | None:
    """截断列表到 cap 个元素（None 原样返回）。"""
    if value is None:
        return None
    return value[:cap]

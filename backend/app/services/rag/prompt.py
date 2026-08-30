"""Prompt 组装与上下文预算截断（FR-006 / FR-011）。

Token 预算（research §6）：SystemPrompt + RAG 知识片段 + 对话历史 + 用户问题。
超限降级顺序：**先丢最早历史（按消息边界）→ 再减知识片段数量 → 严禁先丢知识**。
字符近似 token（~1.5 字符/token，保守值）。
"""
from __future__ import annotations

CHARS_PER_TOKEN = 1.5

SYSTEM_PROMPT = (
    "你是 AI 智能客服助手。回答必须严格依据下面编号的知识片段，"
    "禁止使用片段之外的任何信息编造内容。若片段不足以回答，"
    "请明确告知无法回答。回答应引用片段中提供的事实。"
)

CHUNK_TEMPLATE = "【{i}】来源：{doc_name}｜片段：{snippet}\n{text}"


def format_chunks(chunks: list[dict]) -> str:
    """带编号与来源元信息注入，如：【1】来源：FAQ.md｜片段：xxx\n正文。"""
    return "\n\n".join(
        CHUNK_TEMPLATE.format(
            i=i + 1, doc_name=c["doc_name"], snippet=c["snippet"], text=c["text"]
        )
        for i, c in enumerate(chunks)
    )


def _messages(system: str, history: list[dict], question: str) -> list[dict]:
    msgs = [{"role": "system", "content": system}]
    msgs.extend({"role": h["role"], "content": h["content"]} for h in history)
    msgs.append({"role": "user", "content": question})
    return msgs


def _estimate(chars: int) -> int:
    return int(chars / CHARS_PER_TOKEN)


def build_messages(
    question: str,
    history: list[dict],
    chunks: list[dict],
    max_tokens: int = 6000,
) -> list[dict]:
    """组装 messages；超预算时优先丢最早历史，再减知识片段。"""
    budget = int(max_tokens * CHARS_PER_TOKEN)
    hist = list(history)
    kept_chunks = list(chunks)

    # 知识优先：初始保留全部片段
    system = SYSTEM_PROMPT + "\n\n" + format_chunks(kept_chunks) if kept_chunks else SYSTEM_PROMPT
    used = _estimate(len(system) + sum(len(h["content"]) for h in hist) + len(question))

    # 降级①：丢最早历史（按消息边界，最多保留一条最晚历史）
    while hist and used > budget:
        removed = hist.pop(0)
        used -= _estimate(len(removed["content"]))

    # 降级②：仍超 → 从末尾减知识片段（保持编号连续）
    while kept_chunks and used > budget:
        dropped = kept_chunks.pop()
        used -= _estimate(len(dropped["text"]))
        system = (
            SYSTEM_PROMPT + "\n\n" + format_chunks(kept_chunks)
            if kept_chunks
            else SYSTEM_PROMPT
        )

    return _messages(system, hist, question)

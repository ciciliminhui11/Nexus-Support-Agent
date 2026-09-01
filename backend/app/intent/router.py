"""意图 → 处理 Handler 映射（FR-012）。

- product_consult / after_sale → rag_qa：走 001 RAG 问答链路
- small_talk → small_talk：模板回复，不检索知识库
- complaint → complaint：转人工客服提示，不检索知识库
- 中段置信度澄清（IntcResult.clarification_question 非空）→ clarify
- unknown → default：走 001 正常问答或兜底话术，不阻断主流程
"""
from __future__ import annotations

from .schema import HandlerKey, IntentCategory, IntentResult

_HANDLER_BY_INTENT: dict[IntentCategory, HandlerKey] = {
    IntentCategory.product_consult: HandlerKey.rag_qa,
    IntentCategory.after_sale: HandlerKey.rag_qa,
    IntentCategory.small_talk: HandlerKey.small_talk,
    IntentCategory.complaint: HandlerKey.complaint,
    IntentCategory.unknown: HandlerKey.default,
}


def route_intent(result: IntentResult) -> HandlerKey:
    """按识别结果路由到对应处理链路。"""
    if result.clarification_question:
        return HandlerKey.clarify
    return _HANDLER_BY_INTENT.get(result.intent, HandlerKey.default)

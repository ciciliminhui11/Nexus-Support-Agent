"""大模型兜底分类（FR-010）：Few-shot + 强制 JSON，任何失败返回 None。

模型名与 base_url 统一使用 `llm_model` / `llm_base_url`（与 001 对话 LLM 共用）。
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.core.logging import get_logger

from ..schema import IntentCategory
from ..small_model.client import _parse_intent_json, log_llm_usage, post_chat_completion
from .few_shot import FALLBACK_FEW_SHOT_EXAMPLES

logger = get_logger(__name__)

FALLBACK_SYSTEM_PROMPT = (
    "你是意图识别分类器。根据以下样例判断用户输入属于 "
    "product_consult/after_sale/small_talk/complaint/unknown 五类之一：\n"
    + "\n".join(
        f"用户：{ex['user']} → 意图：{ex['intent']}"
        for ex in FALLBACK_FEW_SHOT_EXAMPLES
    )
    + "\n只输出 JSON：{\"intent\": \"<意图枚举>\", \"confidence\": 0到1的小数}\n"
    "无法判断时输出 unknown。禁止自由文本闲聊。"
)


def classify_fallback(
    query: str, transport: httpx.BaseTransport | None = None
) -> tuple[IntentCategory, float] | None:
    """大模型兜底分类；任何异常/解析失败返回 None（调用方降级 unknown）。"""
    try:
        model = settings.llm_model
        messages = [
            {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        data = post_chat_completion(messages, model=model, transport=transport)
        log_llm_usage(data, "fallback", model)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _parse_intent_json(content)
    except Exception as exc:  # noqa: BLE001  兜底层失败不得外抛
        logger.debug("意图兜底分类失败（降级 unknown）: %s", exc)
        return None

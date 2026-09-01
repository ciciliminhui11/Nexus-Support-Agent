"""小模型层调用：OpenAI 兼容 /chat/completions 同步封装 + 意图分类。

- 空密钥短路不发 HTTP（抛 LLMConnectionError，由调用方决定降级）；
- 429 指数退避后抛 LLMRateLimitError；超时抛 LLMTimeoutError；
- 其余 HTTP/网络错误抛 LLMConnectionError；
- 每次成功调用把 usage 记入日志（各漏斗层成本占比，data-model §3 成本统计）。

复用 `app.services.rag.llm` 的异常类，与 001 链路错误语义一致。
"""
from __future__ import annotations

import json
import time

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.services.rag.llm import LLMConnectionError, LLMRateLimitError, LLMTimeoutError

from ..schema import IntentCategory, parse_intent_category

logger = get_logger(__name__)

SMALL_MODEL_SYSTEM_PROMPT = (
    "你是意图识别分类器。请判断用户输入属于以下四类意图之一：\n"
    "- product_consult 产品咨询：产品功能/使用方法/价格/参数等咨询\n"
    "- after_sale 售后：退换货、维修、售后政策等\n"
    "- small_talk 闲聊：打招呼/感谢/非业务话题\n"
    "- complaint 投诉：不满、投诉、要求转人工\n"
    "只输出 JSON：{\"intent\": \"<意图枚举>\", \"confidence\": 0到1的小数}\n"
    "禁止输出其它内容。"
)


def _parse_intent_json(content: str) -> tuple[IntentCategory, float] | None:
    """解析模型 JSON 输出 → (intent, confidence)；失败/越界/unknown 返回 None。"""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    intent = parse_intent_category(str(data.get("intent", "")).strip())
    if intent is None or intent is IntentCategory.unknown:
        return None
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if not 0.0 <= confidence <= 1.0:
        return None
    return intent, confidence


def log_llm_usage(data: dict, layer: str, model: str) -> None:
    """记录模型调用 usage（成本统计通道，data-model §3）。"""
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    logger.info(
        "intent_usage layer=%s model=%s prompt_tokens=%s completion_tokens=%s "
        "total_tokens=%s reasoning_tokens=%s",
        layer,
        model,
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        usage.get("total_tokens"),
        details.get("reasoning_tokens"),
    )


def post_chat_completion(
    messages: list[dict],
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """同步调用 /chat/completions（强制 JSON 输出），返回完整响应 JSON。

    凭据优先级：显式 `api_key`/`base_url` 参数 > 全局 `deepseek_*` 配置。
    注意：小模型层必须显式传 `api_key=settings.small_model_api_key`（即使为空），
    以严格隔离 DEEPSEEK 凭据、绝不复用；空密钥直接短路抛 LLMConnectionError。
    `transport` 仅测试注入（httpx.MockTransport）；生产为 None。
    """
    key = api_key if api_key is not None else settings.deepseek_api_key
    if not key:
        raise LLMConnectionError("LLM API Key 未配置")
    base = (base_url or settings.deepseek_base_url).rstrip("/") or "https://api.deepseek.com"
    url = f"{base}/chat/completions"
    payload = {
        "model": model or settings.deepseek_chat_model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {key}"}
    timeout = httpx.Timeout(settings.intent_llm_timeout_seconds)
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            for attempt in range(settings.intent_llm_max_retries + 1):
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 429:
                    if attempt < settings.intent_llm_max_retries:
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    raise LLMRateLimitError()
                resp.raise_for_status()
                return resp.json()
    except httpx.HTTPStatusError as exc:
        raise LLMConnectionError(
            f"意图识别模型 HTTP {exc.response.status_code}"
        ) from exc
    except httpx.TimeoutException as exc:
        raise LLMTimeoutError("意图识别模型请求超时") from exc
    except httpx.HTTPError as exc:
        raise LLMConnectionError(f"意图识别模型请求失败: {exc}") from exc
    raise LLMRateLimitError()  # 不可达（循环内 raise）


def classify_small(
    query: str, transport: httpx.BaseTransport | None = None
) -> tuple[IntentCategory, float] | None:
    """小模型意图分类。

    返回：
    - (intent, confidence) 分类成功；
    - None：解析失败/连接错误/HTTP 非 2xx（交兜底层）；
    - 抛出 LLMRateLimitError / LLMTimeoutError（按 FR-013 降级 unknown）。
    """
    # 小模型层未完整配置（缺模型名或密钥）→ 直接返回 None，交由兜底层，绝不带空模型名发请求
    if not settings.small_model_name or not settings.small_model_api_key:
        return None

    messages = [
        {"role": "system", "content": SMALL_MODEL_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    try:
        data = post_chat_completion(
            messages,
            model=settings.small_model_name,
            api_key=settings.small_model_api_key,
            base_url=settings.small_model_base_url,
            transport=transport,
        )
    except LLMConnectionError:
        return None
    log_llm_usage(data, "small_model", settings.small_model_name)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _parse_intent_json(content)

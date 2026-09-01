"""意图识别编排（三层漏斗）。

链路（data-model §状态流转）：
  输入 → 空/纯标点 → unknown
       → normalize → 规则层命中（含负样本抑制）→ 输出（source=rule，零模型）
       → intent_enabled 关闭 / 无 API key → unknown
       → 小模型层：429/超时 → unknown；≥高阈值 → 输出（source=small_model）
           └ 中段 → 重判 intent_clarify_retry 次 → 仍中段 → 澄清反问（路由 clarify）
           └ <低阈值 或 反向校准拒绝 → 放弃
       → 大模型兜底层：成功 → 输出（source=fallback）；任何失败 → unknown

`recognize()` 永不抛异常：一切模型异常按 FR-013 降级 unknown，保证不阻断 001
主链路。`debug_recognize()` 返回各层原始结果，供 /api/intent/debug 联调。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.services.config_service import get_config_value
from app.services.rag.llm import LLMRateLimitError, LLMTimeoutError

from .fallback.client import classify_fallback
from .normalize import normalize
from .rules.engine import get_rule_engine
from .schema import IntentCategory, IntentResult, SourceLayer
from .small_model.calibrate import reverse_calibrate
from .small_model.client import classify_small
from .small_model.threshold import decide, make_clarify_question

logger = get_logger(__name__)


@dataclass
class IntentTrace:
    """各层溯源（联调接口透出）。"""

    normalized_query: str = ""
    rule: dict | None = None
    small_model: dict | None = None
    fallback: dict | None = None
    error: str | None = None


def recognize(db: Session, query: str) -> IntentResult:
    """三层漏斗识别入口；外层再兜底一层 try/except，保证永不抛异常（FR-013）。"""
    result, _ = recognize_with_trace(db, query)
    return result


def recognize_with_trace(db: Session, query: str) -> tuple[IntentResult, IntentTrace]:
    """带分层溯源的公共入口（008 埋点用，FR-006）。

    复用 `_recognize_with_trace` 并加外层永不抛异常兜底（与 `recognize()` 同款
    纪律，FR-013）：一次调用同时拿到最终意图与各层原始结果（rule/small_model/
    fallback/error），供 chat 链路 intent span 记录来源层与置信度。返回结构
    类型化、零额外推理成本（research.md §4）。
    """
    try:
        return _recognize_with_trace(db, query)
    except Exception as exc:  # noqa: BLE001  意外异常全吞，降级 unknown
        logger.exception("意图识别意外异常（降级 unknown）: %s", exc)
        return _unknown(query or "", ""), IntentTrace(error="unexpected_error")


def debug_recognize(db: Session, query: str) -> dict:
    """联调用：识别 + 返回各层原始结果与降级原因。"""
    try:
        result, trace = _recognize_with_trace(db, query)
        return {
            "query": query,
            "normalized_query": trace.normalized_query,
            "rule_layer": trace.rule,
            "small_model_layer": trace.small_model,
            "fallback_layer": trace.fallback,
            "error": trace.error,
            "final": {
                "intent": result.intent.value,
                "confidence": result.confidence,
                "source_layer": result.source_layer.value,
                "clarification_question": result.clarification_question,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("意图识别联调意外异常（降级 unknown）: %s", exc)
        return {
            "query": query,
            "normalized_query": "",
            "rule_layer": None,
            "small_model_layer": None,
            "fallback_layer": None,
            "error": "unexpected_error",
            "final": {
                "intent": IntentCategory.unknown.value,
                "confidence": 0.0,
                "source_layer": SourceLayer.unknown.value,
                "clarification_question": None,
            },
        }


def _unknown(query: str, normalized: str) -> IntentResult:
    return IntentResult(
        intent=IntentCategory.unknown,
        confidence=0.0,
        source_layer=SourceLayer.unknown,
        raw_query=query,
        normalized_query=normalized,
    )


def _build(
    intent: IntentCategory,
    confidence: float,
    layer: SourceLayer,
    query: str,
    normalized: str,
    matched: list[str] | None = None,
    clarify: str | None = None,
) -> IntentResult:
    return IntentResult(
        intent=intent,
        confidence=confidence,
        source_layer=layer,
        raw_query=query,
        normalized_query=normalized,
        matched_patterns=matched or [],
        clarification_question=clarify,
    )


def _recognize_with_trace(db: Session, query: str) -> tuple[IntentResult, IntentTrace]:
    trace = IntentTrace()

    # ---------- 空/纯标点输入 ----------
    if query is None or not query.strip():
        return _unknown(query or "", ""), trace

    normalized = normalize(query)
    trace.normalized_query = normalized
    if not normalized:
        return _unknown(query, normalized), trace

    # ---------- 总开关 ----------
    if not settings.intent_enabled:
        trace.error = "intent_disabled"
        return _unknown(query, normalized), trace

    # ---------- 第 1 层：规则层（零模型短路，FR-005） ----------
    intent, matched = get_rule_engine().match(normalized)
    if intent is not None:
        trace.rule = {"intent": intent.value, "matched": matched}
        return _build(intent, 1.0, SourceLayer.rule, query, normalized, matched), trace

    # 规则层未命中 → 模型层；小模型（SMALL_MODEL_*）与兜底（DEEPSEEK_*）密钥
    # 均未配置时直接降级（FR-013）。任一配置即可进入模型层——各层内部自行短路。
    if not settings.small_model_api_key and not settings.deepseek_api_key:
        trace.error = "no_api_key"
        return _unknown(query, normalized), trace

    high = float(get_config_value(db, "intent_high_threshold", settings.intent_high_threshold))
    low = float(get_config_value(db, "intent_low_threshold", settings.intent_low_threshold))
    clarify_retry = int(get_config_value(db, "intent_clarify_retry", settings.intent_clarify_retry))
    reverse_cal = bool(get_config_value(db, "intent_reverse_calibrate", settings.intent_reverse_calibrate))

    # ---------- 第 2 层：小模型层 ----------
    try:
        small = classify_small(query)
    except LLMRateLimitError:
        trace.small_model = {"error": "rate_limited"}
        trace.error = "small_model_rate_limited"
        return _unknown(query, normalized), trace
    except LLMTimeoutError:
        trace.small_model = {"error": "timeout"}
        trace.error = "small_model_timeout"
        return _unknown(query, normalized), trace

    if small is not None:
        intent, conf = small
        trace.small_model = {"intent": intent.value, "confidence": conf}
        # 反向校准：负样本命中拒绝预测（FR-007）
        if reverse_cal and reverse_calibrate(query, intent):
            trace.small_model["reversed"] = True
            small = None

    if small is not None:
        intent, conf = small
        band = decide(conf, high, low)
        if band == "high":
            return _build(intent, conf, SourceLayer.small_model, query, normalized), trace
        if band == "middle":
            # 中段置信度：按配置重判（FR-008）。重判高 → 输出；低 → 放弃；
            # 重判耗尽仍中段 → 输出澄清反问（路由 clarify）。
            still_clarify = True
            for _ in range(max(clarify_retry, 0)):
                try:
                    again = classify_small(query)
                except (LLMRateLimitError, LLMTimeoutError):
                    again = None
                if again is None:
                    still_clarify = False
                    break
                i2, c2 = again
                band2 = decide(c2, high, low)
                if band2 == "high":
                    return _build(i2, c2, SourceLayer.small_model, query, normalized), trace
                if band2 == "low":
                    small = None
                    still_clarify = False
                    break
                intent, conf = i2, c2  # 仍中段，继续下一轮重判
            if still_clarify:
                return _build(
                    intent, conf, SourceLayer.small_model, query, normalized,
                    clarify=make_clarify_question(intent),
                ), trace
        # band == low → 放弃小模型结果，流转兜底

    # ---------- 第 3 层：大模型兜底层（FR-009/FR-010） ----------
    fb = classify_fallback(query)
    trace.fallback = {"result": (fb[0].value, fb[1]) if fb else None}
    if fb is None:
        trace.error = "fallback_failed"
        return _unknown(query, normalized), trace
    f_intent, f_conf = fb
    return _build(f_intent, f_conf, SourceLayer.fallback, query, normalized), trace

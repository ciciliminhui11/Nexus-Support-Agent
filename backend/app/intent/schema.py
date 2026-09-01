"""意图识别核心类型：意图/来源层/Handler 枚举 + IntentResult 传输对象。

对应 specs/006-intent-recognition/data-model.md §1/§2/§4。本特性不新增业务表，
识别结果仅落 `message.intent_label`（中文标签），其余均为进程内传输对象。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IntentCategory(str, Enum):
    product_consult = "product_consult"  # 产品咨询
    after_sale = "after_sale"            # 售后
    small_talk = "small_talk"            # 闲聊
    complaint = "complaint"              # 投诉
    unknown = "unknown"                  # 未识别（降级值）


class SourceLayer(str, Enum):
    rule = "rule"                  # 规则层（零模型）
    small_model = "small_model"    # 小模型层
    fallback = "fallback"          # 大模型兜底层
    unknown = "unknown"            # 降级


class HandlerKey(str, Enum):
    rag_qa = "rag_qa"      # 001 RAG 问答链路
    small_talk = "small_talk"  # 闲聊模板回复，不检索
    complaint = "complaint"    # 投诉转人工提示，不检索
    clarify = "clarify"        # 中段置信度澄清反问
    default = "default"        # 未识别 → 走 001 正常问答


INTENT_LABEL_CN: dict[IntentCategory, str] = {
    IntentCategory.product_consult: "产品咨询",
    IntentCategory.after_sale: "售后",
    IntentCategory.small_talk: "闲聊",
    IntentCategory.complaint: "投诉",
    IntentCategory.unknown: "未识别",
}


def parse_intent_category(value: str) -> IntentCategory | None:
    """把模型输出的字符串解析为合法意图枚举；非法返回 None。"""
    try:
        return IntentCategory(value)
    except ValueError:
        return None


@dataclass
class IntentResult:
    """一次识别流程的产出（进程内传输对象，不落库）。

    属性对齐 data-model §2：intent / confidence / source_layer /
    raw_query / normalized_query / matched_patterns / clarification_question。
    """

    intent: IntentCategory
    confidence: float
    source_layer: SourceLayer
    raw_query: str
    normalized_query: str
    matched_patterns: list[str] = field(default_factory=list)
    clarification_question: str | None = None

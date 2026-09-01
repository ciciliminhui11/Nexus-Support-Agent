"""高/低双阈值三分带判定（FR-008）。

- 置信度 ≥ 高阈值 → high：直接输出意图；
- 低阈值 ≤ 置信度 < 高阈值 → middle：反问澄清 + 重判；
- 置信度 < 低阈值 → low：放弃小模型结果，流转大模型兜底。
"""
from __future__ import annotations

from ..schema import IntentCategory


def decide(confidence: float, high: float, low: float) -> str:
    if confidence >= high:
        return "high"
    if confidence >= low:
        return "middle"
    return "low"


def make_clarify_question(predicted: IntentCategory) -> str:
    """中段置信度澄清追问（v1 模板基线，面向两个 RAG 意图对比提问）。"""
    if predicted in (IntentCategory.product_consult, IntentCategory.after_sale):
        return (
            "抱歉，我想和您确认一下：您是想咨询产品信息（产品咨询），"
            "还是咨询售后/退换货相关服务（售后）呢？"
        )
    return "抱歉，请再详细描述一下您的问题，我好更准确地为您服务。"

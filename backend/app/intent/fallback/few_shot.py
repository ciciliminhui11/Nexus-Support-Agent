"""大模型兜底层 Few-shot 样例（FR-009）。

四类意图各 ≥1 例 + 1 个歧义归 unknown 的样例，随 system prompt 注入。
"""
from __future__ import annotations

FALLBACK_FEW_SHOT_EXAMPLES: list[dict[str, str]] = [
    # product_consult 产品咨询
    {"user": "我想咨询下你们最新款手机的价格", "intent": "product_consult"},
    {"user": "这个产品怎么使用？", "intent": "product_consult"},
    # after_sale 售后
    {"user": "我的订单可以退货吗", "intent": "after_sale"},
    {"user": "保修期内维修怎么申请", "intent": "after_sale"},
    # small_talk 闲聊
    {"user": "谢谢你的帮助", "intent": "small_talk"},
    {"user": "在吗？", "intent": "small_talk"},
    # complaint 投诉
    {"user": "你们的服务态度太差了，我要投诉", "intent": "complaint"},
    {"user": "怎么投诉你们", "intent": "complaint"},
    # 歧义/离题 → unknown
    {"user": "能退吗", "intent": "unknown"},
    {"user": "今天天气怎么样", "intent": "unknown"},
]

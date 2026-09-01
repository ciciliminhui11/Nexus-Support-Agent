"""006 意图识别（三层漏斗）：规则层 → 小模型层 → 大模型兜底层。

模块划分：
- schema.py     意图/来源层/路由枚举与 IntentResult 传输对象
- normalize.py  文本归一化（FR-001）
- rules/        规则层（AC 关键词 + 句式模板 + 负样本抑制，零模型短路）
- small_model/  小模型识别层（双阈值 + 澄清重判 + 反向校准）
- fallback/     大模型兜底层（Few-shot + 强制 JSON）
- service.py    三层漏斗编排（recognize / debug_recognize）
- router.py     意图 → Handler 路由映射（FR-012）
"""

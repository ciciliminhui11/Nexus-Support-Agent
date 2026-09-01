"""规则层（006 第 1 层）：零模型短路的意图识别。

- ac_automaton.py        AC 关键词多模式匹配（最长匹配 + 词边界）
- template_patterns.py   句式模板匹配（pyparsing.Regex）
- engine.py              RuleEngine 聚合 + 负样本抑制 + 进程内单例
"""
from .engine import RuleEngine, get_rule_engine, reload_rule_engine

__all__ = ["RuleEngine", "get_rule_engine", "reload_rule_engine"]

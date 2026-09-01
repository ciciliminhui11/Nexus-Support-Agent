"""规则层引擎：聚合 AC 关键词 + 句式模板 + 负样本抑制（FR-005 命中即短路）。

负样本在规则层的作用：抑制复合词/机构名造成的误命中（如关键词「投诉」命中
「投诉咨询中心」）。这与小模型层的反向校准（calibrate.py）共用同一负样本库，
是本层「词边界」语义的补充。
"""
from __future__ import annotations

from app.core.logging import get_logger

from ..config_loader import get_keywords, get_negative_samples, get_patterns
from ..schema import IntentCategory
from .ac_automaton import AcKeywordMatcher
from .template_patterns import TemplateMatcher

logger = get_logger(__name__)


class RuleEngine:
    def __init__(
        self,
        keywords: dict[str, IntentCategory],
        patterns: dict[IntentCategory, list[str]],
        negative_samples: dict[IntentCategory, list[str]],
    ) -> None:
        self._ac = AcKeywordMatcher(keywords)
        self._tmpl = TemplateMatcher(patterns)
        self._negative = negative_samples

    def match(self, text: str) -> tuple[IntentCategory | None, list[str]]:
        """对归一化文本匹配，返回 (意图 | None, 命中的关键词/模板列表)。"""
        words: list[str] = []
        tmpls: list[str] = []
        intent, words = self._ac.match(text)
        if intent is not None and not self._suppressed(intent, text):
            return intent, words
        t_intent, tmpls = self._tmpl.match(text)
        if t_intent is not None and not self._suppressed(t_intent, text):
            return t_intent, words + tmpls
        return None, words + tmpls

    def _suppressed(self, intent: IntentCategory, text: str) -> bool:
        """负样本命中 → 抑制该意图的规则命中（子串匹配）。"""
        for sample in self._negative.get(intent, []):
            if sample in text:
                return True
        return False


_engine: RuleEngine | None = None


def get_rule_engine() -> RuleEngine:
    """进程内惰性单例（首次调用加载 yaml；reload_rule_engine 重置）。"""
    global _engine
    if _engine is None:
        _engine = RuleEngine(get_keywords(), get_patterns(), get_negative_samples())
    return _engine


def reload_rule_engine() -> None:
    """重置单例（测试/热加载用），下次访问重新加载配置。"""
    global _engine
    _engine = None

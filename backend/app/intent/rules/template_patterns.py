"""句式模板匹配（FR-004）：pyparsing.Regex 编译命名分组模板，search 定位。

模板即正则字符串（如 `取消订单(?P<order_id>.+)`），yaml 中书写命名分组，
编译期跳过非法模板；匹配取「是否命中」+ 记录命中的模板文本（溯源用）。
"""
from __future__ import annotations

import pyparsing as pp

from app.core.logging import get_logger

from ..schema import IntentCategory

logger = get_logger(__name__)


class TemplateMatcher:
    def __init__(self, patterns: dict[IntentCategory, list[str]]) -> None:
        self._templates: list[tuple[IntentCategory, pp.Regex, str]] = []
        for intent, tmpls in patterns.items():
            for tmpl in tmpls:
                try:
                    expr = pp.Regex(tmpl)
                    expr.re  # pyparsing 惰性编译，此处强制触发，让非法模板在构造期被跳过
                    self._templates.append((intent, expr, tmpl))
                except Exception as exc:  # noqa: BLE001  非法模板跳过
                    logger.warning("006 句式模板编译失败（跳过）: %s -> %s", tmpl, exc)

    def match(self, text: str) -> tuple[IntentCategory | None, list[str]]:
        """返回 (意图 | None, 命中的模板列表)。跨意图命中视为冲突 → None。"""
        matched: list[str] = []
        intents: set[IntentCategory] = set()
        for intent, expr, raw in self._templates:
            if expr.search_string(text):
                matched.append(raw)
                intents.add(intent)
        if not matched:
            return None, []
        if len(intents) != 1:
            # 跨意图模板冲突 → 不阻断，交模型层
            return None, matched
        return intents.pop(), matched

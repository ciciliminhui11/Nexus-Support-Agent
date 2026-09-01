"""反向校准（FR-007）：负样本命中即拒绝该预测。

匹配规则：`re:` 前缀当正则，其余按子串包含。负样本来源：
- 默认读取配置 yaml（get_negative_samples）；
- 可显式传入 dict（测试/调试用）。
"""
from __future__ import annotations

import re

from app.core.logging import get_logger

from ..config_loader import get_negative_samples
from ..schema import IntentCategory

logger = get_logger(__name__)


def reverse_calibrate(
    text: str,
    intent: IntentCategory,
    negative_samples: dict[IntentCategory, list[str]] | None = None,
) -> bool:
    """返回 True 表示该预测应被拒绝（输入命中该意图的负样本特征）。"""
    samples = negative_samples if negative_samples is not None else get_negative_samples()
    for sample in samples.get(intent, []):
        if not sample:
            continue
        if sample.startswith("re:"):
            try:
                if re.search(sample[3:], text):
                    return True
            except re.error as exc:
                logger.warning("006 负样本正则非法（忽略）: %s -> %s", sample, exc)
                continue
        elif sample in text:
            return True
    return False

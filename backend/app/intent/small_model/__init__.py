"""小模型识别层（006 第 2 层）：双阈值判定 + 澄清重判 + 反向校准。

- client.py      OpenAI 兼容 /chat/completions 同步封装 + classify_small
- threshold.py   高/低双阈值三分带判定（FR-008）
- calibrate.py   反向校准（负样本拦截，FR-007）
"""

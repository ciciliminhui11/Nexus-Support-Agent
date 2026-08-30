"""文本抽取：txt/md（utf-8 优先，gbk 兜底），空内容拒绝。"""
from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BizError

_ENCODINGS = ("utf-8-sig", "utf-8", "gbk")


def parse_text(file_path: str) -> str:
    data = Path(file_path).read_bytes()
    text = None
    for enc in _ENCODINGS:
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise BizError(
            code="parse_error",
            message="文本抽取失败：文件编码无法识别（expected utf-8）",
        )
    if not text.strip():
        raise BizError(code="empty_file", message="文件内容为空")
    return text

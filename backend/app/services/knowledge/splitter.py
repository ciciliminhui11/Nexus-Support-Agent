"""文本切分（自研、可读可调）。

策略：按段落（双换行）为基本单元，合并入当前 chunk 直到 chunk_size；
单段超长则硬切；跨 chunk 时携带前 chunk 尾部 overlap 字符保持语义连续。
"""
from __future__ import annotations

import re


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 80) -> list[str]:
    if chunk_size <= 0:
        chunk_size = 500
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # 单段超 chunk_size 硬切
        while len(para) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:chunk_size])
            para = para[chunk_size:]
        if not current:
            current = para
        elif len(current) + 1 + len(para) <= chunk_size:
            current = f"{current}\n{para}"
        else:
            chunks.append(current)
            tail = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = f"{tail}\n{para}" if tail else para

    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def make_snippet(chunk: str, length: int = 100) -> str:
    """来源摘要：去空白归一化后的切片首部（供 meta 事件 / reference_source）。"""
    compact = re.sub(r"\s+", " ", chunk).strip()
    return compact[:length] + ("…" if len(compact) > length else "")

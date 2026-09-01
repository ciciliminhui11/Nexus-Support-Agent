"""文本切分（自研、可读可调）。

- `split_text()`：基础段落切分（段落合并 / 单段硬切 / overlap），返回 `list[str]`，
  供检索测试与「无标题/超长章节」兜底复用；
- `split_document()`：按文件类型增强切分（T012）——
  - **markdown**：按 `#`/`##`/`###` 标题层级切分，一个章节一个 chunk（带
    `section` 章节名与 `heading_path` 标题路径）；无标题/超长章节走固定长度兜底；
    表格块转自然语言后再切；
  - **txt**：先粗切，若传入 embedding client 则对相邻段落做相似度检测，
    在低相似断点二次切分（无 client 保持粗切，不阻断）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import settings
from app.core.logging import get_logger
from app.services.embedding import EmbeddingClient, embed_texts

logger = get_logger(__name__)

# txt 语义断点阈值（余弦相似度）：低于该值视为语义边界，强制换块
SEMANTIC_SPLIT_THRESHOLD = 0.5

_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")


@dataclass
class Chunk:
    """结构化切片（T012 输出契约）。text 为章节正文，heading_path 供标题注入。"""

    text: str
    section: str | None = None
    heading_path: str | None = None


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 80) -> list[str]:
    if chunk_size <= 0:
        chunk_size = 500
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return _merge_paragraphs(paragraphs, chunk_size, chunk_overlap, breakpoints=set())


def make_snippet(chunk: str, length: int = 100) -> str:
    """来源摘要：去空白归一化后的切片首部（供 meta 事件 / reference_source）。"""
    compact = re.sub(r"\s+", " ", chunk).strip()
    return compact[:length] + ("…" if len(compact) > length else "")


def split_document(
    source_name: str,
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    embed_client: EmbeddingClient | None = None,
    semantic_threshold: float = SEMANTIC_SPLIT_THRESHOLD,
) -> list[Chunk]:
    """按文件类型增强切分（T012）。

    - markdown（.md/.markdown）：标题层级切分 + 表格转自然语言；
    - 其他（txt 等）：段落粗切 + （有 embed_client 时）语义断点二次切分。
    """
    if chunk_size <= 0:
        chunk_size = 500
    name = source_name.lower()
    if name.endswith((".md", ".markdown")):
        return _split_markdown(text, chunk_size, chunk_overlap)
    return _split_plain(text, chunk_size, chunk_overlap, embed_client, semantic_threshold)


# ---------- 基础段落合并（chunk_size / overlap / 断点感知） ----------


def _merge_paragraphs(
    paragraphs: list[str],
    chunk_size: int,
    chunk_overlap: int,
    breakpoints: set[int],
) -> list[str]:
    """把段落合并成 chunk。`breakpoints` 为段间边界下标集合：`j ∈ breakpoints`
    表示第 j 段与第 j+1 段之间必须断开（语义断点），即使大小允许也不合并。"""
    chunks: list[str] = []
    current = ""

    for i, para in enumerate(paragraphs):
        # 语义断点：段落 i 之前是边界 (i-1) → 强制换块
        if current and i > 0 and (i - 1) in breakpoints:
            chunks.append(current)
            current = ""
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


# ---------- markdown：标题层级切分 + 表格转自然语言 ----------


def _split_markdown(
    text: str, chunk_size: int, chunk_overlap: int
) -> list[Chunk]:
    text = _tables_to_natural(text)
    lines = text.splitlines()

    heading_stack: list[tuple[int, str]] = []  # (level, title)，根在前
    current_title: str | None = None
    current_path: str | None = None
    buffer: list[str] = []
    sections: list[tuple[str | None, str | None, str]] = []

    def flush() -> None:
        nonlocal buffer
        body = "\n".join(buffer).strip()
        if body:
            sections.append((current_title, current_path, body))
        buffer = []

    for line in lines:
        m = _MARKDOWN_HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            current_title = title
            current_path = " > ".join(t for _, t in heading_stack)
        else:
            buffer.append(line)
    flush()

    # 无任何标题 → 固定长度兜底，无章节信息
    if not sections:
        return [Chunk(text=t) for t in _merge_paragraphs(
            _to_paragraphs(text), chunk_size, chunk_overlap, breakpoints=set()
        )]

    chunks: list[Chunk] = []
    for title, path, body in sections:
        if len(body) <= chunk_size:
            chunks.append(Chunk(text=body, section=title, heading_path=path))
        else:
            # 超长章节 → 固定长度兜底，但保留章节归属（标题注入仍生效）
            for sub in _merge_paragraphs(
                _to_paragraphs(body), chunk_size, chunk_overlap, breakpoints=set()
            ):
                chunks.append(Chunk(text=sub, section=title, heading_path=path))
    return chunks


def _to_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _tables_to_natural(text: str) -> str:
    """markdown 表格块（连续 `|` 行）转自然语言后再切分（T012/T013）。"""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        if _TABLE_ROW_RE.match(lines[i]):
            rows: list[str] = []
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i]):
                rows.append(lines[i])
                i += 1
            natural = _table_rows_to_natural(rows)
            if natural:
                out.append(natural)
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def _table_rows_to_natural(rows: list[str]) -> str:
    cells_rows = [_split_cells(r) for r in rows]
    # 跳过表头分隔行（| --- | --- |）
    cells_rows = [c for c in cells_rows if not _is_separator_row(c)]
    if not cells_rows:
        return ""
    header = cells_rows[0]
    body = cells_rows[1:]
    sentences = []
    for row in body:
        pairs = []
        for idx, val in enumerate(row):
            name = header[idx] if idx < len(header) and header[idx] else f"列{idx + 1}"
            pairs.append(f"{name}：{val}")
        sentences.append("，".join(pairs))
    return "。".join(sentences)


def _split_cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(
        re.fullmatch(r":?-+:?", c.replace(" ", "")) for c in cells
    )


# ---------- txt：粗切 + 语义断点二次切分 ----------


def _split_plain(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    embed_client: EmbeddingClient | None,
    semantic_threshold: float,
) -> list[Chunk]:
    paragraphs = _to_paragraphs(text)
    if not paragraphs:
        return []
    if embed_client is None:
        return [Chunk(text=t) for t in _merge_paragraphs(
            paragraphs, chunk_size, chunk_overlap, breakpoints=set()
        )]
    breakpoints = _semantic_breakpoints(paragraphs, embed_client, semantic_threshold)
    merged = _merge_paragraphs(paragraphs, chunk_size, chunk_overlap, breakpoints)
    return [Chunk(text=t) for t in merged]


def _semantic_breakpoints(
    paragraphs: list[str],
    embed_client: EmbeddingClient,
    threshold: float,
) -> set[int]:
    """相邻段落 embedding 相似度 < 阈值 → 段间为语义边界。

    相似度计算失败（如 embedding 服务瞬时不可用）→ 返回空集，保持粗切不阻断；
    语义切分仅是增强，不应因它让整份文档失败。
    """
    if len(paragraphs) < 2:
        return set()
    try:
        embeddings = embed_texts(
            embed_client, paragraphs, batch_size=settings.embedding_batch_size
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("002 语义断点检测失败，保持粗切: %s", exc)
        return set()
    breakpoints: set[int] = set()
    for i in range(len(paragraphs) - 1):
        if _cosine_similarity(embeddings[i], embeddings[i + 1]) < threshold:
            breakpoints.add(i)
    return breakpoints


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

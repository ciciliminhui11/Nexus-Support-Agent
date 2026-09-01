"""文本抽取（编码兜底）与切分（段落 / 硬切 / overlap）。"""
from __future__ import annotations

import pytest

from app.core.exceptions import BizError
from app.services.knowledge import parser, splitter


# ---------- parser：编码兜底 ----------

def test_parse_utf8(tmp_path):
    p = tmp_path / "a.txt"
    # 显式 newline="\n"，避免 Windows 文本模式把 \n 转成 \r\n
    p.write_text("你好世界\n第二行", encoding="utf-8", newline="\n")
    assert parser.parse_text(str(p)) == "你好世界\n第二行"


def test_parse_utf8_bom(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"\xef\xbb\xbf" + "你好".encode("utf-8"))
    assert parser.parse_text(str(p)) == "你好"


def test_parse_gbk_fallback(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes("中文内容".encode("gbk"))
    assert parser.parse_text(str(p)) == "中文内容"


def test_parse_unrecognized_encoding(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"\xff\xfe\x00\x99\x88")
    with pytest.raises(BizError) as ei:
        parser.parse_text(str(p))
    assert ei.value.code == "parse_error"


def test_parse_empty_file(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("   \n  ", encoding="utf-8")
    with pytest.raises(BizError) as ei:
        parser.parse_text(str(p))
    assert ei.value.code == "empty_file"


def test_parse_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        parser.parse_text(str(tmp_path / "nope.txt"))


# ---------- splitter：段落 / 硬切 / overlap ----------

def test_short_text_merges_into_one_chunk():
    assert splitter.split_text("你好\n世界", chunk_size=500, chunk_overlap=80) == [
        "你好\n世界"
    ]


def test_paragraphs_within_limit_merge():
    text = "第一段\n\n第二段\n\n第三段"
    assert splitter.split_text(text, chunk_size=500, chunk_overlap=80) == [
        "第一段\n第二段\n第三段"
    ]


def test_oversized_paragraph_forced_into_new_chunk():
    para = "测" * 300  # 300+1+300 > 500 → 必须换块
    text = f"{para}\n\n{para}"
    chunks = splitter.split_text(text, chunk_size=500, chunk_overlap=80)
    assert len(chunks) == 2
    assert all(len(c) >= 300 for c in chunks)


def test_hard_cuts_single_oversized_paragraph():
    para = "甲" * 1200
    assert splitter.split_text(para, chunk_size=500, chunk_overlap=80) == [
        "甲" * 500,
        "甲" * 500,
        "甲" * 200,
    ]


def test_overlap_keeps_previous_tail():
    para = "乙" * 400
    text = f"{para}\n\n{para}"
    chunks = splitter.split_text(text, chunk_size=500, chunk_overlap=80)
    assert len(chunks) == 2
    # 第二个 chunk 以第一个 chunk 尾部 80 字开头，保持语义连续
    assert chunks[1].startswith("乙" * 80)


def test_make_snippet_truncates_with_ellipsis():
    assert splitter.make_snippet("你好 世界", length=3) == "你好 …"


def test_make_snippet_compacts_whitespace():
    assert splitter.make_snippet("简短") == "简短"


# ---------- split_document：markdown 标题切分 / txt 语义断点（T012/T018） ----------

def test_markdown_splits_by_heading_levels():
    text = (
        "# 常见问题\n\n开头内容\n\n"
        "## 退换货\n\n退货政策说明\n\n"
        "### 退货时限\n\n七天内可退"
    )
    chunks = splitter.split_document("faq.md", text, chunk_size=500, chunk_overlap=80)
    assert [c.section for c in chunks] == ["常见问题", "退换货", "退货时限"]
    assert [c.heading_path for c in chunks] == [
        "常见问题",
        "常见问题 > 退换货",
        "常见问题 > 退换货 > 退货时限",
    ]
    assert "退货政策说明" in chunks[1].text


def test_markdown_without_heading_falls_back_to_plain():
    chunks = splitter.split_document("a.md", "第一段\n\n第二段", 500, 80)
    assert len(chunks) == 1
    assert chunks[0].section is None
    assert chunks[0].heading_path is None
    assert "第一段" in chunks[0].text and "第二段" in chunks[0].text


def test_markdown_oversized_section_fixed_length_fallback():
    long_body = "详" * 1200
    chunks = splitter.split_document("big.md", f"# 大章节\n\n{long_body}", 500, 80)
    assert len(chunks) == 3  # 1200 字 → 500/500/200
    assert all(c.section == "大章节" for c in chunks)
    assert all(c.heading_path == "大章节" for c in chunks)
    assert sum(len(c.text) for c in chunks) == 1200


def test_markdown_table_converted_to_natural_language():
    text = (
        "# 价格表\n\n"
        "| 产品 | 价格 |\n"
        "| --- | --- |\n"
        "| 标准版 | 99 |\n"
        "| 高级版 | 199 |\n"
    )
    chunks = splitter.split_document("price.md", text, 500, 80)
    assert len(chunks) == 1
    joined = chunks[0].text
    assert "产品：标准版" in joined and "价格：99" in joined
    assert "产品：高级版" in joined and "价格：199" in joined


def test_txt_without_client_keeps_coarse_split():
    # 无 embedding client → 按大小合并，不做语义断点
    text = "退货 order1 需要\n\n系统 order2 维护"
    chunks = splitter.split_document("a.txt", text, 500, 80)
    assert len(chunks) == 1


def test_txt_semantic_breakpoints_split_low_similarity(fake_embedding):
    # 三段关键词互不重叠 → 相邻段余弦相似度≈0 < 阈值 → 断点全开
    text = "退货 order1 需要\n\n系统 order2 维护\n\n网络 order3 故障"
    chunks = splitter.split_document(
        "a.txt", text, 500, 80, embed_client=fake_embedding
    )
    assert len(chunks) == 3


def test_txt_semantic_breakpoints_keep_similar(fake_embedding):
    # 两段共享「退货/order1」→ 相似度 > 阈值 → 合并为一块
    text = "退货 order1 需要\n\n退货 order1 请提供"
    chunks = splitter.split_document(
        "a.txt", text, 500, 80, embed_client=fake_embedding
    )
    assert len(chunks) == 1


def test_txt_semantic_split_keeps_sections_none(fake_embedding):
    chunks = splitter.split_document(
        "a.txt", "退货 order1 需要\n\n系统 order2 维护", 500, 80,
        embed_client=fake_embedding,
    )
    assert all(c.section is None and c.heading_path is None for c in chunks)

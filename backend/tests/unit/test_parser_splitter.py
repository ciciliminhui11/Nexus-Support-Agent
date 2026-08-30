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

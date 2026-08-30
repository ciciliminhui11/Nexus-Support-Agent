"""知识库上传校验：格式白名单 / 大小上限 / 空文件。"""
from __future__ import annotations

import pytest

from app.config import settings
from app.core.exceptions import BizError, FileTooLargeError
from app.services.knowledge import validator


def test_accepts_txt_and_md():
    validator.validate_upload("faq.txt", b"hello")
    validator.validate_upload("FAQ.MD", "# 标题\n正文".encode("utf-8"))
    validator.validate_upload("a.b.md", b"x")


@pytest.mark.parametrize(
    "name", ["a.exe", "b.pdf", "c", "d.png", ".hidden", "无扩展名"]
)
def test_rejects_unsupported_format(name):
    with pytest.raises(BizError) as ei:
        validator.validate_upload(name, b"content")
    assert ei.value.code == "unsupported_format"


def test_rejects_empty_content():
    for content in (b"", b"   \n\t ", b"\r\n\r\n"):
        with pytest.raises(BizError) as ei:
            validator.validate_upload("a.txt", content)
        assert ei.value.code == "empty_file"


def test_rejects_too_large(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    with pytest.raises(FileTooLargeError):
        validator.validate_upload("big.txt", b"a" * (1 * 1024 * 1024 + 1))

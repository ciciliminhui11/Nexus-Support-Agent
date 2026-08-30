"""上传校验：格式白名单 / 大小上限 / 空文件（与契约错误码一致）。"""
from __future__ import annotations

import os

from app.config import settings
from app.core.exceptions import BizError, FileTooLargeError

ALLOWED_EXTENSIONS = {".txt", ".md"}


def validate_upload(filename: str, content: bytes) -> None:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BizError(
            code="unsupported_format", message="仅支持 txt 与 markdown 格式"
        )
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise FileTooLargeError(
            message=f"文件大小超过 {settings.max_upload_size_mb}MB 上限"
        )
    if not content.strip():
        raise BizError(code="empty_file", message="文件内容为空")

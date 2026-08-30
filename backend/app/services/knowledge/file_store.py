"""原始文件本地磁盘存储（生产可换对象存储，本模块为唯一读写点）。"""
from __future__ import annotations

import os
import uuid

from app.config import settings


def save_upload(content: bytes, filename: str) -> str:
    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{os.path.basename(filename)}"
    path = os.path.join(settings.upload_dir, safe_name)
    with open(path, "wb") as f:
        f.write(content)
    return path


def delete_file(path: str) -> None:
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass  # 文件已不存在等，忽略

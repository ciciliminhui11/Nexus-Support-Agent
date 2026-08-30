"""知识库接口 Pydantic 结构（与 specs/002/contracts/knowledge-api.md 一致）。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class KnowledgeDocItem(BaseModel):
    doc_id: int
    doc_name: str
    status: str
    upload_time: datetime
    fail_msg: str | None = None


class KnowledgeListResponse(BaseModel):
    total: int
    items: list[KnowledgeDocItem]


class UploadResponse(BaseModel):
    doc_id: int
    doc_name: str
    status: str
    upload_time: datetime

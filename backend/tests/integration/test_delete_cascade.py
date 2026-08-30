"""级联删除：元数据 + 向量切片 + 原始文件 + 解析任务一并清理（FR-008）。"""
from __future__ import annotations

import os

from sqlalchemy import select

from app.db.models import KnowledgeDoc, ParseTask
from app.db.session import SessionLocal
from app.vector_store import chroma


def test_delete_cascades_all_artifacts(client, auth_headers):
    headers, _ = auth_headers(role="admin")
    resp = client.post(
        "/api/knowledge/upload",
        files={"file": ("faq.md", "退货政策内容\n\n常见问题解答".encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    doc_id = resp.json()["doc_id"]
    assert resp.status_code == 202
    assert chroma.get_collection().count() >= 1

    with SessionLocal() as s:
        path = s.get(KnowledgeDoc, doc_id).file_path
        assert os.path.exists(path)

    r = client.delete(f"/api/knowledge/{doc_id}", headers=headers)
    assert r.status_code == 204

    # 元数据不存在
    assert client.get(f"/api/knowledge/{doc_id}", headers=headers).status_code == 404
    # 向量切片清空
    assert chroma.get_collection().count() == 0
    # 原始文件删除
    assert not os.path.exists(path)
    # 解析任务随文档一并清理
    with SessionLocal() as s:
        assert s.scalar(select(ParseTask).where(ParseTask.doc_id == doc_id)) is None


def test_delete_missing_doc_returns_404(client, auth_headers):
    headers, _ = auth_headers(role="admin")
    assert client.delete("/api/knowledge/9999", headers=headers).status_code == 404


def test_delete_requires_admin(client, auth_headers):
    headers, _ = auth_headers(role="user")
    assert client.delete("/api/knowledge/1", headers=headers).status_code == 403

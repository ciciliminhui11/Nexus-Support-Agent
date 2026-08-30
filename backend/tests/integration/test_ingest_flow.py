"""知识库上传全流程：上传 → 后台解析入库 → 就绪 → 检索命中（API 层 + 伪 embedding）。"""
from __future__ import annotations

from app.vector_store import chroma


def _upload(client, headers, content, name="faq.md", mime="text/markdown"):
    return client.post(
        "/api/knowledge/upload",
        files={"file": (name, content, mime)},
        headers=headers,
    )


def test_upload_ingests_and_retrieves(client, auth_headers, fake_embedding):
    headers, _ = auth_headers(role="admin")
    content = (
        "常见问题\n\n问：如何退货？\n答：提供订单号即可。\n\n"
        "问：如何换货？\n答：联系在线客服。\n\n"
        "# 退货政策\n收货后 30 天内可申请退货。"
    )
    resp = _upload(client, headers, content.encode("utf-8"))
    assert resp.status_code == 202
    doc_id = resp.json()["doc_id"]

    # 后台任务在响应返回前已执行完 → 文档应为就绪
    detail = client.get(f"/api/knowledge/{doc_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "就绪"

    # 列表可查
    lst = client.get("/api/knowledge/list", headers=headers)
    assert lst.status_code == 200
    data = lst.json()
    assert data["total"] == 1
    assert data["items"][0]["doc_id"] == doc_id

    # 向量已写入，检索"退货"能命中含"退货"的切片
    result = chroma.query(fake_embedding.embed(["退货"])[0], n_results=3)
    assert result["ids"][0], "应检索到切片"
    assert any("退货" in d for d in result["documents"][0])


def test_upload_requires_admin(client, auth_headers):
    headers, _ = auth_headers(role="user")
    resp = _upload(client, headers, b"hi", name="a.md")
    assert resp.status_code == 403


def test_upload_rejects_bad_format(client, auth_headers):
    headers, _ = auth_headers(role="admin")
    resp = _upload(client, headers, b"x", name="virus.exe")
    assert resp.status_code == 400
    assert resp.json()["code"] == "unsupported_format"


def test_upload_rejects_empty(client, auth_headers):
    headers, _ = auth_headers(role="admin")
    resp = _upload(client, headers, b"", name="empty.txt")
    assert resp.status_code == 400
    assert resp.json()["code"] == "empty_file"


def test_list_paginates(client, auth_headers):
    headers, _ = auth_headers(role="admin")
    for i in range(3):
        _upload(client, headers, f"文档 {i}\n\n内容".encode("utf-8"), name=f"d{i}.md")

    data = client.get("/api/knowledge/list?page=1&page_size=2", headers=headers).json()
    assert data["total"] == 3
    assert len(data["items"]) == 2


def test_detail_404_for_missing(client, auth_headers):
    headers, _ = auth_headers(role="admin")
    assert client.get("/api/knowledge/9999", headers=headers).status_code == 404

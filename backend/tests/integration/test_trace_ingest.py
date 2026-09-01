"""008 ingest 链路埋点集成测试（T013，FR-001）。

上传 → 后台处理（BackgroundTasks 响应前同步执行）→ trace 入缓冲 →
`trace_flush(db)` 显式落库 → 断言 span 序列 / detail 关键指标 / 终态；
失败与并发删除取消路径用 monkeypatch 确定性触发。
"""
from __future__ import annotations

from app.db.models import KnowledgeDoc, TraceEvent
from app.db.session import SessionLocal


def _upload(client, headers, content, name="faq.md", mime="text/markdown"):
    return client.post(
        "/api/knowledge/upload",
        files={"file": (name, content, mime)},
        headers=headers,
    )


def _rows(db, doc_id):
    return (
        db.query(TraceEvent)
        .filter(TraceEvent.doc_id == doc_id)
        .order_by(TraceEvent.seq)
        .all()
    )


def test_normal_upload_produces_ok_ingest_trace(
    client, db, auth_headers, trace_flush, fake_embedding
):
    """正常上传：≥4 条 ok span，detail 含字符数/切片数/batches/dim。"""
    headers, _ = auth_headers(role="admin")
    content = (
        "常见问题\n\n问：如何退货？\n答：提供订单号即可。\n\n"
        "# 退货政策\n收货后 30 天内可申请退货。"
    )
    resp = _upload(client, headers, content.encode("utf-8"))
    assert resp.status_code == 202
    doc_id = resp.json()["doc_id"]
    assert trace_flush() >= 1

    rows = _rows(db, doc_id)
    assert rows, "应产出 ingest trace"
    stages = [r.stage for r in rows]
    assert stages[0] == "meta"
    for stage in ("doc_load", "doc_parse", "doc_split", "doc_embed_ingest", "doc_status"):
        assert stage in stages, f"缺少阶段 {stage}"
    assert all(r.status == "ok" for r in rows)

    def _detail(stage: str) -> dict:
        return next(r for r in rows if r.stage == stage).detail

    assert _detail("doc_parse")["chars"] == len(content)
    split_d = _detail("doc_split")
    assert split_d["chunks"] >= 1
    assert split_d["semantic_split"] is False  # .md 不语义切分
    embed_d = _detail("doc_embed_ingest")
    assert embed_d["vectors"] >= 1
    assert embed_d["batches"] >= 1
    assert embed_d["dim"] == fake_embedding.dim
    assert _detail("doc_status")["status"] == "就绪"


def test_parse_failure_records_error_trace(
    client, db, auth_headers, trace_flush, monkeypatch
):
    """解析失败：出错阶段 error span + doc_status 失败 + trace 整体 error。"""
    headers, _ = auth_headers(role="admin")

    def boom(path):  # noqa: ARG001
        raise ValueError("无法解析的文件格式")

    monkeypatch.setattr("app.services.knowledge.parser.parse_text", boom)
    resp = _upload(client, headers, b"garbage", name="bad.txt")
    assert resp.status_code == 202
    doc_id = resp.json()["doc_id"]
    trace_flush()

    rows = _rows(db, doc_id)
    meta = rows[0]
    assert meta.status == "error"
    assert "无法解析的文件格式" in (meta.error or "")

    stages = [r.stage for r in rows]
    assert "doc_parse" in stages
    assert "doc_rollback" in stages
    assert "doc_status" in stages
    err_span = next(r for r in rows if r.stage == "doc_parse")
    assert err_span.status == "error"
    assert "无法解析的文件格式" in (err_span.error or "")
    rollback_d = next(r for r in rows if r.stage == "doc_rollback").detail
    assert "无法解析的文件格式" in rollback_d["reason"]
    status_d = next(r for r in rows if r.stage == "doc_status").detail
    assert status_d["status"] == "失败"


def test_concurrent_delete_records_cancelled(
    client, db, auth_headers, trace_flush, monkeypatch
):
    """并发删除取消：doc_status=已取消 + rollback 标记，不残留误导终态。"""
    headers, _ = auth_headers(role="admin")
    import app.services.knowledge.pipeline as pipeline

    original = pipeline.splitter.split_document

    def delete_then_split(
        source_name,
        text,
        chunk_size=500,
        chunk_overlap=80,
        embed_client=None,
        semantic_threshold=0.5,
    ):
        chunks = original(
            source_name, text, chunk_size, chunk_overlap, embed_client, semantic_threshold
        )
        # 模拟并发删除：处理中途文档被删除（独立会话提交，绕过 identity map）
        other = SessionLocal()
        try:
            other.query(KnowledgeDoc).filter(
                KnowledgeDoc.doc_name == source_name
            ).delete()
            other.commit()
        finally:
            other.close()
        return chunks

    monkeypatch.setattr(
        "app.services.knowledge.pipeline.splitter.split_document", delete_then_split
    )
    resp = _upload(client, headers, "并发删除测试\n\n内容。".encode("utf-8"), name="cancel.txt")
    assert resp.status_code == 202
    doc_id = resp.json()["doc_id"]
    trace_flush()

    rows = _rows(db, doc_id)
    status_span = next(r for r in rows if r.stage == "doc_status")
    assert status_span.detail["status"] == "已取消"
    assert status_span.detail["rollback"] is True
    assert status_span.status == "ok"
    assert rows[0].status == "ok"  # 已取消是正常终态，非 error

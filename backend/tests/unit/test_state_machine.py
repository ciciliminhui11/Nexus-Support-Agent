"""知识库状态机：处理中→就绪 / 失败（含部分写入回滚）/ 已取消（并发删除），及超时守卫。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import LLMError
from app.db.models import KnowledgeDoc, ParseTask
from app.db.session import SessionLocal
from app.services.knowledge import pipeline
from app.services.knowledge.splitter import split_text
from app.vector_store import chroma


def _insert_doc(db, tmp_path, text, name="faq.md") -> KnowledgeDoc:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    doc = KnowledgeDoc(doc_name=name, file_path=str(p), status="处理中")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _task(db, doc_id):
    return db.scalar(select(ParseTask).where(ParseTask.doc_id == doc_id))


def test_success_transitions_to_ready(db, tmp_path):
    doc = _insert_doc(db, tmp_path, "问：如何退货？\n答：联系客服。\n\n# 政策\n退货需 30 天内。")

    pipeline.process_document(doc.id)

    db.refresh(doc)
    assert doc.status == "就绪"
    assert doc.fail_msg is None
    task = _task(db, doc.id)
    assert task.status == "成功"
    assert chroma.get_collection().count() >= 1


def test_failure_marks_doc_and_task_failed(db, tmp_path):
    doc = _insert_doc(db, tmp_path, "x", name="broken.md")
    # 指向不存在的文件 → 解析抛 FileNotFoundError
    doc.file_path = str(tmp_path / "nope.md")
    db.commit()

    pipeline.process_document(doc.id)

    db.refresh(doc)
    assert doc.status == "失败"
    assert doc.fail_msg
    task = _task(db, doc.id)
    assert task.status == "失败"
    assert task.fail_msg
    assert chroma.get_collection().count() == 0


def test_partial_failure_rolls_back_chunks(db, tmp_path, monkeypatch):
    """批量向量化中途失败 → 已写入的切片被整份回滚（FR-011）。"""
    para = "答：" + "详" * 400  # 403 字/段，每段独立成 chunk
    text = "\n\n".join([para] * 20)
    assert len(split_text(text, 500, 80)) > 16  # 超过 batch_size=16，确保分批

    doc = _insert_doc(db, tmp_path, text, name="big.md")

    class FlakyEmbedding:
        def __init__(self, inner) -> None:
            self._inner = inner
            self._calls = 0

        def embed(self, texts):
            self._calls += 1
            if self._calls > 1:
                raise LLMError(message="embedding 服务中断")
            return self._inner.embed(texts)

    monkeypatch.setattr(
        "app.services.knowledge.pipeline.get_embedding_client",
        lambda: FlakyEmbedding(_dummy_embedding()),
    )

    pipeline.process_document(doc.id)

    db.refresh(doc)
    assert doc.status == "失败"
    # 第一批已写入的 16 个切片被回滚
    assert chroma.get_collection().count() == 0


def test_concurrent_delete_marks_task_cancelled(db, tmp_path, monkeypatch):
    """处理期间文档被并发删除 → 向量回滚、任务置已取消、不残留半成品。"""
    doc = _insert_doc(db, tmp_path, "问题\n\n答案\n\n更多内容")

    real_ingest = pipeline.ingest_chunks

    def deleting_ingest(doc_id, chunks, client, batch_size):
        real_ingest(doc_id, chunks, client, batch_size)
        # 模拟并发：向量刚写完，元数据已被删除
        with SessionLocal() as s:
            d = s.get(KnowledgeDoc, doc_id)
            s.delete(d)
            s.commit()

    monkeypatch.setattr("app.services.knowledge.pipeline.ingest_chunks", deleting_ingest)

    pipeline.process_document(doc.id)

    task = _task(db, doc.id)
    assert task.status == "已取消"
    # 本会话 identity map 仍缓存被删对象，须用全新会话验证行确实已删
    with SessionLocal() as s:
        assert s.get(KnowledgeDoc, doc.id) is None
    assert chroma.get_collection().count() == 0


def test_stale_processing_times_out(db):
    """超时守卫：处理中超过阈值的任务/文档置失败（SC-004 防卡死）。"""
    doc = KnowledgeDoc(doc_name="slow.md", file_path="unused", status="处理中")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    task = ParseTask(doc_id=doc.id, status="处理中")
    db.add(task)
    db.commit()
    task.create_time = datetime.now() - timedelta(hours=2)
    db.commit()

    cleaned = pipeline.mark_stale_processing_timeout(timeout_seconds=60)

    assert cleaned == 1
    db.refresh(task)
    assert task.status == "失败"
    assert task.fail_msg == "解析任务超时"
    db.refresh(doc)
    assert doc.status == "失败"
    assert doc.fail_msg == "解析任务超时"


def _dummy_embedding():
    """常量向量即可：同一文档内所有切片维度一致即可满足 Chroma。"""

    class _Const:
        def embed(self, texts):
            return [[1.0, 0.0, 0.0] for _ in texts]

    return _Const()

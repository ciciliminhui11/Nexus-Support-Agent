"""文档处理流水线（后台任务入口）。

解析 → 切分 → 向量化 → 写入 Chroma → 文档状态就绪；
任一环节失败：回滚已写入切片 + 文档/任务状态置失败（FR-011 整份失败回滚）。
并发删除（处理中文档被删）时：向量回滚 + 任务置已取消，不残留半成品。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.config import settings
from app.core.logging import get_logger
from app.db.models import KnowledgeDoc, ParseTask
from app.db.session import SessionLocal
from app.services.embedding import get_embedding_client
from app.services.knowledge import parser, splitter
from app.services.knowledge.ingester import ingest_chunks
from app.vector_store import chroma

logger = get_logger(__name__)


def process_document(doc_id: int) -> None:
    db = SessionLocal()
    try:
        doc = db.get(KnowledgeDoc, doc_id)
        if doc is None:
            return  # 已被清理
        task = ParseTask(doc_id=doc_id, status="处理中")
        db.add(task)
        db.commit()
        db.refresh(task)
        try:
            text = parser.parse_text(doc.file_path)
            chunks = splitter.split_text(
                text, settings.chunk_size, settings.chunk_overlap
            )
            if not chunks:
                raise ValueError("文档切分后无有效内容")
            client = get_embedding_client()
            ingest_chunks(doc_id, chunks, client, settings.embedding_batch_size)

            # 重新加载，校验文档是否被并发删除。
            # 注意 identity map：doc 已在会话内加载过，普通 get 命中缓存返回陈旧对象，
            # 必须 populate_existing 强制走 DB，行已删则返回 None。
            doc = db.get(KnowledgeDoc, doc_id, populate_existing=True)
            if doc is None:
                chroma.delete_by_doc_id(doc_id)
                task.status = "已取消"
                task.finish_time = datetime.now()
                db.commit()
                return
            doc.status = "就绪"
            doc.fail_msg = None
            task.status = "成功"
        except Exception as exc:  # noqa: BLE001  任何环节失败 → 整份失败
            logger.exception("文档 %s 处理失败", doc_id)
            chroma.delete_by_doc_id(doc_id)  # 回滚已写入切片
            doc = db.get(KnowledgeDoc, doc_id, populate_existing=True)
            if doc is not None:
                doc.status = "失败"
                doc.fail_msg = str(exc)[:1000]
            task.status = "失败"
            task.fail_msg = str(exc)[:1000]
        task.finish_time = datetime.now()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("处理文档 %s 时数据库异常", doc_id)
    finally:
        db.close()


def mark_stale_processing_timeout(timeout_seconds: int | None = None) -> int:
    """超时守卫：处理中超过阈值（默认 600s）的任务/文档置失败（SC-004 防卡死）。"""
    timeout = timeout_seconds or settings.parse_timeout_seconds
    db = SessionLocal()
    try:
        cutoff = datetime.now().timestamp() - timeout
        rows = db.scalars(
            select(ParseTask).where(ParseTask.status == "处理中")
        ).all()
        cleaned = 0
        for task in rows:
            if task.create_time.timestamp() < cutoff:
                task.status = "失败"
                task.fail_msg = "解析任务超时"
                task.finish_time = datetime.now()
                doc = db.get(KnowledgeDoc, task.doc_id)
                if doc is not None and doc.status == "处理中":
                    doc.status = "失败"
                    doc.fail_msg = "解析任务超时"
                cleaned += 1
        db.commit()
        return cleaned
    finally:
        db.close()

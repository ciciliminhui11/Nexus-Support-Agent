"""删除级联：原始文件 + MySQL 元数据 + 向量切片（FR-008 事务性级联）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeDoc, ParseTask
from app.services.knowledge import file_store
from app.vector_store import chroma


def delete_document(db: Session, doc_id: int) -> bool:
    doc = db.get(KnowledgeDoc, doc_id)
    if doc is None:
        return False

    # 取消进行中的解析任务（终态已取消，向量回滚由 cleaner 完成）
    running = db.scalars(
        select(ParseTask).where(
            ParseTask.doc_id == doc_id, ParseTask.status == "处理中"
        )
    ).all()
    for task in running:
        task.status = "已取消"
        task.finish_time = datetime.now()

    # 级联：向量 + 文件 + 元数据 + 解析任务（MySQL 由 FK ON DELETE CASCADE
    # 兜底；这里显式删除，保证 SQLite 等未启用 FK 级联的环境行为一致）
    chroma.delete_by_doc_id(doc_id)
    file_store.delete_file(doc.file_path)
    db.execute(delete(ParseTask).where(ParseTask.doc_id == doc_id))
    db.delete(doc)
    db.commit()
    return True

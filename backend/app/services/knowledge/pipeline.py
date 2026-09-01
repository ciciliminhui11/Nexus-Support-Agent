"""文档处理流水线（后台任务入口）。

解析 → 切分 → 向量化 → 写入 Chroma → 文档状态就绪；
任一环节失败：回滚已写入切片 + 文档/任务状态置失败（FR-011 整份失败回滚）。
并发删除（处理中文档被删）时：向量回滚 + 任务置已取消，不残留半成品。

v3 由 FastAPI `BackgroundTasks` 进程内执行的普通函数（非 Celery task），见 research §1。
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
from app.services.tracing.events import (
    ERROR_MAX_CHARS,
    STAGE_DOC_EMBED_INGEST,
    STAGE_DOC_LOAD,
    STAGE_DOC_PARSE,
    STAGE_DOC_ROLLBACK,
    STAGE_DOC_SPLIT,
    STAGE_DOC_STATUS,
    STATUS_ERROR,
    STATUS_OK,
    TRACE_TYPE_INGEST,
)
from app.services.tracing.tracer import Tracer
from app.vector_store import chroma

logger = get_logger(__name__)


def _rollback_chunks(doc_id: int) -> None:
    """回滚已写入 Chroma 的全部切片。

    删除操作自身异常单独捕获并输出 ERROR 告警（向量残留 = 半成品，必须可观测）；
    无论删除成功与否，MySQL 状态由调用方继续置终态（FR-011）。
    """
    try:
        chroma.delete_by_doc_id(doc_id, raise_on_error=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("文档 %s 向量回滚失败（存在向量残留，需清扫兜底）: %s", doc_id, exc)


def process_document(doc_id: int) -> None:
    # 008 埋点（FR-001）：创建 ingest 链路 Tracer，各阶段 span + 终态 meta；
    # trace_enabled=false 时 Tracer 全程短路，零开销（FR-010）。
    tracer = Tracer(TRACE_TYPE_INGEST, doc_id=doc_id)
    db = SessionLocal()
    try:
        # ---------- doc_load：读取文档 + 防并发竞态检查 ----------
        with tracer.span(STAGE_DOC_LOAD):
            doc = db.get(KnowledgeDoc, doc_id)
            if doc is None:
                return  # 已被清理（无实际处理，不产出 trace）
            if doc.status == "处理中":
                # 防并发竞态：已有进行中的 ParseTask 即视为该文档正在被处理，拒绝重复触发。
                # 首次上传触发时文档虽也是“处理中”，但尚无 ParseTask，不会误拦。
                in_flight = db.scalar(
                    select(ParseTask).where(
                        ParseTask.doc_id == doc_id, ParseTask.status == "处理中"
                    )
                )
                if in_flight is not None:
                    logger.warning("文档 %s 已有进行中的解析任务，拒绝重复触发", doc_id)
                    return
            tracer.doc_name = doc.doc_name
        task = ParseTask(doc_id=doc_id, status="处理中")
        db.add(task)
        db.commit()
        db.refresh(task)
        try:
            with tracer.span(STAGE_DOC_PARSE) as detail:
                text = parser.parse_text(doc.file_path)
                detail["chars"] = len(text)
            client = get_embedding_client()
            # T012：markdown 标题切分 / txt 语义断点（txt 二次切分需 embedding client）
            semantic_split = bool(
                not doc.doc_name.lower().endswith((".md", ".markdown"))
            )
            with tracer.span(STAGE_DOC_SPLIT) as detail:
                chunks = splitter.split_document(
                    doc.doc_name, text, settings.chunk_size, settings.chunk_overlap,
                    embed_client=client,
                )
                if not chunks:
                    raise ValueError("文档切分后无有效内容")
                detail["chunks"] = len(chunks)
                detail["semantic_split"] = semantic_split
            # T013：标题注入 + 扩展元数据（source_file/version_date 取自文档记录）
            with tracer.span(STAGE_DOC_EMBED_INGEST) as detail:
                ingest_chunks(
                    doc_id, chunks, client, settings.embedding_batch_size,
                    source_file=doc.doc_name,
                    version_date=doc.upload_time,
                    stats=detail,
                )

            # 重新加载，校验文档是否被并发删除。
            # 注意 identity map：doc 已在会话内加载过，普通 get 命中缓存返回陈旧对象，
            # 必须 populate_existing 强制走 DB，行已删则返回 None。
            with tracer.span(STAGE_DOC_STATUS) as detail:
                doc = db.get(KnowledgeDoc, doc_id, populate_existing=True)
                if doc is None:
                    # 并发删除取消路径：向量回滚 + 任务已取消，不残留“处理中”误导
                    _rollback_chunks(doc_id)
                    task.status = "已取消"
                    task.finish_time = datetime.now()
                    db.commit()
                    detail["status"] = "已取消"
                    detail["rollback"] = True
                    tracer.finish(status=STATUS_OK)
                    return
                doc.status = "就绪"
                doc.fail_msg = None
                task.status = "成功"
                detail["status"] = "就绪"
            task.finish_time = datetime.now()
            db.commit()
            tracer.finish(status=STATUS_OK)
        except Exception as exc:  # noqa: BLE001  任何环节失败 → 整份失败
            logger.exception("文档 %s 处理失败", doc_id)
            _rollback_chunks(doc_id)  # 回滚已写入切片（删除异常已内部告警）
            with tracer.span(STAGE_DOC_ROLLBACK) as detail:
                detail["reason"] = str(exc)[:ERROR_MAX_CHARS]
            # 无论向量回滚成功与否，MySQL 文档/任务必须置失败（FR-011）
            doc = db.get(KnowledgeDoc, doc_id, populate_existing=True)
            with tracer.span(STAGE_DOC_STATUS) as detail:
                if doc is not None:
                    doc.status = "失败"
                    doc.fail_msg = str(exc)[:1000]
                task.status = "失败"
                task.fail_msg = str(exc)[:1000]
                detail["status"] = "失败"
            task.finish_time = datetime.now()
            db.commit()
            tracer.finish(status=STATUS_ERROR, error=str(exc)[:ERROR_MAX_CHARS])
    except Exception:
        db.rollback()
        logger.exception("处理文档 %s 时数据库异常", doc_id)
        tracer.finish(status=STATUS_ERROR, error="数据库异常")
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

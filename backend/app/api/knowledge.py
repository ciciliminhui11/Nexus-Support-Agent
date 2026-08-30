"""知识库接口：上传 / 列表 / 详情 / 删除（全部管理员专属）。"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.async_tasks import run_in_background
from app.core.exceptions import NotFoundError
from app.db.models import KnowledgeDoc, User
from app.db.session import get_db
from app.schemas.knowledge import (
    KnowledgeDocItem,
    KnowledgeListResponse,
    UploadResponse,
)
from app.services.config_service import get_config_value
from app.services.knowledge import file_store, validator
from app.services.knowledge import cleaner
from app.services.knowledge import pipeline
from app.config import settings

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _doc_item(doc: KnowledgeDoc) -> KnowledgeDocItem:
    return KnowledgeDocItem(
        doc_id=doc.id,
        doc_name=doc.doc_name,
        status=doc.status,
        upload_time=doc.upload_time,
        fail_msg=doc.fail_msg,
    )


@router.post("/upload", status_code=202, response_model=UploadResponse)
def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UploadResponse:
    content = file.file.read()
    filename = file.filename or ""
    validator.validate_upload(filename, content)

    path = file_store.save_upload(content, filename)
    doc = KnowledgeDoc(doc_name=filename, file_path=path, status="处理中")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    run_in_background(background_tasks, pipeline.process_document, doc.id)
    return UploadResponse(
        doc_id=doc.id,
        doc_name=doc.doc_name,
        status=doc.status,
        upload_time=doc.upload_time,
    )


@router.get("/list", response_model=KnowledgeListResponse)
def list_docs(
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> KnowledgeListResponse:
    size = page_size or int(
        get_config_value(db, "session_page_size", settings.session_page_size)
    )
    total = db.scalar(select(func.count()).select_from(KnowledgeDoc)) or 0
    items = (
        db.scalars(
            select(KnowledgeDoc)
            .order_by(KnowledgeDoc.upload_time.desc(), KnowledgeDoc.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .all()
    )
    return KnowledgeListResponse(total=total, items=[_doc_item(d) for d in items])


@router.get("/{doc_id}", response_model=KnowledgeDocItem)
def doc_detail(
    doc_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> KnowledgeDocItem:
    doc = db.get(KnowledgeDoc, doc_id)
    if doc is None:
        raise NotFoundError(code="doc_not_found", message="文档不存在")
    return _doc_item(doc)


@router.delete("/{doc_id}", status_code=204)
def delete_doc(
    doc_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    if not cleaner.delete_document(db, doc_id):
        raise NotFoundError(code="doc_not_found", message="文档不存在")
    return None

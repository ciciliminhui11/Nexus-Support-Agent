"""006 意图识别联调接口：POST /api/intent/debug（管理员专属）。

透出三层漏斗各层原始结果与降级原因（含模型 429/超时），供联调校准词库、
模板与模型配置；空/超长 query 返回 400 invalid_query。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.exceptions import ValidationError
from app.db.models import User
from app.db.session import get_db
from app.intent.service import debug_recognize
from app.schemas.intent import IntentDebugRequest

router = APIRouter(prefix="/api/intent", tags=["intent"])


@router.post("/debug")
def intent_debug(
    body: IntentDebugRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    query = body.query.strip()
    if not query:
        raise ValidationError(code="invalid_query", message="query 不能为空")
    if len(query) > 500:
        raise ValidationError(code="invalid_query", message="query 超过 500 字上限")
    return debug_recognize(db, query)

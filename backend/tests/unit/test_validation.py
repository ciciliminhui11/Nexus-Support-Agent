"""RAG 入口校验：长度边界（FR-001）与配额原子计数（FR-002）。"""
from __future__ import annotations

import pytest

from app.core.exceptions import BizError, QuotaExceededError
from app.db.models import UserQuotaDaily
from app.services.validation import consume_quota, validate_question


# ---------- FR-001 长度 ----------

def test_question_500_boundary_passes():
    validate_question("问" * 500)


def test_question_501_rejected():
    with pytest.raises(BizError) as ei:
        validate_question("问" * 501)
    assert ei.value.code == "question_too_long"


def test_question_empty_rejected():
    for q in ("", "   ", "\n\t"):
        with pytest.raises(BizError) as ei:
            validate_question(q)
        assert ei.value.code == "question_empty"


# ---------- FR-002 配额 ----------

def test_quota_first_question_consumes(db):
    assert consume_quota(db, 1, limit=100) == 1
    assert consume_quota(db, 1, limit=100) == 2


def test_quota_reaches_limit_then_rejects(db):
    for _ in range(3):
        consume_quota(db, 1, limit=3)
    with pytest.raises(QuotaExceededError) as ei:
        consume_quota(db, 1, limit=3)
    assert ei.value.code == "quota_exceeded"
    # 计数不被超额消费
    row = db.query(UserQuotaDaily).filter(UserQuotaDaily.user_id == 1).one()
    assert row.count == 3


def test_quota_isolated_per_user(db):
    consume_quota(db, 1, limit=2)
    consume_quota(db, 1, limit=2)
    assert consume_quota(db, 2, limit=2) == 1

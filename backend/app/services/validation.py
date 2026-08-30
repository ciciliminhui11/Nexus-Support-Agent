"""RAG 问答入口校验：问题长度（FR-001）与每日配额（FR-002）。

配额计数要点（research §10）：校验与递增在同一事务内完成；
采用 `UPDATE ... SET count = count + 1 WHERE count < :limit` 原子操作，
并发到达时不会重复计数。首条提问（无当日记录）走 INSERT。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import BizError, QuotaExceededError
from app.db.models import UserQuotaDaily

QUESTION_MAX_LENGTH = 500


def validate_question(question: str) -> None:
    """FR-001：空 / 超长拒绝（边界 500 通过、501 拒绝），不进入生成。"""
    if not question or not question.strip():
        raise BizError(code="question_empty", message="问题不能为空")
    if len(question) > QUESTION_MAX_LENGTH:
        raise BizError(code="question_too_long", message="问题长度不能超过 500 字")


def consume_quota(db: Session, user_id: int, limit: int) -> int:
    """FR-002：校验 + 原子递增配额，返回递增后的当日已用次数。

    达到上限抛 `QuotaExceededError`（HTTP 429 / code=quota_exceeded）。
    MySQL 生产依赖单行 `UPDATE ... WHERE count < :limit` 的原子性；
    SQLite 测试为单连接无并发，行为一致。
    """
    today = date.today()
    result = db.execute(
        update(UserQuotaDaily)
        .where(
            UserQuotaDaily.user_id == user_id,
            UserQuotaDaily.stat_date == today,
            UserQuotaDaily.count < limit,
        )
        .values(count=UserQuotaDaily.count + 1)
    )
    if result.rowcount == 1:
        db.commit()
        return db.scalar(
            select(UserQuotaDaily.count).where(
                UserQuotaDaily.user_id == user_id,
                UserQuotaDaily.stat_date == today,
            )
        )

    # rowcount == 0：要么当日无记录（首次提问），要么已达上限
    row = db.scalar(
        select(UserQuotaDaily).where(
            UserQuotaDaily.user_id == user_id,
            UserQuotaDaily.stat_date == today,
        )
    )
    if row is None:
        db.add(UserQuotaDaily(user_id=user_id, stat_date=today, count=1))
        db.commit()
        return 1
    db.rollback()  # 放弃未生效的 UPDATE
    raise QuotaExceededError(message="今日提问次数已用尽，请明天再试")

"""统一数据模型（MySQL 8.0 目标，SQLAlchemy 2.0）。

各表结构与 specs/*/data-model.md 保持一致；生产建表使用
`backend/数据库初始化脚本/init.sql`（含索引），测试可用 `create_all()` 便捷建表。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _now() -> datetime:
    return datetime.now()


# 主键类型：MySQL 用 BIGINT；SQLite 下退化为 INTEGER（只有 INTEGER PRIMARY KEY
# 才作为 rowid 别名支持自增，BIGINT 主键在 SQLite 不会自增）
_PK = BigInteger().with_variant(Integer, "sqlite")


# ---------- 003 用户鉴权 ----------
class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    account_identifier: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    account_type: Mapped[str] = mapped_column(
        Enum("phone", "email", name="user_account_type"), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("user", "admin", name="user_role"), nullable=False, default="user"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class UserQuotaDaily(Base):
    """每日提问计数（001 负责递增，003 提供查询展示）。"""

    __tablename__ = "user_quota_daily"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id"), nullable=False
    )
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "stat_date", name="uq_user_quota_daily"),
    )


# ---------- 004 会话与消息 ----------
class ChatSession(Base):
    """会话（表名 session）。"""

    __tablename__ = "session"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        Index("ix_session_user_time", "user_id", "create_time"),
    )


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("session.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Enum("user", "ai", name="message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reference_source: Mapped[list | None] = mapped_column(JSON, nullable=True)
    intent_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        Index("ix_message_session_time_id", "session_id", "create_time", "id"),
    )


# ---------- 002 知识库 ----------
class KnowledgeDoc(Base):
    __tablename__ = "knowledge_doc"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    doc_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("处理中", "就绪", "失败", name="knowledge_status"),
        nullable=False,
        default="处理中",
    )
    fail_msg: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        Index("ix_knowledge_status", "status"),
        Index("ix_knowledge_upload_time", "upload_time"),
    )


class ParseTask(Base):
    __tablename__ = "parse_task"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_doc.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum("处理中", "成功", "失败", "已取消", name="parsetask_status"),
        nullable=False,
        default="处理中",
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    finish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fail_msg: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (Index("ix_parsetask_status", "status"),)


# ---------- 005 用户反馈 ----------
class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("message.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id"), nullable=False
    )
    feedback_type: Mapped[str] = mapped_column(
        Enum("like", "dislike", name="feedback_type"), nullable=False
    )
    feedback_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_feedback_message_user"),
    )


# ---------- 008 链路埋点 ----------
class TraceEvent(Base):
    """链路埋点 span（追加式观测表）。

    一次链路（文档入库 / 问答）的每个阶段平铺为一行，用 `trace_id` 关联；
    `seq` 保持同 trace 内顺序（meta 行 seq=0 携带 question/doc_name 上下文）。
    观测数据可丢：落库失败只记日志不重试，不影响业务链路（FR-003/FR-010）。
    """

    __tablename__ = "trace_event"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_type: Mapped[str] = mapped_column(String(20), nullable=False)  # ingest | chat
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ok | error | skipped
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    doc_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    __table_args__ = (
        Index("ix_trace_trace_id", "trace_id"),
        Index("ix_trace_type_time", "trace_type", "create_time"),
        Index("ix_trace_session", "session_id"),
    )


# ---------- 公共：运行时配置 ----------
class SystemConfig(Base):
    """运行时热调参数（key-value）。未配置的 key 回落到 app/config.py 默认值。"""

    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_now, onupdate=_now
    )

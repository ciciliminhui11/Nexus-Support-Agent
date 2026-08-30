"""SQLAlchemy engine / Session 管理。

- 生产：MySQL 8.0（`settings.database_url`，经 .env 配置）。
- 测试：可将 `DATABASE_URL` 指为 `sqlite://` 等以快速跑通；连接串在
  `tests/conftest.py` 中以引擎覆盖方式隔离。
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        # 内存库用 StaticPool 保证所有连接共享同一库（默认 QueuePool 会各自独立建库）
        is_memory = ":memory:" in url or "mode=memory" in url
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            future=True,
            **({"poolclass": StaticPool} if is_memory else {}),
        )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
        future=True,
    )


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话（请求结束自动回滚未提交事务并关闭）。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_all() -> None:
    """按模型元数据建表（开发/测试便捷入口；生产使用 数据库初始化脚本/init.sql）。"""
    from app.db import models  # noqa: F401  确保模型注册

    Base.metadata.create_all(bind=engine)

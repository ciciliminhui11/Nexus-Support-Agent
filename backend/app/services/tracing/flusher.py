"""后台批量落库任务（FR-003/FR-011）。

生命周期与 `main.py` 的僵尸清扫器同构：随应用 lifespan 启动 `asyncio.create_task`，
周期或缓冲达阈值触发 flush（DB 写经 `asyncio.to_thread` 丢到 anyio 线程池），
关停时在 task 内兜底 flush 剩余（进程重启不丢观测数据）。见 research.md §2。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import delete

from app.config import settings
from app.core.logging import get_logger
from app.db.models import TraceEvent
from app.db.session import SessionLocal
from app.services.tracing.collector import collector

logger = get_logger(__name__)

# 保留期清理节流：每约 600s（10 分钟）执行一次 purge_old，避免每周期都查表
_PURGE_EVERY_SECONDS = 600


async def trace_flush_task(stop: asyncio.Event) -> None:
    """周期 / 达缓冲阈值触发 flush（research §2）；`stop` 置位退出并兜底 flush 剩余。

    每个循环周期（`trace_flush_interval_seconds`）检查缓冲，有积压即批量落库；
    保留期清理（FR-011）按 `_PURGE_EVERY_SECONDS` 节流，不随每次 flush 跑。
    """
    purge_elapsed = 0
    while not stop.is_set():
        try:
            if collector.pending() > 0:
                await asyncio.to_thread(collector.flush)
        except Exception as exc:  # noqa: BLE001  刷写失败不中断循环
            logger.exception("trace flush 失败（忽略）: %s", exc)
        # 保留期清理：每累计约 10 分钟一次（interval 秒/轮折算）
        purge_elapsed += max(settings.trace_flush_interval_seconds, 1)
        if settings.trace_retention_days > 0 and purge_elapsed >= _PURGE_EVERY_SECONDS:
            purge_elapsed = 0
            try:
                await asyncio.to_thread(purge_old)
            except Exception as exc:  # noqa: BLE001  清理失败不中断循环
                logger.exception("trace 保留期清理失败（忽略）: %s", exc)
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=settings.trace_flush_interval_seconds
            )
        except TimeoutError:
            continue  # 间隔到了，回到循环顶部再判缓冲
        except asyncio.CancelledError:
            break  # 应用关闭触发取消
    # 关停兜底：flush 剩余
    try:
        await asyncio.to_thread(collector.flush)
    except Exception as exc:  # noqa: BLE001
        logger.exception("trace 关停 flush 失败（忽略）: %s", exc)


def purge_old() -> int:
    """按 `trace_retention_days` 清理过期 span；<=0 表示不清理。返回清理条数。"""
    days = settings.trace_retention_days
    if days <= 0:
        return 0
    cutoff = datetime.now() - timedelta(days=days)
    db = SessionLocal()
    try:
        result = db.execute(
            delete(TraceEvent).where(TraceEvent.create_time < cutoff)
        )
        db.commit()
        return int(result.rowcount or 0)
    except Exception as exc:  # noqa: BLE001  清理失败不阻断
        db.rollback()
        logger.exception("trace 清理失败（忽略）: %s", exc)
        return 0
    finally:
        db.close()

"""008 后台 flush 任务单测：关停兜底 flush / 保留期清理。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from app.config import settings
from app.db.models import TraceEvent
from app.services.tracing.collector import collector
from app.services.tracing.flusher import purge_old, trace_flush_task
from app.services.tracing.tracer import Tracer


def test_shutdown_flush_drains(db, monkeypatch):
    """stop 已置位时任务立即退出循环并兜底 flush 缓冲到库。"""
    monkeypatch.setattr(settings, "trace_flush_interval_seconds", 3600)
    collector.reset()
    t = Tracer("chat", session_id=1, user_id=1, question="q")
    with t.span("intent"):
        pass
    t.finish()
    assert collector.pending() > 0

    async def _run():
        stop = asyncio.Event()
        stop.set()  # 立即退出 while 循环，走关停兜底 flush
        await trace_flush_task(stop)

    asyncio.run(_run())
    assert collector.pending() == 0
    assert db.query(TraceEvent).count() >= 2  # meta + intent


def test_purge_old_respects_retention_zero(db, monkeypatch):
    monkeypatch.setattr(settings, "trace_retention_days", 0)
    assert purge_old() == 0  # <=0 不清理


def test_purge_old_deletes_expired(db, monkeypatch):
    monkeypatch.setattr(settings, "trace_retention_days", 1)
    collector.reset()
    # 造两条过期记录（create_time 直接写入过去）
    now = datetime.now()
    stale = now - timedelta(days=10)
    db.add_all(
        [
            TraceEvent(
                trace_id="old",
                trace_type="chat",
                stage="meta",
                seq=0,
                status="ok",
                start_at=stale,
                create_time=stale,
            ),
            TraceEvent(
                trace_id="new",
                trace_type="chat",
                stage="meta",
                seq=0,
                status="ok",
                start_at=now,
            ),
        ]
    )
    db.commit()
    assert db.query(TraceEvent).count() == 2
    cleaned = purge_old()  # 内部自开 SessionLocal，写同一 StaticPool 连接
    assert cleaned == 1
    remaining = db.query(TraceEvent.trace_id).all()
    assert [r[0] for r in remaining] == ["new"]


def test_flush_task_purges_expired(db, monkeypatch):
    """任务周期内按保留期清理过期 span（FR-011 接线）。"""
    from app.services.tracing import flusher

    monkeypatch.setattr(settings, "trace_flush_interval_seconds", 0.01)
    monkeypatch.setattr(settings, "trace_retention_days", 1)
    monkeypatch.setattr(flusher, "_PURGE_EVERY_SECONDS", 0.01)  # 测试节流立即触发
    stale = datetime.now() - timedelta(days=10)
    db.add(
        TraceEvent(
            trace_id="old",
            trace_type="chat",
            stage="meta",
            seq=0,
            status="ok",
            start_at=stale,
            create_time=stale,
        )
    )
    db.commit()
    assert db.query(TraceEvent).count() == 1

    async def _run_loop():
        stop = asyncio.Event()
        task = asyncio.create_task(trace_flush_task(stop))
        await asyncio.sleep(0.05)
        stop.set()
        await task

    asyncio.run(_run_loop())
    assert db.query(TraceEvent).count() == 0


def test_flush_task_batch_flush(db, monkeypatch):
    """缓冲达阈值时提前 flush。"""
    monkeypatch.setattr(settings, "trace_buffer_size", 1)
    monkeypatch.setattr(settings, "trace_flush_interval_seconds", 3600)
    collector.reset()
    t = Tracer("chat", session_id=2, user_id=2, question="q")
    with t.span("intent"):
        pass
    t.finish()
    assert collector.pending() >= 1

    async def _run_loop():
        stop = asyncio.Event()
        task = asyncio.create_task(trace_flush_task(stop))
        # 循环首轮即可达阈值触发 flush，随后停在 stop.wait()
        await asyncio.sleep(0.05)
        stop.set()
        await task

    asyncio.run(_run_loop())
    assert collector.pending() == 0
    assert db.query(TraceEvent).count() >= 2

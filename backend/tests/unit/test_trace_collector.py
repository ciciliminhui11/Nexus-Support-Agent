"""008 采集器单测：缓冲 / drain / reset / 批量落库 / 失败不抛。"""
from __future__ import annotations

from datetime import datetime

import importlib
import pytest

from app.db.models import TraceEvent
from app.services.tracing.collector import Collector

# `app/services/tracing/__init__.py` 的 `from ...collector import collector`
# 会把包属性 `collector` 遮蔽为实例，故用 importlib 取真实子模块。
collector_module = importlib.import_module("app.services.tracing.collector")


@pytest.fixture()
def c():
    return Collector()


def test_add_pending_drain_reset(c):
    c.add({"trace_id": "a", "stage": "x"})
    c.add({"trace_id": "b", "stage": "y"})
    assert c.pending() == 2
    events = c.drain()
    assert len(events) == 2
    assert c.pending() == 0
    # 再 drain 幂等返回空
    assert c.drain() == []
    # reset 丢弃
    c.add({"trace_id": "c", "stage": "z"})
    c.reset()
    assert c.pending() == 0


def test_flush_empty_returns_zero(c):
    assert c.flush() == 0


def test_flush_with_session_persists_rows(c, db):
    c.add(
        {
            "trace_id": "trace-1",
            "trace_type": "chat",
            "stage": "intent",
            "seq": 1,
            "status": "ok",
            "start_at": datetime.now(),
            "duration_ms": 5,
            "detail": {"layer": "rule"},
            "session_id": 7,
            "user_id": 3,
        }
    )
    assert c.flush(db) == 1
    rows = db.query(TraceEvent).all()
    assert len(rows) == 1
    assert rows[0].trace_id == "trace-1"
    assert rows[0].stage == "intent"
    assert rows[0].detail == {"layer": "rule"}
    assert rows[0].session_id == 7


def test_flush_failure_does_not_raise(c, db, monkeypatch):
    """落库失败只记日志，不向调用方抛异常（观测数据可丢，FR-010）。"""
    c.add({"trace_id": "boom", "stage": "x", "seq": 0, "status": "ok"})

    def _raise(**kwargs):  # noqa: ARG001
        raise RuntimeError("db down")

    monkeypatch.setattr(collector_module, "TraceEvent", _raise)
    # 不应抛异常
    assert c.flush(db) == 0

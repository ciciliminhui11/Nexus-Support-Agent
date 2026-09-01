"""进程级线程安全缓冲 + 批量落库。

埋点记录可能来自 threadpool 线程（BackgroundTasks / asyncio.to_thread）、事件循环
或测试线程，缓冲区必须加锁；`add` 只做内存 append（微秒级），不阻塞任何业务链路
（FR-003）。落库失败只记日志不重试——观测数据可丢，防坏数据堵死队列（FR-010）。
"""
from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import TraceEvent
from app.db.session import SessionLocal

logger = get_logger(__name__)


class Collector:
    """线程安全缓冲。`flush(db=None)` 批量落库，db 为空则自开 `SessionLocal()`。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buffer: list[dict] = []

    def add(self, event: dict) -> None:
        """推入缓冲（绝不阻塞；异常静默记录）。"""
        try:
            with self._lock:
                self._buffer.append(event)
        except Exception:  # noqa: BLE001  观测失败不影响业务
            logger.exception("trace 入缓冲失败（忽略）")

    def pending(self) -> int:
        with self._lock:
            return len(self._buffer)

    def drain(self) -> list[dict]:
        """原子取走并清空缓冲（幂等安全：并发 drain 返回各自份额）。"""
        with self._lock:
            events = self._buffer
            self._buffer = []
            return events

    def reset(self) -> None:
        """丢弃缓冲（测试隔离用）。"""
        self.drain()

    def flush(self, db: Session | None = None) -> int:
        """drain 后批量落库，返回成功落库条数。

        失败只记日志不重试（观测数据可丢）；测试传入 `db` 复用测试会话保证
        同线程串行、结果立即可见（research §3）。
        """
        events = self.drain()
        if not events:
            return 0
        try:
            if db is not None:
                db.add_all([TraceEvent(**e) for e in events])
                db.commit()
            else:
                own = SessionLocal()
                try:
                    own.add_all([TraceEvent(**e) for e in events])
                    own.commit()
                finally:
                    own.close()
        except Exception:  # noqa: BLE001
            logger.exception("trace 落库失败（丢弃 %s 条）", len(events))
            return 0
        return len(events)


collector = Collector()

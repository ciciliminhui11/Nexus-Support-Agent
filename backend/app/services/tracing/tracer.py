"""Tracer：一次链路操作的全部 span 收集 + 控制台输出。

- `span(stage)` 同步 contextmanager：退出时算 duration；span 内异常标 error 并继续上抛；
- `finish()` 幂等：拼 meta 行(seq=0) + 全部 span 批量推入 collector，并按
  `trace_console_log` 打印可读链路块；
- `trace_enabled=False` 时全程短路（span 空操作、finish 直接返回），零开销（FR-010）。

埋点只做内存操作，不触碰 DB / 网络，因此可安全包裹在 async 生成器里不阻塞 SSE（FR-004）。
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app.config import settings
from app.core.logging import get_logger
from app.services.tracing.collector import collector
from app.services.tracing.console import render_trace_block
from app.services.tracing.events import (
    ERROR_DB_MAX_CHARS,
    ERROR_MAX_CHARS,
    QUESTION_MAX_CHARS,
    STAGE_META,
    STATUS_ERROR,
    STATUS_OK,
    TRACE_TYPE_CHAT,
    TRACE_TYPE_INGEST,
    truncate_text,
)

logger = get_logger(__name__)


class Tracer:
    """一次链路操作的观测句柄（doc_id/session_id 等关联 id 由构造传入，全 span 共享）。"""

    def __init__(
        self,
        trace_type: str,
        *,
        doc_id: int | None = None,
        session_id: int | None = None,
        user_id: int | None = None,
        message_id: int | None = None,
        question: str | None = None,
        doc_name: str | None = None,
    ) -> None:
        if trace_type not in (TRACE_TYPE_INGEST, TRACE_TYPE_CHAT):
            raise ValueError(f"不支持的 trace_type: {trace_type!r}")
        self.trace_id = uuid.uuid4().hex
        self.trace_type = trace_type
        self.doc_id = doc_id
        self.session_id = session_id
        self.user_id = user_id
        self.message_id = message_id
        self.question = truncate_text(question, QUESTION_MAX_CHARS)
        self.doc_name = doc_name
        self._spans: list[dict] = []
        self._finished = False
        self._enabled = bool(settings.trace_enabled)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @contextmanager
    def span(self, stage: str):
        """计时 span。yield 出可变 detail dict（调用方中途塞字段，如 first_token_ms）。

        异常：标 error、记录错误消息并继续上抛（不吞业务异常）。
        """
        if not self._enabled:
            yield {}
            return
        sp: dict[str, Any] = {
            "stage": stage,
            "detail": {},
            "start_at": datetime.now(),
            "t": time.monotonic(),
            "status": STATUS_OK,
        }
        self._spans.append(sp)
        try:
            yield sp["detail"]
        except Exception as exc:  # noqa: BLE001
            sp["status"] = STATUS_ERROR
            sp["error"] = str(exc)[:ERROR_MAX_CHARS]
            raise
        finally:
            sp["duration_ms"] = int((time.monotonic() - sp["t"]) * 1000)

    def mark_span_error(self, stage: str, error: str | None = None) -> None:
        """把业务内已捕获的异常 span 显式标 error（如 LLM 流式错误被就地捕获）。

        区别于 `span()` 自动标错：异常未逃出 span 上下文时，由调用方主动标记，
        保证 span 级状态与 detail 的 error_code 一致（FR-008）。
        """
        if not self._enabled:
            return
        for sp in self._spans:
            if sp["stage"] == stage:
                sp["status"] = STATUS_ERROR
                if error:
                    sp["error"] = error[:ERROR_MAX_CHARS]
                return

    def finish(self, status: str = STATUS_OK, error: str | None = None, **meta) -> None:
        """幂等收尾：meta 行 + 全部 span 推入 collector，并按开关打印链路块。"""
        if not self._enabled or self._finished:
            return
        self._finished = True
        error = truncate_text(error, ERROR_DB_MAX_CHARS)

        meta_detail: dict[str, Any] = {"trace_status": status}
        if self.question is not None:
            meta_detail["question"] = self.question
        if self.doc_name is not None:
            meta_detail["doc_name"] = self.doc_name
        meta_detail.update(meta)

        events = [
            {
                "trace_id": self.trace_id,
                "trace_type": self.trace_type,
                "stage": STAGE_META,
                "seq": 0,
                "status": status,
                "start_at": datetime.now(),
                "duration_ms": None,
                "detail": meta_detail,
                "doc_id": self.doc_id,
                "session_id": self.session_id,
                "user_id": self.user_id,
                "message_id": self.message_id,
                "error": error,
            }
        ]
        for i, sp in enumerate(self._spans, start=1):
            if "duration_ms" not in sp:
                # 允许在 span 未退出时 finish（如并发删除取消路径提前 return），
                # 用 span 内记录的单调时钟兜底计算耗时
                sp["duration_ms"] = int((time.monotonic() - sp["t"]) * 1000)
            events.append(
                {
                    "trace_id": self.trace_id,
                    "trace_type": self.trace_type,
                    "stage": sp["stage"],
                    "seq": i,
                    "status": sp["status"],
                    "start_at": sp["start_at"],
                    "duration_ms": sp["duration_ms"],
                    "detail": sp["detail"] or None,
                    "doc_id": self.doc_id,
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "message_id": self.message_id,
                    "error": sp.get("error"),
                }
            )

        for e in events:
            collector.add(e)

        if settings.trace_console_log:
            try:
                logger.info("\n%s", render_trace_block(self, events))
            except Exception:  # noqa: BLE001  打印失败不影响链路
                logger.exception("trace 控制台输出失败（忽略）")

    def is_finished(self) -> bool:
        return self._finished

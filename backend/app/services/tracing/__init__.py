"""链路埋点（008）：Tracer 采集 + Collector 异步落库 + 控制台输出。

对外入口：`Tracer`（每操作一个实例）、全局 `collector`（缓冲/落库）、
`trace_flush_task`/`purge_old`（后台任务与清理）。
"""
from app.services.tracing.collector import Collector, collector
from app.services.tracing.flusher import purge_old, trace_flush_task
from app.services.tracing.tracer import Tracer

__all__ = ["Collector", "collector", "Tracer", "trace_flush_task", "purge_old"]

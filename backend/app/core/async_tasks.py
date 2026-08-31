"""后台任务抽象。

v3 使用 FastAPI `BackgroundTasks` 进程内执行异步任务，API 层经本模块提交任务。
`func` 为普通可调用对象（如 `pipeline.process_document`），经 `BackgroundTasks.add_task`
在 Web 进程同事件循环内后台执行（零外部依赖，免 Redis/Celery，见 research §1）。

未来如需跨进程扩展（多 worker / 任务队列），可在此薄接口切换提交方式为 Celery
`.delay()`，上层 upload 接口不感知切换。
"""
from __future__ import annotations

from fastapi import BackgroundTasks


def run_in_background(
    background_tasks: BackgroundTasks, func, *args, **kwargs
) -> None:
    """提交后台任务（`background_tasks.add_task(func, *args, **kwargs)`）。

    由调用方（上传接口）注入 `background_tasks: BackgroundTasks` 后传入；任务进程内
    后台执行，HTTP 先返回（FR-002）。测试环境由 TestClient 在响应后同步执行。
    """
    background_tasks.add_task(func, *args, **kwargs)
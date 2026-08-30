"""后台任务抽象。

v1 使用 FastAPI `BackgroundTasks`（响应返回后执行）；大规模文档场景切换
Celery 时仅替换本模块（将 func/args 入队），业务代码不变。
"""
from __future__ import annotations

from fastapi import BackgroundTasks


def run_in_background(background_tasks: BackgroundTasks, func, *args, **kwargs) -> None:
    background_tasks.add_task(func, *args, **kwargs)

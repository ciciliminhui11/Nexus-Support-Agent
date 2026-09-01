"""FastAPI 应用装配：中间件、全局异常处理、路由注册、启动初始化。"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api import (
    admin,
    auth,
    chat,
    feedback,
    intent_debug,
    knowledge,
    session as session_api,
    trace as trace_api,
)
from app.config import settings
from app.core.exceptions import BizError
from app.core.logging import get_logger, setup_logging
from app.db.models import User
from app.db.session import SessionLocal, create_all

logger = get_logger(__name__)


def seed_admin() -> None:
    """启动时预置管理员：存在则置 admin 角色，不存在则按 .env 默认创建。"""
    from app.core.security import hash_password

    db = SessionLocal()
    try:
        existing = db.scalar(
            select(User).where(User.account_identifier == settings.admin_account)
        )
        if existing is not None:
            if existing.role != "admin":
                existing.role = "admin"
                db.commit()
            return
        db.add(
            User(
                account_identifier=settings.admin_account,
                account_type="email",
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
        )
        db.commit()
        logger.warning(
            "已预置管理员账号 %s（密码为 .env ADMIN_PASSWORD，生产请立即修改）",
            settings.admin_account,
        )
    finally:
        db.close()


def sweep_zombie_tasks() -> None:
    """启动时清扫僵尸解析任务（SC-004 双层兜底 · 第 1 层）。

    进程崩溃 / OOM 时 except 分支不会执行，文档可能永久停留在「处理中」。
    启动（新解释器）时把超过 `parse_timeout_seconds` 的「处理中」任务/文档置失败；
    单进程 dev 场景下重启即意味前一解释器已死，遗留「处理中」必然是僵尸。
    """
    try:
        from app.services.knowledge.pipeline import mark_stale_processing_timeout

        cleaned = mark_stale_processing_timeout()
        if cleaned:
            logger.warning("启动清扫僵尸解析任务 %s 个", cleaned)
    except Exception as exc:  # noqa: BLE001  清扫失败不应阻断启动
        logger.exception("启动清扫僵尸任务异常（忽略）: %s", exc)


def warmup_reranker() -> None:
    """启动预热 Reranker 精排模型（best-effort，research §9 进程级预热）。

    未安装 sentence-transformers 或模型加载失败时内部降级为 NoopReranker，
    不阻断启动；仅在有真实精排模型时才有实质预热效果。
    """
    try:
        from app.services.rag.reranker import warmup

        warmup()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Reranker 预热异常（忽略）: %s", exc)


async def _runtime_zombie_sweeper_task(stop: asyncio.Event) -> None:
    """运行期周期性清扫（SC-004 双层兜底 · 第 2 层）。

    进程在 lifespan 启动后长期存活期间，若某次后台任务崩溃 / 卡死（未走 except
    分支），文档可能停留「处理中」。本循环每 `parse_timeout_seconds` 秒调一次
    `mark_stale_processing_timeout()` 收敛；随应用启动/停止，无需 celery-beat/
    APScheduler/外部常驻进程（见 specs/002-knowledge-base/research.md §1）。

    注意：BackgroundTasks 为进程内执行，本循环是与它们共享同一事件循环的异步
    协程，不会并发写死；清扫本身自开 SessionLocal，与请求会话解耦。
    """
    from app.services.knowledge.pipeline import mark_stale_processing_timeout

    while not stop.is_set():
        try:
            cleaned = mark_stale_processing_timeout()
            if cleaned:
                logger.warning("运行期清扫僵尸解析任务 %s 个", cleaned)
        except Exception as exc:  # noqa: BLE001  清扫失败不应中断循环
            logger.exception("运行期清扫僵尸任务异常（下次继续）: %s", exc)
        try:
            await asyncio.sleep(settings.parse_timeout_seconds)
        except asyncio.CancelledError:
            break  # 应用关闭触发取消，正常退出循环


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    create_all()  # 启动时自动建表（含 trace_event 等 008 埋点表）
    seed_admin()
    warmup_reranker()
    sweep_zombie_tasks()
    stop = asyncio.Event()
    tasks: list[asyncio.Task] = []
    sweeper = asyncio.create_task(_runtime_zombie_sweeper_task(stop))
    tasks.append(sweeper)
    # 008 链路埋点后台落库（FR-003）：trace_flush_enabled 时启动周期 flush；
    # 与僵尸清扫器同构，随 lifespan 启停（research.md §2）。
    trace_flusher: asyncio.Task | None = None
    if settings.trace_flush_enabled:
        from app.services.tracing import trace_flush_task

        trace_flusher = asyncio.create_task(trace_flush_task(stop))
        tasks.append(trace_flusher)
        logger.info("trace 后台落库任务已启动")
    logger.info("应用启动完成（运行期僵尸清扫循环已启动）")
    yield
    # 应用关闭：停止后台协程，避免残留未取消协程告警
    stop.set()
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="AI 智能客服系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发期放开；生产按 frontend 域名收敛
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "服务内部错误，请稍后再试"},
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(session_api.router)
app.include_router(knowledge.router)
app.include_router(chat.router)
app.include_router(feedback.router)
app.include_router(intent_debug.router)
app.include_router(trace_api.router)
app.include_router(admin.router)

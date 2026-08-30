"""FastAPI 应用装配：中间件、全局异常处理、路由注册、启动初始化。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api import auth, chat, feedback, knowledge, session as session_api
from app.config import settings
from app.core.exceptions import BizError
from app.core.logging import get_logger, setup_logging
from app.db.models import User
from app.db.session import SessionLocal

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    seed_admin()
    warmup_reranker()
    logger.info("应用启动完成")
    yield


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

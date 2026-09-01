"""测试夹具。

- 数据库：SQLite 内存库（StaticPool 单连接共享），每用例重建全部表；
- 应用：TestClient 触发 lifespan（含 admin 预置）；
- 提供 make_user / auth_headers 便捷工厂。

注意：环境变量需在导入 app 前设置（engine 在导入时按 DATABASE_URL 创建）。
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests-0123456789abcdef")
os.environ.setdefault("DAILY_QUOTA_LIMIT", "100")
# Chroma 用临时内存库（EphemeralClient），不落磁盘
os.environ.setdefault("CHROMA_DIR", "")
# 006 意图识别：测试环境默认空密钥，模型层短路为 unknown，避免误触真实 API。
# 小模型层（SMALL_MODEL_*）与兜底（DEEPSEEK_*）两套凭据都要置空——用户 .env 里可能已填
# 真实密钥，若不置空会泄漏进设置/误发真实请求。需要模型层行为的用例直接 monkeypatch
# app.intent.service.classify_small / classify_fallback。
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("SMALL_MODEL_NAME", "")
os.environ.setdefault("SMALL_MODEL_API_KEY", "")
os.environ.setdefault("SMALL_MODEL_BASE_URL", "")
os.environ.setdefault("INTENT_ENABLED", "true")
# 008 链路埋点：后台 flush 在测试中彻底关掉（规避 SQLite StaticPool 单连接并发 +
# 被 drop 表写入），控制台打印与保留期清理关闭；断言落库用 `trace_flush(db)` fixture
# 显式 flush（见 research.md §3）。
os.environ.setdefault("TRACE_FLUSH_ENABLED", "false")
os.environ.setdefault("TRACE_CONSOLE_LOG", "false")
os.environ.setdefault("TRACE_RETENTION_DAYS", "0")
# 002 后台任务已改为 FastAPI BackgroundTasks 进程内执行（免 Celery/Redis）。
# TestClient 在响应后同步执行 BackgroundTasks，测试无需额外配置。

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.models import User
from app.db.session import Base, SessionLocal, engine


@pytest.fixture(autouse=True)
def _reset_login_guard():
    """登录防护为模块级内存单例，避免用例间泄漏状态。"""
    from app.core.login_guard import login_guard

    login_guard._records.clear()
    yield
    login_guard._records.clear()


@pytest.fixture(autouse=True)
def _reset_chroma():
    """重建 Chroma 单例集合，避免用例间向量数据泄漏。"""
    from app.vector_store import chroma

    chroma.reset_collection()
    yield
    chroma.reset_collection()


@pytest.fixture(autouse=True)
def _reset_intent_rules():
    """006 规则引擎与配置为进程内惰性单例，需在用例间重载避免配置状态泄漏。"""
    from app.intent.config_loader import reload_intent_config
    from app.intent.rules.engine import reload_rule_engine

    reload_rule_engine()
    reload_intent_config()
    yield
    reload_rule_engine()
    reload_intent_config()


@pytest.fixture(autouse=True)
def _reset_trace_collector():
    """008 清空采集器缓冲，避免用例间 trace 泄漏（后台 flush 已关，缓冲仅靠显式 flush）。"""
    from app.services.tracing.collector import collector

    collector.reset()
    yield
    collector.reset()


@pytest.fixture()
def trace_flush(db):
    """008 把缓冲中 span 显式落库到当前测试库（供 trace 集成测试断言）。

    纪律：先完成业务操作（其内部已 commit）再调 `_flush()`，避免测试会话有未提交
    写事务时被本调用误提交（StaticPool 单连接共享，research.md §3）。
    """
    from app.services.tracing.collector import collector

    def _flush() -> int:
        return collector.flush(db)

    return _flush


class FakeEmbeddingClient:
    """基于 token 哈希的确定性伪 embedding（相似文本余弦相似度高）。"""

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        import math
        import re
        import zlib

        def _one(text: str) -> list[float]:
            vec = [0.0] * self.dim
            for token in re.findall(r"[\w一-鿿]+", text):
                vec[zlib.crc32(token.encode("utf-8")) % self.dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            return [v / norm for v in vec]

        return [_one(t) for t in texts]


@pytest.fixture()
def fake_embedding():
    return FakeEmbeddingClient()


@pytest.fixture(autouse=True)
def _fake_embedding_client(monkeypatch, fake_embedding):
    """默认使用伪 embedding，避免依赖 Ollama 实例：
    - 知识库流水线（002）内部自取；
    - RAG 问答（001）在 api/chat.py 编排层获取后传入 retriever。
    """
    monkeypatch.setattr(
        "app.services.knowledge.pipeline.get_embedding_client",
        lambda: fake_embedding,
    )
    monkeypatch.setattr("app.api.chat.get_embedding_client", lambda: fake_embedding)
    return fake_embedding


@pytest.fixture(autouse=True)
def _tmp_upload_dir(tmp_path, monkeypatch):
    """上传文件落到用例级临时目录，避免污染工作区。"""
    from app.config import settings

    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(settings, "upload_dir", str(upload_dir))
    return str(upload_dir)


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(db, monkeypatch):
    from app.config import settings
    from app.main import app

    # 测试不加载真实 CrossEncoder 模型：1) 避免 lifespan warmup 在每条集成用例加载/导入
    # sentence-transformers（慢且污染 sys.modules）；2) 需要精排行为的用例直接
    # monkeypatch retriever.get_reranker（如 test_rag_chat_flow）。
    monkeypatch.setattr(settings, "rag_reranker_enabled", False)

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def make_user(db):
    """创建用户并返回 User 对象。"""

    def _make(
        identifier: str = "13800138000",
        account_type: str = "phone",
        password: str = "secret123",
        role: str = "user",
    ) -> User:
        u = User(
            account_identifier=identifier,
            account_type=account_type,
            password_hash=hash_password(password),
            role=role,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u

    return _make


@pytest.fixture()
def auth_headers(make_user):
    """创建用户并返回 (headers, user)。"""

    def _make(
        identifier: str = "13800138000",
        account_type: str = "phone",
        password: str = "secret123",
        role: str = "user",
    ):
        u = make_user(
            identifier=identifier, account_type=account_type,
            password=password, role=role,
        )
        token = create_access_token(u.id, u.role, u.account_type)
        return {"Authorization": f"Bearer {token}"}, u

    return _make

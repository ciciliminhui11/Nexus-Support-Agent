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
def client(db):
    from app.main import app

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

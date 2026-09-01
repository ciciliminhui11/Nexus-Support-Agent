"""Embedding 客户端抽象（可插拔后端）。

- `openai_compat`：OpenAI 兼容 `/embeddings` API（如 SiliconFlow 免费 bge-m3），
  模型 `EMBEDDING_API_MODEL`，零本地内存占用；
- `ollama`（默认）：调用 Ollama `/api/embed`，模型 `OLLAMA_EMBED_MODEL`（bge-m3）；
- `local`：sentence-transformers 本地加载（可选依赖，未安装时报清晰错误）。

外部服务不可用抛 `LLMError`，由上层转业务错误（文档标记失败）；测试用 Fake 客户端替换。
"""
from __future__ import annotations

import time

import httpx

from app.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OllamaEmbeddingClient(EmbeddingClient):
    def __init__(self, base_url: str, model: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("embeddings") or []
        except httpx.HTTPError as exc:
            raise LLMError(message=f"Embedding 服务不可用：{exc}")


class OpenAIBackendEmbeddingClient(EmbeddingClient):
    """OpenAI 兼容 Embedding API（如 SiliconFlow 免费 bge-m3）。

    POST `{base_url}/embeddings`，批量 `input` + `model`，`Authorization: Bearer` 鉴权；
    响应 `data` 按 `index` 排序还原入参顺序。测试注入 `httpx.MockTransport`。
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._transport = transport

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise LLMError(
                message="Embedding 服务不可用：未配置 EMBEDDING_API_KEY"
            )
        try:
            with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
                resp = client.post(
                    f"{self.base_url}/embeddings",
                    json={"model": self.model, "input": texts},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
            items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
            return [item["embedding"] for item in items]
        except httpx.HTTPError as exc:
            raise LLMError(message=f"Embedding 服务不可用：{exc}")


class LocalEmbeddingClient(EmbeddingClient):
    """本地 sentence-transformers（bge-m3）。首次调用时加载模型。"""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise LLMError(
                    message="本地 embedding 需要安装 sentence-transformers，"
                    "或将 EMBEDDING_BACKEND 切换为 ollama"
                )
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self._load().encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]


def get_embedding_client() -> EmbeddingClient:
    if settings.embedding_backend == "local":
        return LocalEmbeddingClient(settings.local_embed_model)
    if settings.embedding_backend == "openai_compat":
        return OpenAIBackendEmbeddingClient(
            settings.embedding_api_base_url,
            settings.embedding_api_model,
            settings.embedding_api_key,
        )
    return OllamaEmbeddingClient(settings.ollama_base_url, settings.ollama_embed_model)


def _embed_batch_with_retry(client: EmbeddingClient, batch: list[str]) -> list[list[float]]:
    """单个批次向量化 + 有限重试（处理瞬时网络超时）。

    仅对 Embedding 服务不可用（LLMError，如网络超时/连接中断）做有限次重试，
    退避随重试次数线性增长；重试耗尽仍失败则上抛，由上层（FR-011 回滚）处理。
    """
    attempts = 0
    while True:
        try:
            return client.embed(batch)
        except LLMError as exc:
            attempts += 1
            if attempts >= settings.embedding_retry_times:
                raise
            delay = settings.embedding_retry_backoff_seconds * attempts
            logger.warning(
                "Embedding 批次失败，%s/%s 次后重试（%.1fs 后）: %s",
                attempts,
                settings.embedding_retry_times,
                delay,
                exc,
            )
            time.sleep(delay)


def embed_texts(
    client: EmbeddingClient, texts: list[str], batch_size: int = 16
) -> list[list[float]]:
    """分批向量化，避免单次请求过大；每批带有限重试。"""
    if not texts:
        return []
    results: list[list[float]] = []
    for i in range(0, len(texts), max(batch_size, 1)):
        results.extend(_embed_batch_with_retry(client, texts[i : i + batch_size]))
    return results

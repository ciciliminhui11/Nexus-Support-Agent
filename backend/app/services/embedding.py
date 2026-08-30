"""Embedding 客户端抽象（可插拔后端）。

- `ollama`（默认）：调用 Ollama `/api/embed`，模型 `OLLAMA_EMBED_MODEL`（bge-m3）；
- `local`：sentence-transformers 本地加载（可选依赖，未安装时报清晰错误）。

外部服务不可用抛 `LLMError`，由上层转业务错误（文档标记失败）；测试用 Fake 客户端替换。
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.core.exceptions import LLMError


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
    return OllamaEmbeddingClient(settings.ollama_base_url, settings.ollama_embed_model)


def embed_texts(
    client: EmbeddingClient, texts: list[str], batch_size: int = 16
) -> list[list[float]]:
    """分批向量化，避免单次请求过大。"""
    if not texts:
        return []
    results: list[list[float]] = []
    for i in range(0, len(texts), max(batch_size, 1)):
        results.extend(client.embed(texts[i : i + batch_size]))
    return results

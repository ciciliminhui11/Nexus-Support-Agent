"""Reranker 精排抽象：CrossEncoder（可选依赖）与 Noop 降级。

research §3：粗筛（向量+BM25 经 RRF 融合）后，用本地 CrossEncoder
（bge-reranker-v2-m3）对「问题-片段」对精排，最终取 top-k 送 LLM。

降级策略（保证服务不挂）：
- `rag_reranker_enabled=False` → Noop（保持 RRF 融合序）；
- 未安装 sentence-transformers（`find_spec` 检测，不触发重导入）→ Noop；
- 模型加载 / 推理异常 → retriever 层 try/except 回落融合序。

安装教程（用户自行操作，镜像见 docs/重难点总结.md 第五部分 §5）。
"""
from __future__ import annotations

import importlib.util
import logging
from typing import Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class Reranker(Protocol):
    def rerank(self, query: str, texts: list[str]) -> list[float]:
        """返回与 texts 等长的分数，越大越相关；降序后即精排结果。"""


class CrossEncoderReranker:
    """sentence-transformers CrossEncoder；延迟导入，模型首次 _load 时加载。"""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder  # 延迟导入

            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        model = self._load()
        return [float(s) for s in model.predict([(query, t) for t in texts])]


class NoopReranker:
    """降级：保持输入顺序。返回递减整数，使其按降序排序时原序不变。"""

    def rerank(self, query: str, texts: list[str]) -> list[float]:
        return [float(len(texts) - i) for i in range(len(texts))]


_reranker_cache: Reranker | None = None
_reranker_attempted = False


def _build_reranker() -> Reranker:
    if not settings.rag_reranker_enabled:
        return NoopReranker()
    # find_spec 不触发重导入（sentence_transformers 会连带 torch，避免请求路径卡顿）
    if importlib.util.find_spec("sentence_transformers") is None:
        logger.warning(
            "sentence-transformers 未安装，Reranker 降级为 NoopReranker（保持 RRF 融合序）。"
            "安装教程见 docs/重难点总结.md 第五部分 §5。"
        )
        return NoopReranker()
    return CrossEncoderReranker(settings.rag_reranker_model)


def get_reranker() -> Reranker:
    """进程级单例；构造失败后不再重试（后续请求走 Noop，避免请求路径反复卡顿）。"""
    global _reranker_cache, _reranker_attempted
    if _reranker_cache is not None:
        return _reranker_cache
    if _reranker_attempted:
        return NoopReranker()
    _reranker_attempted = True
    _reranker_cache = _build_reranker()
    return _reranker_cache


def warmup() -> None:
    """启动预热（best-effort）：尽力加载模型；失败置 Noop，不阻断启动。"""
    try:
        r = get_reranker()
        if isinstance(r, CrossEncoderReranker):
            r._load()
            logger.info("Reranker 已预热：%s", r.model_name)
    except Exception as exc:  # noqa: BLE001
        global _reranker_cache
        _reranker_cache = NoopReranker()
        logger.warning("Reranker 预热失败，使用 NoopReranker：%s", exc)


def reset_reranker() -> None:
    """测试隔离：清空缓存与尝试标记，下次 get_reranker 重新决议。"""
    global _reranker_cache, _reranker_attempted
    _reranker_cache = None
    _reranker_attempted = False

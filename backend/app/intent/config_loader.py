"""006 规则配置加载：词库 / 句式模板 / 负样本库 YAML 惰性读取 + 模块级缓存。

配置路径经 settings 注入（.env 可覆盖），缺省回落 `backend/config/` 目录
（兼容 cwd 非 backend 的场景）。文件缺失/解析失败时返回空并告警，不阻断启动。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from app.config import settings
from app.core.logging import get_logger

from .schema import IntentCategory

logger = get_logger(__name__)

# backend/config/（app/intent/ 上溯两级）
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

_cache: dict[str, dict] = {}


def _resolve_path(cfg_attr: str, filename: str) -> Path:
    configured = Path(getattr(settings, cfg_attr, ""))
    if configured.is_absolute() and configured.exists():
        return configured
    if configured.exists():
        return configured
    fallback = _DEFAULT_CONFIG_DIR / filename
    if fallback.exists():
        return fallback
    return configured  # 不存在 → _load_yaml 记告警


def _load_yaml(name: str, cfg_attr: str, filename: str) -> dict:
    if name in _cache:
        return _cache[name]
    path = _resolve_path(cfg_attr, filename)
    if not path.exists():
        logger.warning("006 意图配置缺失：%s（跳过该配置源）", path)
        _cache[name] = {}
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            data = {}
    except Exception as exc:  # noqa: BLE001  配置解析失败不阻断
        logger.exception("006 意图配置解析失败 %s: %s", path, exc)
        data = {}
    _cache[name] = data
    return data


def _to_intent(key: str) -> IntentCategory | None:
    try:
        return IntentCategory(key)
    except ValueError:
        logger.warning("006 配置含未知意图 key=%s（已忽略）", key)
        return None


def get_keywords() -> dict[str, IntentCategory]:
    """词库 → {词: 意图}（供 AC 自动机）。"""
    raw = _load_yaml("keywords", "intent_keywords_path", "intent_keywords.yaml")
    result: dict[str, IntentCategory] = {}
    for key, words in raw.items():
        intent = _to_intent(key)
        if intent is None or intent is IntentCategory.unknown:
            continue
        if not isinstance(words, list):
            continue
        for word in words:
            if isinstance(word, str) and word.strip():
                result[word.strip()] = intent
    return result


def get_patterns() -> dict[IntentCategory, list[str]]:
    """句式模板 → {意图: [模板,...]}（pyparsing.Regex 编译）。"""
    raw = _load_yaml("patterns", "intent_patterns_path", "intent_patterns.yaml")
    result: dict[IntentCategory, list[str]] = {}
    for key, tmpls in raw.items():
        intent = _to_intent(key)
        if intent is None or intent is IntentCategory.unknown:
            continue
        if not isinstance(tmpls, list):
            continue
        result[intent] = [t for t in tmpls if isinstance(t, str) and t.strip()]
    return result


def get_negative_samples() -> dict[IntentCategory, list[str]]:
    """负样本库 → {意图: [反特征,...]}（反向校准拦截 + 规则层抑制）。"""
    raw = _load_yaml("negative_samples", "intent_negative_samples_path", "intent_negative_samples.yaml")
    result: dict[IntentCategory, list[str]] = {}
    for key, samples in raw.items():
        intent = _to_intent(key)
        if intent is None or intent is IntentCategory.unknown:
            continue
        if not isinstance(samples, list):
            continue
        result[intent] = [s for s in samples if isinstance(s, str) and s.strip()]
    return result


def reload_intent_config() -> None:
    """清空配置缓存（测试/热加载用），下次访问重新读盘。"""
    _cache.clear()

"""统一业务异常体系。

所有受控错误都抛出 `BizError` 子类，由 FastAPI 全局异常处理器转换为
`{ "code": ..., "message": ... }` 响应体（与各模块接口契约的错误码一致）。
"""
from __future__ import annotations

from typing import Any


class BizError(Exception):
    """业务异常基类。"""

    status_code: int = 400
    code: str = "bad_request"
    default_message: str = "请求参数有误"

    def __init__(self, message: str | None = None, code: str | None = None,
                 **extra: Any) -> None:
        super().__init__(message or self.default_message)
        self.code = code or self.code
        self.message = message or self.default_message
        self.extra = extra  # 额外字段（如 retry_after）会合并进响应体

    def to_payload(self) -> dict[str, Any]:
        payload = {"code": self.code, "message": self.message}
        payload.update(self.extra)
        return payload


# ---------- 401 / 403 ----------
class UnauthorizedError(BizError):
    status_code = 401
    code = "unauthorized"
    default_message = "请重新登录"


class ForbiddenError(BizError):
    status_code = 403
    code = "forbidden"
    default_message = "无权操作"


# ---------- 404 ----------
class NotFoundError(BizError):
    status_code = 404
    code = "not_found"
    default_message = "资源不存在"


# ---------- 400 校验类 ----------
class ValidationError(BizError):
    status_code = 400
    code = "validation_error"
    default_message = "参数校验失败"


# ---------- 409 冲突 ----------
class ConflictError(BizError):
    status_code = 409
    code = "conflict"
    default_message = "资源已存在"


# ---------- 429 ----------
class QuotaExceededError(BizError):
    status_code = 429
    code = "quota_exceeded"
    default_message = "今日提问次数已用尽，请明天再试"


class RateLimitError(BizError):
    """限流/尝试过频。extra 带 retry_after。"""

    status_code = 429
    code = "too_many_attempts"
    default_message = "尝试过于频繁，请稍后再试"


# ---------- 知识库 / 文件 ----------
class FileTooLargeError(BizError):
    status_code = 413
    code = "file_too_large"
    default_message = "文件大小超过上限"


# ---------- LLM ----------
class LLMError(BizError):
    """LLM 调用异常（超时/限流/服务错误）。由 SSE error 事件承载。"""

    status_code = 502
    code = "llm_error"
    default_message = "模型服务暂时不可用，请稍后再试"

"""连续登录失败递增延迟防护（账号标识 + 来源 IP 维度）。

- 不落库（v1 内存态；重启后状态丢失为已知限制，多实例需换 Redis）；
- `fail_count >= threshold`（默认 5）触发锁定，锁定时间 = min(2^fail_count, max_lock) 秒；
- 登录成功清零。
"""
from __future__ import annotations

import time
from math import ceil

from app.core.exceptions import RateLimitError

from app.config import settings


class LoginGuard:
    def __init__(
        self,
        threshold: int | None = None,
        max_lock_seconds: int | None = None,
    ) -> None:
        self.threshold = threshold or settings.login_fail_threshold
        self.max_lock_seconds = max_lock_seconds or settings.login_lock_max_seconds
        # key -> {"fail_count": int, "locked_until": float}
        self._records: dict[str, dict] = {}

    @staticmethod
    def _make_key(identifier: str, ip: str) -> str:
        return f"{identifier}|{ip}"

    def check(self, identifier: str, ip: str) -> None:
        """尝试登录前调用；若处于锁定期抛出 429（带 retry_after）。"""
        rec = self._records.get(self._make_key(identifier, ip))
        now = time.time()
        if rec and rec["locked_until"] and now < rec["locked_until"]:
            retry_after = ceil(rec["locked_until"] - now)
            raise RateLimitError(
                message=f"尝试过于频繁，请 {retry_after} 秒后再试",
                retry_after=retry_after,
            )

    def record_failure(self, identifier: str, ip: str) -> None:
        key = self._make_key(identifier, ip)
        rec = self._records.setdefault(key, {"fail_count": 0, "locked_until": 0.0})
        rec["fail_count"] += 1
        if rec["fail_count"] >= self.threshold:
            rec["locked_until"] = time.time() + min(
                2 ** rec["fail_count"], self.max_lock_seconds
            )

    def record_success(self, identifier: str, ip: str) -> None:
        self._records.pop(self._make_key(identifier, ip), None)


# 全局单例（所有登录入口共用）
login_guard = LoginGuard()

"""登录失败递增延迟防护。"""
from __future__ import annotations

import pytest

from app.core.exceptions import RateLimitError
from app.core.login_guard import LoginGuard


def test_success_after_failures_resets():
    guard = LoginGuard(threshold=2, max_lock_seconds=300)
    guard.record_failure("u", "1.1.1.1")
    guard.record_failure("u", "1.1.1.1")
    # 第 2 次失败触发锁定
    with pytest.raises(RateLimitError):
        guard.check("u", "1.1.1.1")
    guard.record_success("u", "1.1.1.1")
    guard.check("u", "1.1.1.1")  # 不再抛异常


def test_below_threshold_allows_attempt():
    guard = LoginGuard(threshold=5, max_lock_seconds=300)
    guard.record_failure("u", "1.1.1.1")
    guard.record_failure("u", "1.1.1.1")
    guard.check("u", "1.1.1.1")  # 未达阈值，允许


def test_different_ip_isolated():
    guard = LoginGuard(threshold=2, max_lock_seconds=300)
    guard.record_failure("u", "1.1.1.1")
    guard.record_failure("u", "1.1.1.1")
    with pytest.raises(RateLimitError):
        guard.check("u", "1.1.1.1")
    guard.check("u", "2.2.2.2")  # 不同 IP 不受影响


def test_lock_duration_exponential_capped():
    guard = LoginGuard(threshold=5, max_lock_seconds=300)
    # 连续失败 5 次
    for _ in range(5):
        guard.record_failure("u", "1.1.1.1")
    with pytest.raises(RateLimitError) as exc:
        guard.check("u", "1.1.1.1")
    assert exc.value.extra.get("retry_after") <= 300

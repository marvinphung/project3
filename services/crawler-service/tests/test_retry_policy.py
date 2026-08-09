from __future__ import annotations

from datetime import UTC, datetime

import httpx
from footballpulse_crawler_service.discovery.retry import RetryPolicy


def test_retries_only_transient_statuses() -> None:
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=30)

    assert policy.delay_for_status(500, attempt=1, headers={}) == 1
    assert policy.delay_for_status(503, attempt=2, headers={}) == 2
    assert policy.delay_for_status(404, attempt=1, headers={}) is None
    assert policy.delay_for_status(401, attempt=1, headers={}) is None
    assert policy.delay_for_status(500, attempt=3, headers={}) is None


def test_honors_bounded_retry_after_seconds_and_http_date() -> None:
    now = datetime(2026, 8, 9, 0, 0, tzinfo=UTC)
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=30)

    assert policy.delay_for_status(429, attempt=1, headers={"Retry-After": "8"}, now=now) == 8
    assert (
        policy.delay_for_status(
            429,
            attempt=1,
            headers={"Retry-After": "Sun, 09 Aug 2026 00:00:20 GMT"},
            now=now,
        )
        == 20
    )
    assert policy.delay_for_status(429, attempt=1, headers={"Retry-After": "999"}, now=now) == 30


def test_retries_timeout_and_network_errors_only_with_attempts_left() -> None:
    policy = RetryPolicy(max_attempts=2, base_delay_seconds=0.5, max_delay_seconds=5)

    assert policy.delay_for_exception(httpx.ReadTimeout("slow"), attempt=1) == 0.5
    assert policy.delay_for_exception(httpx.ConnectError("down"), attempt=1) == 0.5
    assert policy.delay_for_exception(ValueError("bad"), attempt=1) is None
    assert policy.delay_for_exception(httpx.ReadTimeout("slow"), attempt=2) is None

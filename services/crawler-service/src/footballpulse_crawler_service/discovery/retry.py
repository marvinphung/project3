from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays must not be negative")

    def delay_for_status(
        self,
        status_code: int,
        *,
        attempt: int,
        headers: Mapping[str, str],
        now: datetime | None = None,
    ) -> float | None:
        if attempt >= self.max_attempts:
            return None
        if status_code == 429:
            retry_after = self._retry_after_seconds(headers.get("Retry-After"), now=now)
            if retry_after is not None:
                return min(retry_after, self.max_delay_seconds)
        if status_code not in {429, 500, 502, 503, 504}:
            return None
        return self._backoff(attempt)

    def delay_for_exception(self, error: Exception, *, attempt: int) -> float | None:
        if attempt >= self.max_attempts:
            return None
        if not isinstance(error, (httpx.TimeoutException, httpx.NetworkError)):
            return None
        return self._backoff(attempt)

    def _backoff(self, attempt: int) -> float:
        return min(
            self.base_delay_seconds * float(2 ** (attempt - 1)),
            self.max_delay_seconds,
        )

    @staticmethod
    def _retry_after_seconds(value: str | None, *, now: datetime | None) -> float | None:
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            pass
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        current = now or datetime.now(UTC)
        return max(0.0, (retry_at - current).total_seconds())

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, MutableSequence
from typing import Any
from uuid import uuid4

from footballpulse_runtime_config.logging import bind_log_context, log_event

type AsgiMessage = dict[str, Any]
type AsgiReceive = Callable[[], Awaitable[Any]]
type AsgiSend = Callable[[Any], Awaitable[None]]
type AsgiApp = Callable[[Any, AsgiReceive, AsgiSend], Awaitable[None]]


class RequestLoggingMiddleware:
    """Log HTTP progress in the request task without BaseHTTPMiddleware."""

    def __init__(self, app: AsgiApp, *, logger: logging.Logger) -> None:
        self._app = app
        self._logger = logger

    async def __call__(
        self, scope: Any, receive: AsgiReceive, send: AsgiSend
    ) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")
        request_id = self._request_id(scope.get("headers", []))
        started = time.monotonic()
        status_code = 500

        async def observe_send(message: AsgiMessage) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                raw_status = message.get("status", 500)
                status_code = raw_status if isinstance(raw_status, int) else 500
                headers = message.setdefault("headers", [])
                if isinstance(headers, MutableSequence):
                    headers.append((b"x-request-id", request_id.encode("ascii")))
            await send(message)

        with bind_log_context(correlation_id=request_id):
            if path != "/health":
                log_event(self._logger, "http_request_started", method=method, path=path)
            try:
                await self._app(scope, receive, observe_send)
            except Exception as error:
                log_event(
                    self._logger,
                    "http_request_failed",
                    level=logging.ERROR,
                    error=error,
                    method=method,
                    path=path,
                    duration_ms=round((time.monotonic() - started) * 1000),
                )
                raise
            if path != "/health":
                log_event(
                    self._logger,
                    "http_request_completed",
                    level=logging.ERROR if status_code >= 500 else logging.INFO,
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=round((time.monotonic() - started) * 1000),
                )

    @staticmethod
    def _request_id(headers: list[tuple[bytes, bytes]]) -> str:
        for name, value in headers:
            if name.lower() == b"x-request-id":
                candidate = value.decode("ascii", errors="ignore").strip()
                if candidate and len(candidate) <= 128:
                    return candidate
        return str(uuid4())

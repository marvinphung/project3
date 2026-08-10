from __future__ import annotations

import math
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse


def install_gateway_middleware(
    app: FastAPI, *, max_requests: int | None = None, window_seconds: int = 60
) -> None:
    if max_requests is not None and max_requests < 1:
        raise ValueError("max_requests must be positive")
    if window_seconds < 1:
        raise ValueError("window_seconds must be positive")
    rate_state: dict[str, tuple[float, int]] = {}

    @app.middleware("http")
    async def gateway_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID", "").strip()
        if not request_id or len(request_id) > 128:
            request_id = str(uuid4())
        response: Response
        if max_requests is not None:
            client_ip = request.client.host if request.client is not None else "unknown"
            now = time.monotonic()
            started_at, count = rate_state.get(client_ip, (now, 0))
            if now - started_at >= window_seconds:
                started_at, count = now, 0
            if count >= max_requests:
                retry_after = max(1, math.ceil(window_seconds - (now - started_at)))
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "request rate limit exceeded",
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            else:
                rate_state[client_ip] = (started_at, count + 1)
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

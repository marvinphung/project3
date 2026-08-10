from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request, Response


def install_gateway_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def gateway_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID", "").strip()
        if not request_id or len(request_id) > 128:
            request_id = str(uuid4())
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

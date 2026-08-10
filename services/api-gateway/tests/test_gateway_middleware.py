from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from footballpulse_api_gateway.middleware import install_gateway_middleware


@pytest.mark.asyncio
async def test_gateway_middleware_adds_request_id_and_security_headers() -> None:
    app = FastAPI()

    @app.get("/")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    install_gateway_middleware(app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_gateway_middleware_generates_request_id_when_missing() -> None:
    app = FastAPI()
    install_gateway_middleware(app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/missing")

    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_gateway_middleware_returns_429_after_rate_limit() -> None:
    app = FastAPI()

    @app.get("/")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    install_gateway_middleware(app, max_requests=1, window_seconds=60)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/")
        second = await client.get("/")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "60"
    assert second.json()["error"]["code"] == "RATE_LIMITED"

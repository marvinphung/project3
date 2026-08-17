from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from footballpulse_api_gateway.api.auth import create_auth_app
from footballpulse_api_gateway.auth import (
    AuthService,
    InMemoryUserRepository,
    Role,
    TokenService,
    User,
)

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
SECRET = "local-secret-012345678901234567890123"


def _client() -> httpx.AsyncClient:
    users = InMemoryUserRepository()
    users.add(User.create("editor", "correct horse", Role.EDITOR, created_at=NOW))
    service = AuthService(users, TokenService(SECRET, clock=lambda: NOW))
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_auth_app(service)), base_url="http://test"
    )


@pytest.mark.anyio
async def test_token_endpoint_returns_jwt_claims() -> None:
    async with _client() as client:
        response = await client.post(
            "/auth/token", json={"username": "editor", "password": "correct horse"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "EDITOR"
    assert body["expires_in"] == 1800
    assert body["access_token"]


@pytest.mark.anyio
async def test_token_endpoint_hides_credential_failure() -> None:
    async with _client() as client:
        response = await client.post(
            "/auth/token", json={"username": "editor", "password": "wrong"}
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "INVALID_CREDENTIALS", "message": "invalid credentials"}
    }

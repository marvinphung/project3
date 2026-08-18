from __future__ import annotations

import httpx
import pytest
from footballpulse_api_gateway.runtime_v2 import build_app, database_url


def test_database_url_prefers_explicit_environment_value() -> None:
    values = {"SUPABASE_DATABASE_URL": "postgresql://example"}

    assert database_url(values) == "postgresql+psycopg://example"


def test_build_app_exposes_public_routes_without_connecting_until_request() -> None:
    app = build_app(
        {
            "SUPABASE_DATABASE_URL": "postgresql://user:pass@localhost/db",
            "FOOTBALLPULSE_MONGODB_URL": "mongodb://localhost:27017",
            "FOOTBALLPULSE_API_ADMIN_TOKEN": "admin-test-token",
        }
    )

    assert "/api/v2/articles/{slug}" in app.openapi()["paths"]
    assert "/api/v2/stories/{story_id}/timeline" in app.openapi()["paths"]
    assert "/admin/v1/articles/{article_id}/publish" in app.openapi()["paths"]
    assert "/auth/token" in app.openapi()["paths"]


@pytest.mark.asyncio
async def test_runtime_liveness_endpoint_does_not_require_database() -> None:
    app = build_app({"SUPABASE_DATABASE_URL": "postgresql://user:pass@localhost/db"})
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "api-gateway", "status": "ok"}

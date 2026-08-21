from __future__ import annotations

import httpx
import pytest


def test_database_url_prefers_explicit_environment_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:pass@localhost/db")
    from footballpulse_api_gateway.runtime_v2 import database_url

    values = {"SUPABASE_DATABASE_URL": "postgresql://example"}

    assert database_url(values) == "postgresql+psycopg://example"


def test_database_url_requires_supabase_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:pass@localhost/db")
    from footballpulse_api_gateway.runtime_v2 import database_url

    with pytest.raises(RuntimeError, match="Supabase database configuration is required"):
        database_url({})


def test_build_app_exposes_public_routes_without_connecting_until_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:pass@localhost/db")
    from footballpulse_api_gateway.runtime_v2 import build_app

    app = build_app(
        {
            "SUPABASE_DATABASE_URL": "postgresql://user:pass@localhost/db",
        }
    )

    assert "/api/v2/entities/top" in app.openapi()["paths"]
    assert "/api/v2/entities/search" in app.openapi()["paths"]
    assert "/api/v2/entities/{entity_id}/timeline" in app.openapi()["paths"]
    assert "/auth/token" in app.openapi()["paths"]


@pytest.mark.asyncio
async def test_runtime_liveness_endpoint_does_not_require_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:pass@localhost/db")
    from footballpulse_api_gateway.runtime_v2 import build_app

    app = build_app({"SUPABASE_DATABASE_URL": "postgresql://user:pass@localhost/db"})
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "api-gateway", "status": "ok"}

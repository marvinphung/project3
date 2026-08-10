from __future__ import annotations

from footballpulse_api_gateway.runtime import build_app, database_url


def test_database_url_prefers_explicit_environment_value() -> None:
    values = {"FOOTBALLPULSE_DATABASE_URL": "postgresql+psycopg://example"}

    assert database_url(values) == values["FOOTBALLPULSE_DATABASE_URL"]


def test_build_app_exposes_public_routes_without_connecting_until_request() -> None:
    app = build_app(
        {
            "FOOTBALLPULSE_DATABASE_URL": "postgresql+psycopg://user:pass@localhost/db"
        }
    )

    assert "/api/v1/articles/{slug}" in app.openapi()["paths"]

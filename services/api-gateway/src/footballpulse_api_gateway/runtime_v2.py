from __future__ import annotations

import os
from collections.abc import Mapping

import uvicorn
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from footballpulse_api_gateway.api.public_v2 import create_public_v2_app
from footballpulse_api_gateway.health import liveness
from footballpulse_api_gateway.middleware import install_gateway_middleware


def database_url(environment: Mapping[str, str]) -> str:
    explicit = environment.get("SUPABASE_DATABASE_URL") or environment.get("FOOTBALLPULSE_DATABASE_URL")
    if explicit:
        return explicit
    return URL.create(
        "postgresql+psycopg",
        username=environment.get("SUPABASE_DB_USER", "postgres"),
        password=environment.get("SUPABASE_DB_PASSWORD", "postgres"),
        host=environment.get("SUPABASE_DB_HOST", "127.0.0.1"),
        port=int(environment.get("SUPABASE_DB_PORT", "5432")),
        database=environment.get("SUPABASE_DB_NAME", "postgres"),
    ).render_as_string(hide_password=False)


def build_app(environment: Mapping[str, str] | None = None) -> FastAPI:
    values = os.environ if environment is None else environment
    app = create_public_v2_app(create_engine(database_url(values), pool_pre_ping=True))

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return liveness()

    install_gateway_middleware(
        app,
        max_requests=int(values.get("FOOTBALLPULSE_API_RATE_LIMIT", "120")),
        window_seconds=int(values.get("FOOTBALLPULSE_API_RATE_WINDOW_SECONDS", "60")),
    )
    return app


app = build_app()


def main() -> None:
    uvicorn.run(
        "footballpulse_api_gateway.runtime_v2:app",
        host=os.getenv("FOOTBALLPULSE_API_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", os.getenv("FOOTBALLPULSE_API_PORT", "8000"))),
        reload=False,
    )

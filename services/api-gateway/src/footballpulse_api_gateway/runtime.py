from __future__ import annotations

import os
from collections.abc import Mapping

import uvicorn
from fastapi import FastAPI
from footballpulse_content_service.editorial.postgres_publication_repository import (
    PostgresPublicationRepository,
)
from footballpulse_content_service.editorial.postgres_repository import (
    PostgresEditorialRevisionRepository,
)
from footballpulse_content_service.editorial.publication import PublicationService
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from footballpulse_api_gateway.api.editorial_admin import create_editorial_admin_app
from footballpulse_api_gateway.api.public import create_public_app
from footballpulse_api_gateway.application.editorial_admin_adapter import (
    ContentEditorialAdminAdapter,
)
from footballpulse_api_gateway.middleware import install_gateway_middleware
from footballpulse_api_gateway.persistence.public_read_repository import (
    PostgresPublicReadRepository,
)


def database_url(environment: Mapping[str, str]) -> str:
    explicit_url = environment.get("FOOTBALLPULSE_DATABASE_URL")
    if explicit_url:
        return explicit_url
    return URL.create(
        "postgresql+psycopg",
        username=environment.get("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
        password=environment.get("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only"),
        host=environment.get("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
        port=int(environment.get("FOOTBALLPULSE_POSTGRES_PORT", "5432")),
        database=environment.get("FOOTBALLPULSE_POSTGRES_DB", "footballpulse"),
    ).render_as_string(hide_password=False)


def build_app(environment: Mapping[str, str] | None = None) -> FastAPI:
    values = os.environ if environment is None else environment
    engine = create_engine(database_url(values), pool_pre_ping=True)
    revision_repository = PostgresEditorialRevisionRepository(engine)
    publication_service = PublicationService(PostgresPublicationRepository(engine))
    editorial_service = ContentEditorialAdminAdapter(
        revision_repository=revision_repository,
        publication_service=publication_service,
    )
    app = create_public_app(PostgresPublicReadRepository(engine))
    admin_app = create_editorial_admin_app(
        editorial_service,
        admin_token=values.get("FOOTBALLPULSE_API_ADMIN_TOKEN", "local-admin-token"),
        editor_token=values.get("FOOTBALLPULSE_API_EDITOR_TOKEN"),
    )
    app.router.routes.extend(admin_app.router.routes)
    app.exception_handlers.update(admin_app.exception_handlers)
    app.openapi_schema = None
    install_gateway_middleware(
        app,
        max_requests=int(values.get("FOOTBALLPULSE_API_RATE_LIMIT", "120")),
        window_seconds=int(values.get("FOOTBALLPULSE_API_RATE_WINDOW_SECONDS", "60")),
    )
    return app


def main() -> None:
    uvicorn.run(
        "footballpulse_api_gateway.runtime:app",
        host=os.getenv("FOOTBALLPULSE_API_HOST", "127.0.0.1"),
        port=int(os.getenv("FOOTBALLPULSE_API_PORT", "8000")),
        reload=False,
    )


app = build_app()

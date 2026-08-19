from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI
from footballpulse_content_service.editorial.postgres_publication_repository import (
    PostgresPublicationRepository,
)
from footballpulse_content_service.editorial.postgres_repository import (
    PostgresEditorialRevisionRepository,
)
from footballpulse_content_service.editorial.publication import PublicationService
from pymongo import MongoClient
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from footballpulse_api_gateway.api.auth import create_auth_app
from footballpulse_api_gateway.api.editorial_admin import create_editorial_admin_app
from footballpulse_api_gateway.api.public_v2 import create_public_v2_app
from footballpulse_api_gateway.application.editorial_admin_adapter import (
    ContentEditorialAdminAdapter,
)
from footballpulse_api_gateway.auth import AuthService, Role, TokenService
from footballpulse_api_gateway.health import liveness
from footballpulse_api_gateway.middleware import install_gateway_middleware
from footballpulse_api_gateway.persistence.admin_publication_read_repository import (
    AdminPublicationReadRepository,
)
from footballpulse_api_gateway.persistence.admin_story_read_repository import (
    AdminStoryReadRepository,
)
from footballpulse_api_gateway.persistence.identity_repository import PostgresUserRepository
from footballpulse_api_gateway.persistence.mongo_source_article_read_repository import (
    MongoSourceArticleReadRepository,
)
from footballpulse_api_gateway.persistence.operations_read_repository import (
    OperationsReadRepository,
)
from footballpulse_api_gateway.persistence.processing_failure_read_repository import (
    ProcessingFailureReadRepository,
)


def database_url(environment: Mapping[str, str]) -> str:
    if environment.get("FOOTBALLPULSE_V2_POSTGRES_URL"):
        return environment["FOOTBALLPULSE_V2_POSTGRES_URL"]
    supabase_db_host = environment.get("SUPABASE_DB_HOST") or None
    supabase_database_url = environment.get("SUPABASE_DATABASE_URL") or None
    footballpulse_database_url = environment.get("FOOTBALLPULSE_DATABASE_URL") or None
    if supabase_db_host:
        return URL.create(
            "postgresql+psycopg",
            username=environment.get("SUPABASE_DB_USER", "postgres"),
            password=environment.get("SUPABASE_DB_PASSWORD", "postgres"),
            host=supabase_db_host,
            port=int(environment.get("SUPABASE_DB_PORT", "5432")),
            database=environment.get("SUPABASE_DB_NAME", "postgres"),
        ).render_as_string(hide_password=False)
    explicit = supabase_database_url or footballpulse_database_url
    if explicit:
        return explicit.replace("postgresql://", "postgresql+psycopg://", 1)
    return URL.create(
        "postgresql+psycopg",
        username=environment.get("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
        password=environment.get("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_v2_local"),
        host=environment.get("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
        port=int(environment.get("FOOTBALLPULSE_POSTGRES_PORT", "15432")),
        database=environment.get("FOOTBALLPULSE_POSTGRES_DB", "footballpulse_v2"),
    ).render_as_string(hide_password=False)


def _bootstrap_user(
    values: Mapping[str, str], repository: PostgresUserRepository, prefix: str, role: Role
) -> None:
    username = values.get(f"FOOTBALLPULSE_API_{prefix}_USERNAME")
    password = values.get(f"FOOTBALLPULSE_API_{prefix}_PASSWORD")
    if username and password:
        try:
            repository.ensure_user(username, password, role, created_at=datetime.now(UTC))
        except ProgrammingError:
            # Public API startup must not fail when optional identity tables have
            # not been provisioned in the target Postgres yet.
            return


def build_app(environment: Mapping[str, str] | None = None) -> FastAPI:
    values = os.environ if environment is None else environment
    engine = create_engine(database_url(values), pool_pre_ping=True)
    app = create_public_v2_app(engine)

    mongo_client = MongoClient(
        values.get("FOOTBALLPULSE_MONGODB_URL", "mongodb://127.0.0.1:27017"),
        connect=False,
    )
    mongo_database = mongo_client[values.get("FOOTBALLPULSE_MONGODB_DB", "footballpulse")]
    revision_repository = PostgresEditorialRevisionRepository(engine)
    publication_service = PublicationService(PostgresPublicationRepository(engine))
    user_repository = PostgresUserRepository(engine)
    token_service = TokenService(
        values.get(
            "FOOTBALLPULSE_API_JWT_SECRET",
            "local-jwt-secret-change-me-0123456789",
        )
    )
    auth_service = AuthService(user_repository, token_service)
    _bootstrap_user(values, user_repository, "ADMIN", Role.ADMIN)
    _bootstrap_user(values, user_repository, "EDITOR", Role.EDITOR)
    editorial_service = ContentEditorialAdminAdapter(
        revision_repository=revision_repository,
        publication_service=publication_service,
    )
    admin_app = create_editorial_admin_app(
        editorial_service,
        admin_token=values.get("FOOTBALLPULSE_API_ADMIN_TOKEN", "local-admin-token"),
        editor_token=values.get("FOOTBALLPULSE_API_EDITOR_TOKEN"),
        token_service=token_service,
        source_article_repository=MongoSourceArticleReadRepository(
            mongo_database["source_articles"]
        ),
        operations_repository=OperationsReadRepository(mongo_database, engine),
        story_repository=AdminStoryReadRepository(engine),
        publication_repository=AdminPublicationReadRepository(engine),
        failure_repository=ProcessingFailureReadRepository(engine),
    )
    auth_app = create_auth_app(auth_service)
    app.router.routes.extend(admin_app.router.routes)
    app.router.routes.extend(auth_app.router.routes)
    app.exception_handlers.update(admin_app.exception_handlers)
    app.exception_handlers.update(auth_app.exception_handlers)
    app.openapi_schema = None

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


if __name__ == "__main__":
    main()

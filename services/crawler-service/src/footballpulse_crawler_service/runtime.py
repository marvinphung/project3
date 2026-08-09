from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from footballpulse_crawler_service.api.app import create_app
from footballpulse_crawler_service.application.source_service import (
    CrawlBatchService,
    SourceService,
)
from footballpulse_crawler_service.persistence.postgres_repositories import (
    PostgresCrawlBatchRepository,
    PostgresSourceRepository,
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


def required_token(environment: Mapping[str, str], name: str) -> str:
    token = environment.get(name, "")
    if not token:
        raise RuntimeError(f"{name} is required")
    return token


def utc_now() -> datetime:
    return datetime.now(UTC)


def build_app(environment: Mapping[str, str] | None = None) -> FastAPI:
    values = os.environ if environment is None else environment
    engine = create_engine(database_url(values), pool_pre_ping=True)
    source_repository = PostgresSourceRepository(engine)
    batch_repository = PostgresCrawlBatchRepository(engine)
    return create_app(
        source_service=SourceService(source_repository, clock=utc_now),
        batch_service=CrawlBatchService(source_repository, batch_repository, clock=utc_now),
        admin_token=required_token(values, "FOOTBALLPULSE_CRAWLER_ADMIN_TOKEN"),
        internal_token=required_token(values, "FOOTBALLPULSE_CRAWLER_INTERNAL_TOKEN"),
    )


app = build_app()

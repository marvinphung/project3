from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from footballpulse_intelligence_service.application.entity_catalog import (
    AliasDecision,
    EntityCatalogService,
)
from footballpulse_intelligence_service.domain.entity import EntityType
from footballpulse_intelligence_service.domain.errors import EntityConflictError
from footballpulse_intelligence_service.domain.extraction import (
    EntityLabel,
    SourceField,
    SpanPrediction,
)
from footballpulse_intelligence_service.domain.unresolved import UnresolvedEntityMention
from footballpulse_intelligence_service.persistence.postgres_repository import (
    PostgresEntityCatalogRepository,
    PostgresUnresolvedMentionRepository,
)
from psycopg import sql
from sqlalchemy import create_engine

ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)


def postgres_url(database: str, *, sqlalchemy_driver: bool = False) -> str:
    scheme = "postgresql+psycopg" if sqlalchemy_driver else "postgresql"
    user = os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse")
    password = os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only")
    host = os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")
    return f"{scheme}://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture
def migrated_database() -> Iterator[str]:
    database = f"footballpulse_entity_test_{uuid4().hex}"
    with psycopg.connect(postgres_url("postgres"), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    environment = os.environ.copy()
    environment["FOOTBALLPULSE_DATABASE_URL"] = postgres_url(database, sqlalchemy_driver=True)
    migration = subprocess.run(
        [
            "uv",
            "run",
            "alembic",
            "-c",
            "services/intelligence-service/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert migration.returncode == 0, migration.stderr
    try:
        yield database
    finally:
        with psycopg.connect(postgres_url("postgres"), autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_ENTITY_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_ENTITY_INTEGRATION=1 with PostgreSQL running",
)
def test_seed_resolution_admin_review_audit_and_atomic_conflict(
    migrated_database: str,
) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    repository = PostgresEntityCatalogRepository(engine)
    service = EntityCatalogService(repository, clock=lambda: NOW)

    vinicius = service.resolve("VINICIUS Junior")
    arsenal = service.resolve("Gunners")
    assert vinicius is not None and vinicius.slug == "vinicius-junior"
    assert arsenal is not None and arsenal.slug == "arsenal"
    assert repository.find_entity_by_slug("real-madrid") is not None

    club = service.create_entity(
        entity_type=EntityType.CLUB,
        canonical_name="Athletic Club",
        slug="athletic-club",
        actor="admin:1",
        reason="Add trusted La Liga club",
    )
    pending = service.propose_pipeline_alias(
        club.id,
        alias="Athletic Bilbao",
        resolver_version="resolver-v1",
        actor="service:intelligence",
        reason="Extracted common alias",
    )
    assert service.resolve("Athletic Bilbao") is None
    approved = service.review_alias(
        pending.id,
        decision=AliasDecision.APPROVE,
        expected_version=1,
        actor="admin:1",
        reason="Known club alias",
    )
    assert service.resolve("athletic bilbao") == club

    renamed = service.rename_entity(
        club.id,
        canonical_name="Athletic Club Bilbao",
        expected_version=1,
        actor="admin:1",
        reason="Use catalog display name",
    )
    assert renamed.slug == "athletic-club"
    assert service.resolve("Athletic Club Bilbao") == renamed
    changed_slug = service.change_slug(
        club.id,
        slug="athletic-club-bilbao",
        expected_version=2,
        actor="admin:1",
        reason="Explicit public slug change",
    )
    assert repository.find_entity_by_slug("athletic-club-bilbao") == changed_slug
    service.disable_alias(
        approved.id,
        expected_version=2,
        actor="admin:1",
        reason="Retire historical name",
    )
    assert service.resolve("Athletic Bilbao") is None
    service.disable_entity(
        club.id,
        expected_version=3,
        actor="admin:1",
        reason="Disable catalog entity without deleting history",
    )
    assert service.resolve("Athletic Club Bilbao") is None

    with pytest.raises(EntityConflictError, match="already exists"):
        service.create_entity(
            entity_type=EntityType.CLUB,
            canonical_name="Arsenal",
            slug="arsenal-copy",
            actor="admin:1",
            reason="Conflict proof",
        )
    assert repository.find_entity_by_slug("arsenal-copy") is None

    with engine.connect() as connection:
        audit_actions = set(
            connection.execute(
                sa.text(
                    "SELECT action FROM intelligence_schema.entity_audit_log "
                    "WHERE actor = 'admin:1'"
                )
            ).scalars()
        )
    assert {
        "CREATE_ENTITY",
        "APPROVE_ALIAS",
        "RENAME_ENTITY",
        "CHANGE_ENTITY_SLUG",
        "DISABLE_ALIAS",
        "DISABLE_ENTITY",
    } <= audit_actions

    source_text = "Mystery FC joined the talks."
    unresolved = UnresolvedEntityMention.from_prediction(
        article_version_id=uuid4(),
        prediction=SpanPrediction.create(
            source_field=SourceField.CONTENT,
            source_text=source_text,
            label=EntityLabel.CLUB,
            start=0,
            end=10,
            score=0.82,
        ),
        predicted_type=EntityType.CLUB,
        model_name="mock-gliner",
        model_version="fixture-v1",
        now=NOW,
    )
    unresolved_repository = PostgresUnresolvedMentionRepository(engine)
    assert unresolved_repository.add_once(unresolved) == unresolved
    assert unresolved_repository.add_once(unresolved) == unresolved
    with engine.connect() as connection:
        unresolved_count = connection.execute(
            sa.text("SELECT count(*) FROM intelligence_schema.unresolved_entity_mentions")
        ).scalar_one()
    assert unresolved_count == 1
    engine.dispose()

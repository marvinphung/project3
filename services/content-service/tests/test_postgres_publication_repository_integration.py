from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from footballpulse_content_service.editorial.postgres_publication_repository import (
    PostgresPublicationRepository,
)
from footballpulse_content_service.editorial.postgres_tables import publication_outbox
from footballpulse_content_service.editorial.publication import Publication
from footballpulse_content_service.editorial.publication_outbox import PublicationPublishedEvent
from sqlalchemy import create_engine, select

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)


@pytest.mark.integration
def test_postgres_publication_repository_is_idempotent() -> None:
    if os.getenv("FOOTBALLPULSE_RUN_CONTENT_INTEGRATION") != "1":
        pytest.skip("set FOOTBALLPULSE_RUN_CONTENT_INTEGRATION=1 to run")
    engine = create_engine(os.environ["FOOTBALLPULSE_DATABASE_URL"])
    repository = PostgresPublicationRepository(engine)
    publication = Publication(
        id=uuid4(),
        generated_article_id=uuid4(),
        revision_id=uuid4(),
        story_id=uuid4(),
        story_version=1,
        slug="arsenal-bid",
        title_en="Arsenal bid",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua",
        body_vi="Arsenal đã gửi đề nghị.",
        idempotency_key=f"test-{uuid4()}",
        published_at=NOW,
    )

    assert repository.create(publication) == publication
    assert repository.get_by_idempotency_key(publication.idempotency_key) == publication
    assert repository.create(publication) == publication


@pytest.mark.integration
def test_postgres_repository_creates_publication_and_outbox_together() -> None:
    if os.getenv("FOOTBALLPULSE_RUN_CONTENT_INTEGRATION") != "1":
        pytest.skip("set FOOTBALLPULSE_RUN_CONTENT_INTEGRATION=1 to run")
    engine = create_engine(os.environ["FOOTBALLPULSE_DATABASE_URL"])
    repository = PostgresPublicationRepository(engine)
    publication = Publication(
        id=uuid4(),
        generated_article_id=uuid4(),
        revision_id=uuid4(),
        story_id=uuid4(),
        story_version=1,
        slug="arsenal-bid-outbox",
        title_en="Arsenal bid",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua",
        body_vi="Arsenal đã gửi đề nghị.",
        idempotency_key=f"test-{uuid4()}",
        published_at=NOW,
    )

    assert repository.create_with_outbox(
        publication, PublicationPublishedEvent.from_publication(publication)
    ) == publication
    with engine.connect() as connection:
        row = (
            connection.execute(
                select(publication_outbox).where(publication_outbox.c.event_id == publication.id)
            )
            .mappings()
            .one()
        )
    assert row["publication_id"] == publication.id
    assert row["state"] == "PENDING"


@pytest.mark.integration
def test_postgres_outbox_supports_pending_success_and_failure_updates() -> None:
    if os.getenv("FOOTBALLPULSE_RUN_CONTENT_INTEGRATION") != "1":
        pytest.skip("set FOOTBALLPULSE_RUN_CONTENT_INTEGRATION=1 to run")
    engine = create_engine(os.environ["FOOTBALLPULSE_DATABASE_URL"])
    repository = PostgresPublicationRepository(engine)
    publication = Publication(
        id=uuid4(),
        generated_article_id=uuid4(),
        revision_id=uuid4(),
        story_id=uuid4(),
        story_version=1,
        slug="arsenal-bid-worker",
        title_en="Arsenal bid",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua",
        body_vi="Arsenal đã gửi đề nghị.",
        idempotency_key=f"test-{uuid4()}",
        published_at=NOW,
    )
    event = PublicationPublishedEvent.from_publication(publication)
    repository.create_with_outbox(publication, event)

    pending = repository.list_pending(limit=10, now=NOW)
    assert [item.event_id for item in pending] == [event.event_id]
    repository.record_failure(event.event_id, failed_at=NOW, error="broker unavailable")
    repository.mark_published(event.event_id, published_at=NOW)
    assert repository.list_pending(limit=10, now=NOW) == []

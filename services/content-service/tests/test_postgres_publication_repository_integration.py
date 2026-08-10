from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from footballpulse_content_service.editorial.postgres_publication_repository import (
    PostgresPublicationRepository,
)
from footballpulse_content_service.editorial.publication import Publication
from sqlalchemy import create_engine

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)


@pytest.mark.integration
def test_postgres_publication_repository_is_idempotent() -> None:
    if os.getenv("FOOTBALLPULSE_RUN_CONTENT_INTEGRATION") != "1":
        pytest.skip("set FOOTBALLPULSE_RUN_CONTENT_INTEGRATION=1 to run")
    repository = PostgresPublicationRepository(
        create_engine(os.environ["FOOTBALLPULSE_DATABASE_URL"])
    )
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

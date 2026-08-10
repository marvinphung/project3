from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_content_service.editorial.postgres_repository import (
    PostgresEditorialRevisionRepository,
)
from footballpulse_content_service.editorial.revision import EditorialRevision, RevisionState
from sqlalchemy import create_engine

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
ARTICLE_ID = UUID(int=1)


@pytest.mark.integration
def test_postgres_repository_round_trip() -> None:
    if os.getenv("FOOTBALLPULSE_RUN_CONTENT_INTEGRATION") != "1":
        pytest.skip("set FOOTBALLPULSE_RUN_CONTENT_INTEGRATION=1 to run")
    database_url = os.environ["FOOTBALLPULSE_DATABASE_URL"]
    repository = PostgresEditorialRevisionRepository(create_engine(database_url))
    revision = EditorialRevision.create(
        revision_id=UUID(int=2),
        generated_article_id=ARTICLE_ID,
        story_id=UUID(int=3),
        story_version=1,
        revision_number=1,
        title_en="Arsenal bid",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua",
        body_vi="Arsenal đã gửi đề nghị.",
        created_at=NOW,
    )

    repository.add(revision)
    submitted = revision.submit_for_review(NOW)
    repository.update(submitted, expected_revision_number=1)

    current = repository.get_current(ARTICLE_ID)
    assert current is not None
    assert current.state is RevisionState.NEEDS_REVIEW

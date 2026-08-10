from __future__ import annotations

import os
from uuid import uuid4

import pytest
from footballpulse_api_gateway.persistence.public_read_repository import (
    PostgresPublicReadRepository,
)
from sqlalchemy import create_engine


@pytest.mark.integration
def test_postgres_public_read_repository_reads_published_article_and_timeline() -> None:
    if os.getenv("FOOTBALLPULSE_RUN_PUBLIC_API_INTEGRATION") != "1":
        pytest.skip("set FOOTBALLPULSE_RUN_PUBLIC_API_INTEGRATION=1 to run")
    repository = PostgresPublicReadRepository(
        create_engine(os.environ["FOOTBALLPULSE_DATABASE_URL"])
    )
    article = repository.get_article_by_slug(f"missing-{uuid4()}")

    assert article is None
    assert repository.list_story_timeline(uuid4()) == []

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_content_service.editorial.repository import (
    EditorialRevisionRepository,
    RevisionConflictError,
)
from footballpulse_content_service.editorial.revision import EditorialRevision

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
ARTICLE_ID = UUID(int=1)
STORY_ID = UUID(int=2)


def revision(number: int) -> EditorialRevision:
    return EditorialRevision.create(
        revision_id=UUID(int=number),
        generated_article_id=ARTICLE_ID,
        story_id=STORY_ID,
        story_version=4,
        revision_number=number,
        title_en="Arsenal bid",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua",
        body_vi="Arsenal đã gửi đề nghị.",
        created_at=NOW,
    )


def test_repository_keeps_latest_revision_and_rejects_stale_update() -> None:
    repository = EditorialRevisionRepository()
    first = revision(1)
    repository.add(first)
    second = revision(2)
    repository.add(second)

    approved = second.submit_for_review(NOW).approve(NOW)
    repository.update(approved, expected_revision_number=2)

    with pytest.raises(RevisionConflictError, match="expected revision"):
        repository.update(first.submit_for_review(NOW), expected_revision_number=1)
    assert repository.get_current(ARTICLE_ID) == approved


def test_repository_rejects_duplicate_revision_number() -> None:
    repository = EditorialRevisionRepository()
    repository.add(revision(1))

    with pytest.raises(RevisionConflictError, match="revision number"):
        repository.add(revision(1))

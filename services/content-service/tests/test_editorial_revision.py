from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_content_service.editorial.revision import (
    EditorialRevision,
    RevisionState,
)

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
ARTICLE_ID = UUID(int=1)
STORY_ID = UUID(int=2)


def revision(version: int = 1) -> EditorialRevision:
    return EditorialRevision.create(
        revision_id=UUID(int=version),
        generated_article_id=ARTICLE_ID,
        story_id=STORY_ID,
        story_version=4,
        revision_number=version,
        title_en="Arsenal bid",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua",
        body_vi="Arsenal đã gửi đề nghị.",
        created_at=NOW,
    )


def test_revision_follows_review_state_machine() -> None:
    draft = revision().submit_for_review(NOW)
    approved = draft.approve(NOW)

    assert draft.state is RevisionState.NEEDS_REVIEW
    assert approved.state is RevisionState.APPROVED


def test_revision_rejects_invalid_transition() -> None:
    with pytest.raises(ValueError, match="NEEDS_REVIEW"):
        revision().approve(NOW)


def test_story_change_marks_revision_stale() -> None:
    stale = revision().mark_stale(story_version=5, now=NOW)

    assert stale.state is RevisionState.STALE
    assert stale.story_version == 5

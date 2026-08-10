from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_content_service.editorial.repository import (
    EditorialRevisionRepository,
    RevisionConflictError,
)
from footballpulse_content_service.editorial.revision import (
    EditorialRevision,
    RevisionState,
)
from footballpulse_content_service.editorial.workflow import EditorialWorkflow

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
ARTICLE_ID = UUID(int=1)
STORY_ID = UUID(int=2)


def revision() -> EditorialRevision:
    return EditorialRevision.create(
        revision_id=UUID(int=1),
        generated_article_id=ARTICLE_ID,
        story_id=STORY_ID,
        story_version=4,
        revision_number=1,
        title_en="Arsenal bid",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua",
        body_vi="Arsenal đã gửi đề nghị.",
        created_at=NOW,
    )


def test_workflow_submits_and_approves_current_revision() -> None:
    repository = EditorialRevisionRepository()
    repository.add(revision())
    workflow = EditorialWorkflow(repository)

    submitted = workflow.submit_for_review(ARTICLE_ID, expected_revision_number=1, now=NOW)
    approved = workflow.approve(ARTICLE_ID, expected_revision_number=1, now=NOW)

    assert submitted.state is RevisionState.NEEDS_REVIEW
    assert approved.state is RevisionState.APPROVED
    assert repository.get_current(ARTICLE_ID) == approved


def test_workflow_rejects_stale_expected_revision() -> None:
    repository = EditorialRevisionRepository()
    repository.add(revision())
    workflow = EditorialWorkflow(repository)

    workflow.submit_for_review(ARTICLE_ID, expected_revision_number=1, now=NOW)
    with pytest.raises(RevisionConflictError, match="expected revision"):
        workflow.approve(ARTICLE_ID, expected_revision_number=0, now=NOW)


def test_workflow_marks_current_revision_stale_after_story_update() -> None:
    repository = EditorialRevisionRepository()
    repository.add(revision())
    workflow = EditorialWorkflow(repository)

    stale = workflow.mark_stale(
        ARTICLE_ID,
        expected_revision_number=1,
        story_version=5,
        now=NOW,
    )

    assert stale.state is RevisionState.STALE
    assert stale.story_version == 5

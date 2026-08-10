from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_api_gateway.application.editorial_admin_adapter import (
    ContentEditorialAdminAdapter,
)
from footballpulse_content_service.editorial.publication import (
    InMemoryPublicationRepository,
    PublicationService,
)
from footballpulse_content_service.editorial.repository import EditorialRevisionRepository
from footballpulse_content_service.editorial.revision import EditorialRevision

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
ARTICLE_ID = UUID(int=1)


def test_adapter_runs_revision_workflow_and_publication_service() -> None:
    revisions = EditorialRevisionRepository()
    revisions.add(
        EditorialRevision.create(
            revision_id=UUID(int=2),
            generated_article_id=ARTICLE_ID,
            story_id=UUID(int=3),
            story_version=4,
            revision_number=1,
            title_en="Arsenal bid",
            body_en="Arsenal submitted a bid.",
            title_vi="Arsenal hỏi mua",
            body_vi="Arsenal đã gửi đề nghị.",
            created_at=NOW,
        )
    )
    adapter = ContentEditorialAdminAdapter(
        revision_repository=revisions,
        publication_service=PublicationService(InMemoryPublicationRepository()),
    )

    submitted = adapter.submit_for_review(ARTICLE_ID, expected_revision_number=1, now=NOW)
    approved = adapter.approve(ARTICLE_ID, expected_revision_number=1, now=NOW)
    publication = adapter.publish(
        ARTICLE_ID, slug="arsenal-bid", idempotency_key="publish-1", now=NOW
    )

    assert submitted.state == "NEEDS_REVIEW"
    assert approved.state == "APPROVED"
    assert publication.slug == "arsenal-bid"

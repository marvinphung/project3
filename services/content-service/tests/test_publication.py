from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_content_service.editorial.publication import (
    InMemoryPublicationRepository,
    PublicationConflictError,
    PublicationService,
)
from footballpulse_content_service.editorial.revision import EditorialRevision, RevisionState

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
ARTICLE_ID = UUID(int=1)
STORY_ID = UUID(int=2)


def revision(state: RevisionState = RevisionState.APPROVED) -> EditorialRevision:
    draft = EditorialRevision.create(
        revision_id=UUID(int=3),
        generated_article_id=ARTICLE_ID,
        story_id=STORY_ID,
        story_version=4,
        revision_number=2,
        title_en="Arsenal bid",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua",
        body_vi="Arsenal đã gửi đề nghị.",
        created_at=NOW,
    )
    if state is RevisionState.NEEDS_REVIEW:
        return draft.submit_for_review(NOW)
    if state is RevisionState.APPROVED:
        return draft.submit_for_review(NOW).approve(NOW)
    return draft


def test_publish_requires_approved_revision_and_returns_immutable_snapshot() -> None:
    service = PublicationService(InMemoryPublicationRepository())

    publication = service.publish(
        revision=revision(), slug="arsenal-bid", idempotency_key="publish-1", published_at=NOW
    )

    assert publication.revision_id == UUID(int=3)
    assert publication.slug == "arsenal-bid"
    assert publication.body_vi == "Arsenal đã gửi đề nghị."


def test_publish_retry_with_same_key_returns_existing_publication() -> None:
    service = PublicationService(InMemoryPublicationRepository())
    first = service.publish(
        revision=revision(), slug="arsenal-bid", idempotency_key="publish-1", published_at=NOW
    )

    retry = service.publish(
        revision=revision(), slug="arsenal-bid", idempotency_key="publish-1", published_at=NOW
    )

    assert retry == first


def test_simultaneous_publish_requests_share_one_publication() -> None:
    service = PublicationService(InMemoryPublicationRepository())

    def publish() -> UUID:
        return service.publish(
            revision=revision(),
            slug="arsenal-bid",
            idempotency_key="publish-concurrent",
            published_at=NOW,
        ).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        publication_ids = list(pool.map(lambda _: publish(), range(2)))

    assert publication_ids[0] == publication_ids[1]


def test_publish_rejects_unapproved_revision_and_key_reuse_for_other_revision() -> None:
    service = PublicationService(InMemoryPublicationRepository())
    with pytest.raises(ValueError, match="APPROVED"):
        service.publish(
            revision=revision(RevisionState.DRAFT),
            slug="arsenal-bid",
            idempotency_key="publish-1",
            published_at=NOW,
        )

    service.publish(
        revision=revision(), slug="arsenal-bid", idempotency_key="publish-1", published_at=NOW
    )
    changed = replace(revision(), id=UUID(int=4))
    with pytest.raises(PublicationConflictError, match="idempotency key"):
        service.publish(
            revision=changed, slug="other", idempotency_key="publish-1", published_at=NOW
        )

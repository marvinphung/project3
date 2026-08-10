from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_content_service.editorial.publication import (
    InMemoryPublicationRepository,
    PublicationService,
)
from footballpulse_content_service.editorial.publication_outbox import (
    InMemoryPublicationOutbox,
    PublicationPublishedEvent,
)
from footballpulse_content_service.editorial.revision import EditorialRevision

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)


def approved_revision() -> EditorialRevision:
    draft = EditorialRevision.create(
        revision_id=UUID(int=3),
        generated_article_id=UUID(int=1),
        story_id=UUID(int=2),
        story_version=4,
        revision_number=2,
        title_en="Arsenal bid",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua",
        body_vi="Arsenal đã gửi đề nghị.",
        created_at=NOW,
    )
    return draft.submit_for_review(NOW).approve(NOW)


def test_publication_emits_one_bilingual_event_on_retry() -> None:
    outbox = InMemoryPublicationOutbox()
    service = PublicationService(InMemoryPublicationRepository(), outbox=outbox)
    revision = approved_revision()

    publication = service.publish(
        revision=revision, slug="arsenal-bid", idempotency_key="publish-1", published_at=NOW
    )
    service.publish(
        revision=revision, slug="arsenal-bid", idempotency_key="publish-1", published_at=NOW
    )

    events = outbox.pending()
    assert len(events) == 1
    assert events[0] == PublicationPublishedEvent.from_publication(publication)
    assert events[0].payload["title_vi"] == "Arsenal hỏi mua"


def test_service_uses_transactional_repository_when_available() -> None:
    class TransactionalRepository(InMemoryPublicationRepository):
        def __init__(self) -> None:
            super().__init__()
            self.transactional_calls = 0

        def create_with_outbox(self, publication, event):
            self.transactional_calls += 1
            self.add_once_event = event
            return self.create(publication)

    repository = TransactionalRepository()
    service = PublicationService(repository)
    publication = service.publish(
        revision=approved_revision(),
        slug="arsenal-bid",
        idempotency_key="publish-transactional",
        published_at=NOW,
    )

    assert repository.transactional_calls == 1
    assert repository.add_once_event.event_id == publication.id

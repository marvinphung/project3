from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from footballpulse_content_service.editorial.publication_outbox import PublicationPublishedEvent


class PublicationPublishError(RuntimeError):
    """The external event transport did not accept the publication event."""


@dataclass(frozen=True, slots=True)
class PublishBatchResult:
    attempted: int
    published: int
    failed: int


class PublicationOutboxRepository(Protocol):
    def list_pending(self, *, limit: int, now: datetime) -> list[PublicationPublishedEvent]: ...

    def mark_published(self, event_id: UUID, *, published_at: datetime) -> None: ...

    def record_failure(self, event_id: UUID, *, failed_at: datetime, error: str) -> None: ...


class PublicationEventPublisher(Protocol):
    def publish(self, event: PublicationPublishedEvent) -> None: ...


class PublicationOutboxWorker:
    def __init__(
        self,
        *,
        repository: PublicationOutboxRepository,
        publisher: PublicationEventPublisher,
        clock: Callable[[], datetime],
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._clock = clock

    def publish_pending(self, *, limit: int = 50) -> PublishBatchResult:
        if not 1 <= limit <= 100:
            raise ValueError("outbox publish limit must be between 1 and 100")
        now = self._clock()
        events = self._repository.list_pending(limit=limit, now=now)
        published = 0
        failed = 0
        for event in events:
            try:
                self._publisher.publish(event)
            except PublicationPublishError as error:
                self._repository.record_failure(event.event_id, failed_at=now, error=str(error))
                failed += 1
                continue
            self._repository.mark_published(event.event_id, published_at=now)
            published += 1
        return PublishBatchResult(len(events), published, failed)

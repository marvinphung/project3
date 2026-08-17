from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from footballpulse_runtime_config import log_event

from footballpulse_content_service.editorial.publication_outbox import PublicationPublishedEvent

LOGGER = logging.getLogger("footballpulse.content.publication_outbox")


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
        log_event(LOGGER, "publication_batch_started", pending_count=len(events), limit=limit)
        published = 0
        failed = 0
        for event in events:
            try:
                self._publisher.publish(event)
            except PublicationPublishError as error:
                self._repository.record_failure(event.event_id, failed_at=now, error=str(error))
                failed += 1
                log_event(
                    LOGGER,
                    "publication_failed",
                    level=logging.ERROR,
                    error=error,
                    event_id=str(event.event_id),
                )
                continue
            self._repository.mark_published(event.event_id, published_at=now)
            published += 1
            log_event(LOGGER, "publication_published", event_id=str(event.event_id))
        log_event(
            LOGGER,
            "publication_batch_completed",
            attempted=len(events),
            published=published,
            failed=failed,
        )
        return PublishBatchResult(len(events), published, failed)

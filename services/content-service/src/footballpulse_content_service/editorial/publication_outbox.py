from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from footballpulse_content_service.editorial.publication import Publication


@dataclass(frozen=True, slots=True)
class PublicationPublishedEvent:
    event_id: UUID
    topic: str
    key: str
    occurred_at: datetime
    payload: Mapping[str, object]

    @classmethod
    def from_publication(cls, publication: Publication) -> PublicationPublishedEvent:
        return cls(
            event_id=publication.id,
            topic="publication.published.v1",
            key=str(publication.generated_article_id),
            occurred_at=publication.published_at,
            payload={
                "event_id": str(publication.id),
                "event_type": "publication.published.v1",
                "publication_id": str(publication.id),
                "generated_article_id": str(publication.generated_article_id),
                "revision_id": str(publication.revision_id),
                "story_id": str(publication.story_id),
                "story_version": publication.story_version,
                "slug": publication.slug,
                "title_en": publication.title_en,
                "body_en": publication.body_en,
                "title_vi": publication.title_vi,
                "body_vi": publication.body_vi,
                "published_at": publication.published_at.isoformat(),
            },
        )


class PublicationOutbox(Protocol):
    def add_once(self, event: PublicationPublishedEvent) -> None: ...


class InMemoryPublicationOutbox:
    def __init__(self) -> None:
        self._events: dict[UUID, PublicationPublishedEvent] = {}

    def add_once(self, event: PublicationPublishedEvent) -> None:
        self._events.setdefault(event.event_id, event)

    def pending(self) -> list[PublicationPublishedEvent]:
        return list(self._events.values())

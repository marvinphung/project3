from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from uuid import UUID, uuid4

from footballpulse_content_service.editorial.revision import EditorialRevision, RevisionState


class PublicationConflictError(RuntimeError):
    """The publication request conflicts with an existing immutable result."""


@dataclass(frozen=True, slots=True)
class Publication:
    id: UUID
    generated_article_id: UUID
    revision_id: UUID
    story_id: UUID
    story_version: int
    slug: str
    title_en: str
    body_en: str
    title_vi: str
    body_vi: str
    idempotency_key: str
    published_at: datetime


class InMemoryPublicationRepository:
    def __init__(self) -> None:
        self._by_key: dict[str, Publication] = {}
        self._lock = Lock()

    def get_by_idempotency_key(self, key: str) -> Publication | None:
        with self._lock:
            return self._by_key.get(key)

    def create(self, publication: Publication) -> Publication:
        with self._lock:
            existing = self._by_key.get(publication.idempotency_key)
            if existing is not None:
                if existing.revision_id != publication.revision_id:
                    raise PublicationConflictError("idempotency key belongs to another revision")
                return existing
            self._by_key[publication.idempotency_key] = publication
            return publication


class PublicationService:
    def __init__(self, repository: InMemoryPublicationRepository) -> None:
        self._repository = repository

    def publish(
        self,
        *,
        revision: EditorialRevision,
        slug: str,
        idempotency_key: str,
        published_at: datetime,
    ) -> Publication:
        if revision.state is not RevisionState.APPROVED:
            raise ValueError("only APPROVED revision can be published")
        normalized_slug = "-".join(slug.strip().lower().split())
        if not normalized_slug:
            raise ValueError("slug must not be empty")
        normalized_key = idempotency_key.strip()
        if not normalized_key:
            raise ValueError("idempotency_key must not be empty")
        existing = self._repository.get_by_idempotency_key(normalized_key)
        if existing is not None:
            if existing.revision_id != revision.id:
                raise PublicationConflictError("idempotency key belongs to another revision")
            return existing
        return self._repository.create(
            Publication(
                id=uuid4(),
                generated_article_id=revision.generated_article_id,
                revision_id=revision.id,
                story_id=revision.story_id,
                story_version=revision.story_version,
                slug=normalized_slug,
                title_en=revision.title_en,
                body_en=revision.body_en,
                title_vi=revision.title_vi,
                body_vi=revision.body_vi,
                idempotency_key=normalized_key,
                published_at=published_at,
            )
        )

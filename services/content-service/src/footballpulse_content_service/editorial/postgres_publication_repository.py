from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from footballpulse_content_service.editorial.postgres_tables import (
    publication_outbox,
    publications,
)
from footballpulse_content_service.editorial.publication import (
    Publication,
    PublicationConflictError,
)
from footballpulse_content_service.editorial.publication_outbox import PublicationPublishedEvent


def _values(publication: Publication) -> dict[str, object]:
    return {
        "id": publication.id,
        "generated_article_id": publication.generated_article_id,
        "revision_id": publication.revision_id,
        "story_id": publication.story_id,
        "story_version": publication.story_version,
        "slug": publication.slug,
        "title_en": publication.title_en,
        "body_en": publication.body_en,
        "title_vi": publication.title_vi,
        "body_vi": publication.body_vi,
        "idempotency_key": publication.idempotency_key,
        "published_at": publication.published_at,
    }


def _from_row(row: RowMapping) -> Publication:
    return Publication(
        id=row["id"],
        generated_article_id=row["generated_article_id"],
        revision_id=row["revision_id"],
        story_id=row["story_id"],
        story_version=row["story_version"],
        slug=row["slug"],
        title_en=row["title_en"],
        body_en=row["body_en"],
        title_vi=row["title_vi"],
        body_vi=row["body_vi"],
        idempotency_key=row["idempotency_key"],
        published_at=row["published_at"],
    )


class PostgresPublicationRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_by_idempotency_key(self, key: str) -> Publication | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    sa.select(publications).where(publications.c.idempotency_key == key)
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else _from_row(row)

    def create(self, publication: Publication) -> Publication:
        try:
            with self._engine.begin() as connection:
                connection.execute(publications.insert().values(**_values(publication)))
        except IntegrityError as error:
            existing = self.get_by_idempotency_key(publication.idempotency_key)
            if existing is not None and existing.revision_id == publication.revision_id:
                return existing
            raise PublicationConflictError(
                "publication conflicts with existing snapshot"
            ) from error
        return publication

    def create_with_outbox(
        self,
        publication: Publication,
        event: PublicationPublishedEvent,
    ) -> Publication:
        try:
            with self._engine.begin() as connection:
                connection.execute(publications.insert().values(**_values(publication)))
                connection.execute(
                    publication_outbox.insert().values(
                        event_id=event.event_id,
                        publication_id=publication.id,
                        topic=event.topic,
                        message_key=event.key,
                        payload=dict(event.payload),
                        occurred_at=event.occurred_at,
                        state="PENDING",
                        attempt_count=0,
                        published_at=None,
                        last_error=None,
                        created_at=event.occurred_at,
                    )
                )
        except IntegrityError as error:
            existing = self.get_by_idempotency_key(publication.idempotency_key)
            if existing is not None and existing.revision_id == publication.revision_id:
                return existing
            raise PublicationConflictError(
                "publication conflicts with existing snapshot"
            ) from error
        return publication

    def list_pending(self, *, limit: int, now: datetime) -> list[PublicationPublishedEvent]:
        with self._engine.connect() as connection:
            rows = (
                connection.execute(
                    sa.select(publication_outbox)
                    .where(
                        publication_outbox.c.state == "PENDING",
                        publication_outbox.c.occurred_at <= now,
                    )
                    .order_by(publication_outbox.c.occurred_at)
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [
            PublicationPublishedEvent(
                event_id=row["event_id"],
                topic=row["topic"],
                key=row["message_key"],
                occurred_at=row["occurred_at"],
                payload=row["payload"],
            )
            for row in rows
        ]

    def mark_published(self, event_id: UUID, *, published_at: datetime) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                publication_outbox.update()
                .where(
                    publication_outbox.c.event_id == event_id,
                    publication_outbox.c.state == "PENDING",
                )
                .values(state="PUBLISHED", published_at=published_at)
            )

    def record_failure(self, event_id: UUID, *, failed_at: datetime, error: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                publication_outbox.update()
                .where(
                    publication_outbox.c.event_id == event_id,
                    publication_outbox.c.state == "PENDING",
                )
                .values(
                    attempt_count=publication_outbox.c.attempt_count + 1,
                    last_failed_at=failed_at,
                    last_error=error[:2000],
                )
            )

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from footballpulse_content_service.editorial.postgres_tables import editorial_revisions
from footballpulse_content_service.editorial.repository import RevisionConflictError
from footballpulse_content_service.editorial.revision import EditorialRevision, RevisionState


def _values(revision: EditorialRevision) -> dict[str, object]:
    return {
        "id": revision.id,
        "generated_article_id": revision.generated_article_id,
        "story_id": revision.story_id,
        "story_version": revision.story_version,
        "revision_number": revision.revision_number,
        "title_en": revision.title_en,
        "body_en": revision.body_en,
        "title_vi": revision.title_vi,
        "body_vi": revision.body_vi,
        "state": revision.state.value,
        "created_at": revision.created_at,
        "updated_at": revision.updated_at,
    }


def _from_row(row: RowMapping) -> EditorialRevision:
    return EditorialRevision(
        id=row["id"],
        generated_article_id=row["generated_article_id"],
        story_id=row["story_id"],
        story_version=row["story_version"],
        revision_number=row["revision_number"],
        title_en=row["title_en"],
        body_en=row["body_en"],
        title_vi=row["title_vi"],
        body_vi=row["body_vi"],
        state=RevisionState(row["state"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresEditorialRevisionRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, revision: EditorialRevision) -> None:
        try:
            with self._engine.begin() as connection:
                connection.execute(editorial_revisions.insert().values(**_values(revision)))
        except IntegrityError as error:
            raise RevisionConflictError("revision already exists") from error

    def get_current(self, generated_article_id: UUID) -> EditorialRevision | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    sa.select(editorial_revisions)
                    .where(editorial_revisions.c.generated_article_id == generated_article_id)
                    .order_by(editorial_revisions.c.revision_number.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else _from_row(row)

    def update(self, revision: EditorialRevision, *, expected_revision_number: int) -> None:
        values = _values(revision)
        values.pop("id")
        values.pop("created_at")
        with self._engine.begin() as connection:
            result = connection.execute(
                editorial_revisions.update()
                .where(
                    editorial_revisions.c.id == revision.id,
                    editorial_revisions.c.revision_number == expected_revision_number,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                raise RevisionConflictError("expected revision is no longer current")

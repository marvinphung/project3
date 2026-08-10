from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine, RowMapping

from footballpulse_api_gateway.api.public import PublicArticle, PublicTimelineEntry
from footballpulse_api_gateway.persistence.public_tables import publications, timeline_entries


def _article_from_row(row: RowMapping) -> PublicArticle:
    return PublicArticle(
        id=row["id"],
        slug=row["slug"],
        title_vi=row["title_vi"],
        body_vi=row["body_vi"],
        story_id=row["story_id"],
        story_version=row["story_version"],
        published_at=row["published_at"],
    )


def _timeline_from_row(row: RowMapping) -> PublicTimelineEntry:
    return PublicTimelineEntry(
        story_id=row["story_id"],
        window_start=row["window_start"],
        summary_vi=row["summary_vi"],
        confirmation=row["confirmation"],
    )


class PostgresPublicReadRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_article_by_slug(self, slug: str) -> PublicArticle | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(sa.select(publications).where(publications.c.slug == slug))
                .mappings()
                .one_or_none()
            )
        return None if row is None else _article_from_row(row)

    def list_story_timeline(self, story_id: UUID) -> list[PublicTimelineEntry]:
        with self._engine.connect() as connection:
            rows = (
                connection.execute(
                    sa.select(timeline_entries)
                    .where(timeline_entries.c.story_id == story_id)
                    .order_by(timeline_entries.c.window_start)
                )
                .mappings()
                .all()
            )
        return [_timeline_from_row(row) for row in rows]

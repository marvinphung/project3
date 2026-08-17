from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine, RowMapping

from footballpulse_api_gateway.api.public import (
    PublicArticle,
    PublicEntityStories,
    PublicEntityTag,
    PublicTimelineEntry,
)
from footballpulse_api_gateway.persistence.public_tables import (
    entities,
    publications,
    story_entities,
    timeline_entries,
)


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


def _with_entities(connection: Connection, article: PublicArticle) -> PublicArticle:
    rows = (
        connection.execute(
            sa.select(
                entities.c.id,
                entities.c.entity_type,
                entities.c.canonical_name,
                entities.c.slug,
            )
            .join(story_entities, story_entities.c.entity_id == entities.c.id)
            .where(story_entities.c.story_id == article.story_id)
            .order_by(entities.c.canonical_name)
        )
        .mappings()
        .all()
    )
    return replace(
        article,
        entities=tuple(
            PublicEntityTag(row["id"], row["entity_type"], row["canonical_name"], row["slug"])
            for row in rows
        ),
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
            return None if row is None else _with_entities(connection, _article_from_row(row))

    def list_articles(
        self, *, limit: int, offset: int, story_id: UUID | None
    ) -> list[PublicArticle]:
        statement = sa.select(publications).order_by(publications.c.published_at.desc())
        if story_id is not None:
            statement = statement.where(publications.c.story_id == story_id)
        statement = statement.offset(offset).limit(limit)
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
            return [_with_entities(connection, _article_from_row(row)) for row in rows]

    def list_story_timeline(
        self,
        story_id: UUID,
        *,
        limit: int,
        offset: int,
        confirmation: str | None,
    ) -> list[PublicTimelineEntry]:
        conditions = [timeline_entries.c.story_id == story_id]
        if confirmation is not None:
            conditions.append(timeline_entries.c.confirmation == confirmation)
        with self._engine.connect() as connection:
            rows = (
                connection.execute(
                    sa.select(timeline_entries)
                    .where(*conditions)
                    .order_by(timeline_entries.c.window_start)
                    .offset(offset)
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [_timeline_from_row(row) for row in rows]

    def list_entity_stories(self, entity_type: str, entity_slug: str) -> PublicEntityStories:
        statement = (
            sa.select(entities.c.entity_type, entities.c.slug, story_entities.c.story_id)
            .join(story_entities, story_entities.c.entity_id == entities.c.id)
            .where(entities.c.entity_type == entity_type.upper(), entities.c.slug == entity_slug)
            .distinct()
            .order_by(story_entities.c.story_id)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return PublicEntityStories(
            entity_type=entity_type.upper(),
            entity_slug=entity_slug,
            story_ids=tuple(row["story_id"] for row in rows),
        )

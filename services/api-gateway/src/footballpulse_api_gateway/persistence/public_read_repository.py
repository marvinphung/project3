from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine, RowMapping

from footballpulse_api_gateway.api.public import (
    PublicArticle,
    PublicArticlePage,
    PublicArticleSource,
    PublicEntity,
    PublicEntityPage,
    PublicEntityStories,
    PublicEntityTag,
    PublicStory,
    PublicTimelineEntry,
)
from footballpulse_api_gateway.persistence.public_tables import (
    entities,
    publications,
    sources,
    stories,
    story_entities,
    story_sources,
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

    def get_story(self, story_id: UUID) -> PublicStory | None:
        published_story = sa.exists(
            sa.select(publications.c.id).where(publications.c.story_id == stories.c.id)
        )
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    sa.select(stories).where(stories.c.id == story_id, published_story)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        return PublicStory(
            row["id"],
            row["event_type"],
            row["status"],
            float(row["confidence_score"]),
            row["version"],
            row["first_seen_at"],
            row["last_seen_at"],
        )

    def list_article_sources(self, slug: str) -> tuple[PublicArticleSource, ...]:
        statement = (
            sa.select(
                sources.c.id,
                sources.c.name,
                sources.c.rss_url,
                story_sources.c.published_at,
                story_sources.c.source_reliability_tier,
            )
            .join(story_sources, story_sources.c.source_id == sources.c.id)
            .join(publications, publications.c.story_id == story_sources.c.story_id)
            .where(publications.c.slug == slug)
            .distinct()
            .order_by(story_sources.c.published_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return tuple(
            PublicArticleSource(
                row["id"],
                row["name"],
                row["rss_url"],
                row["published_at"],
                row["source_reliability_tier"],
            )
            for row in rows
        )

    def list_entities(
        self, *, entity_type: str | None, query: str | None, limit: int, offset: int
    ) -> PublicEntityPage:
        published = (
            sa.select(
                story_entities.c.entity_id.label("entity_id"),
                sa.func.count(sa.distinct(publications.c.story_id)).label("story_count"),
                sa.func.count(sa.distinct(publications.c.id)).label("article_count"),
            )
            .join(publications, publications.c.story_id == story_entities.c.story_id)
            .group_by(story_entities.c.entity_id)
            .subquery()
        )
        conditions = []
        if entity_type is not None:
            conditions.append(entities.c.entity_type == entity_type.upper())
        if query is not None:
            conditions.append(entities.c.canonical_name.ilike(f"%{query.strip()}%"))
        base = (
            sa.select(
                entities.c.id,
                entities.c.entity_type,
                entities.c.canonical_name.label("name"),
                entities.c.slug,
                published.c.story_count,
                published.c.article_count,
            )
            .join(published, published.c.entity_id == entities.c.id)
            .where(*conditions)
        )
        statement = (
            base.order_by(published.c.article_count.desc(), entities.c.canonical_name)
            .offset(offset)
            .limit(limit)
        )
        count_statement = sa.select(sa.func.count()).select_from(base.subquery())
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
            total = connection.execute(count_statement).scalar_one()
        return PublicEntityPage(
            tuple(
                PublicEntity(
                    row["id"],
                    row["entity_type"],
                    row["name"],
                    row["slug"],
                    row["story_count"],
                    row["article_count"],
                )
                for row in rows
            ),
            total,
        )

    def get_entity(self, entity_type: str, entity_slug: str) -> PublicEntity | None:
        page = self.list_entities(entity_type=entity_type, query=None, limit=100, offset=0)
        return next((item for item in page.items if item.slug == entity_slug), None)

    def list_articles(
        self,
        *,
        limit: int,
        offset: int,
        story_id: UUID | None,
        query: str | None,
        entity_type: str | None,
        entity_slug: str | None,
        sort: str,
    ) -> PublicArticlePage:
        conditions: list[sa.ColumnElement[bool]] = []
        if story_id is not None:
            conditions.append(publications.c.story_id == story_id)
        if query is not None:
            pattern = f"%{query.strip()}%"
            conditions.append(
                sa.or_(
                    publications.c.title_vi.ilike(pattern), publications.c.body_vi.ilike(pattern)
                )
            )
        if entity_type is not None and entity_slug is not None:
            entity_story = (
                sa.select(story_entities.c.story_id)
                .join(entities, entities.c.id == story_entities.c.entity_id)
                .where(
                    entities.c.entity_type == entity_type.upper(),
                    entities.c.slug == entity_slug,
                )
            )
            conditions.append(publications.c.story_id.in_(entity_story))
        order = (
            publications.c.published_at.asc()
            if sort == "oldest"
            else publications.c.published_at.desc()
        )
        statement = (
            sa.select(publications).where(*conditions).order_by(order).offset(offset).limit(limit)
        )
        count_statement = sa.select(sa.func.count()).select_from(publications).where(*conditions)
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
            total = connection.execute(count_statement).scalar_one()
            items = tuple(_with_entities(connection, _article_from_row(row)) for row in rows)
        return PublicArticlePage(items, total)

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

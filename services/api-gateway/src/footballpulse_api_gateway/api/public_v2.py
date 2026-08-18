from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.engine import Engine


class V2EntityTag(BaseModel):
    id: UUID
    entity_type: str
    name: str
    slug: str


class V2ArticleResponse(BaseModel):
    id: UUID
    slug: str
    title_en: str
    title_vi: str
    excerpt_vi: str | None
    body_en: str
    body_vi: str
    story_id: UUID | None
    published_at: datetime
    entities: list[V2EntityTag] = []


class V2ArticleListResponse(BaseModel):
    items: list[V2ArticleResponse]
    limit: int
    offset: int


class V2SourceResponse(BaseModel):
    source_id: UUID
    source_name: str
    source_url: str
    published_at: datetime | None
    reliability_tier: int


class V2SourceListResponse(BaseModel):
    items: list[V2SourceResponse]


class V2TimelineEntry(BaseModel):
    story_id: UUID
    happened_at: datetime
    summary_en: str
    summary_vi: str
    confirmation: str


class V2TimelineResponse(BaseModel):
    items: list[V2TimelineEntry]


class V2EntityResponse(BaseModel):
    id: UUID
    entity_type: str
    name: str
    slug: str
    story_count: int
    article_count: int


class V2EntityListResponse(BaseModel):
    items: list[V2EntityResponse]
    limit: int
    offset: int
    total: int


class V2StoryResponse(BaseModel):
    id: UUID
    title_en: str
    title_vi: str
    summary_en: str | None
    summary_vi: str | None
    event_type: str
    status: str
    confirmation: str
    first_seen_at: datetime
    last_seen_at: datetime
    entity_ids: list[UUID]


class V2EntityStoriesResponse(BaseModel):
    entity_type: str
    entity_slug: str
    story_ids: list[UUID]


def create_public_v2_app(engine: Engine) -> FastAPI:
    app = FastAPI(title="FootballPulse Public API v2", version="2.0.0")

    def entity_tags(connection: sa.Connection, story_id: UUID | None) -> list[V2EntityTag]:
        if story_id is None:
            return []
        statement = sa.text(
            """select e.id, e.entity_type::text as entity_type, e.name, e.slug
            from story_entities se
            join entities e on e.id = se.entity_id
            where se.story_id = :story_id
            order by e.name"""
        )
        rows = connection.execute(statement, {"story_id": story_id}).mappings().all()
        return [V2EntityTag.model_validate(row) for row in rows]

    @app.get("/api/v2/articles", response_model=V2ArticleListResponse)
    async def list_articles(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        story_id: UUID | None = Query(None),
        q: str | None = Query(None),
        entity_type: str | None = Query(None),
        entity_slug: str | None = Query(None),
    ) -> V2ArticleListResponse:
        if (entity_type is None) != (entity_slug is None):
            raise HTTPException(status_code=422, detail="entity_type and entity_slug must be provided together")
        query = f"%{q.strip()}%" if q and q.strip() else None
        conditions = ["p.status = 'PUBLISHED'"]
        params: dict[str, object] = {
            "limit": limit,
            "offset": offset,
        }
        if story_id is not None:
            conditions.append("p.story_id = :story_id")
            params["story_id"] = story_id
        if query is not None:
            conditions.append(
                """(
                p.title_vi ilike :query
                or p.body_vi ilike :query
                or p.title_en ilike :query
                or p.body_en ilike :query
              )"""
            )
            params["query"] = query
        if entity_type is not None and entity_slug is not None:
            conditions.append(
                """exists (
                  select 1
                  from story_entities se
                  join entities e on e.id = se.entity_id
                  where se.story_id = p.story_id
                    and e.entity_type::text = upper(:entity_type)
                    and e.slug = :entity_slug
                )"""
            )
            params["entity_type"] = entity_type
            params["entity_slug"] = entity_slug
        statement = sa.text(
            f"""select p.id, p.slug, p.title_en, p.title_vi, p.excerpt_vi, p.body_en, p.body_vi,
            p.story_id, p.published_at
            from publications p
            where {' and '.join(conditions)}
            order by p.published_at desc limit :limit offset :offset"""
        )
        with engine.connect() as connection:
            rows = connection.execute(
                statement,
                params,
            ).mappings().all()
            items = [
                V2ArticleResponse.model_validate({**row, "entities": entity_tags(connection, row["story_id"])})
                for row in rows
            ]
        return V2ArticleListResponse(
            items=items,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/v2/articles/{slug}", response_model=V2ArticleResponse)
    async def get_article(slug: str) -> V2ArticleResponse:
        statement = sa.text(
            """select id, slug, title_en, title_vi, excerpt_vi, body_en, body_vi,
            story_id, published_at from publications
            where slug = :slug and status = 'PUBLISHED'"""
        )
        with engine.connect() as connection:
            row = connection.execute(statement, {"slug": slug}).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="article not found")
        with engine.connect() as connection:
            return V2ArticleResponse.model_validate(
                {**row, "entities": entity_tags(connection, row["story_id"])}
            )

    @app.get("/api/v2/articles/{slug}/sources", response_model=V2SourceListResponse)
    async def get_article_sources(slug: str) -> V2SourceListResponse:
        statement = sa.text(
            """select s.id as source_id, s.name as source_name, s.homepage_url as source_url,
            a.published_at, s.reliability_tier from story_sources ss
            join sources s on s.id = ss.source_id join articles a on a.id = ss.article_id
            join publications p on p.story_id = ss.story_id where p.slug = :slug
            order by a.published_at desc"""
        )
        with engine.connect() as connection:
            rows = connection.execute(statement, {"slug": slug}).mappings().all()
        return V2SourceListResponse(items=[V2SourceResponse.model_validate(row) for row in rows])

    @app.get("/api/v2/stories/{story_id}/timeline", response_model=V2TimelineResponse)
    async def get_story_timeline(
        story_id: UUID,
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0),
        confirmation: str | None = Query(None),
    ) -> V2TimelineResponse:
        statement = sa.text(
            """select story_id, happened_at, summary_en, summary_vi, confirmation
            from timeline_entries where story_id = :story_id
              and (:confirmation is null or confirmation::text = upper(:confirmation))
            order by happened_at desc limit :limit offset :offset"""
        )
        with engine.connect() as connection:
            rows = connection.execute(
                statement,
                {
                    "story_id": story_id,
                    "confirmation": confirmation,
                    "limit": limit,
                    "offset": offset,
                },
            ).mappings().all()
        return V2TimelineResponse(items=[V2TimelineEntry.model_validate(row) for row in rows])

    @app.get("/api/v2/entities", response_model=V2EntityListResponse)
    async def list_entities(
        type: str | None = Query(None),
        q: str | None = Query(None),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> V2EntityListResponse:
        query = f"%{q.strip()}%" if q and q.strip() else None
        statement = sa.text(
            """with published as (
              select se.entity_id,
                     count(distinct p.story_id) as story_count,
                     count(distinct p.id) as article_count
              from story_entities se
              join publications p on p.story_id = se.story_id
              where p.status = 'PUBLISHED'
              group by se.entity_id
            )
            select e.id, e.entity_type::text as entity_type, e.name, e.slug,
                   published.story_count, published.article_count
            from entities e
            join published on published.entity_id = e.id
            where (:entity_type is null or e.entity_type::text = upper(:entity_type))
              and (:query is null or e.name ilike :query)
            order by published.article_count desc, e.name asc
            limit :limit offset :offset"""
        )
        count_statement = sa.text(
            """with published as (
              select se.entity_id
              from story_entities se
              join publications p on p.story_id = se.story_id
              where p.status = 'PUBLISHED'
              group by se.entity_id
            )
            select count(*)
            from entities e
            join published on published.entity_id = e.id
            where (:entity_type is null or e.entity_type::text = upper(:entity_type))
              and (:query is null or e.name ilike :query)"""
        )
        params = {"entity_type": type, "query": query, "limit": limit, "offset": offset}
        with engine.connect() as connection:
            rows = connection.execute(statement, params).mappings().all()
            total = connection.execute(count_statement, params).scalar_one()
        return V2EntityListResponse(
            items=[V2EntityResponse.model_validate(row) for row in rows],
            limit=limit,
            offset=offset,
            total=total,
        )

    @app.get("/api/v2/entities/{entity_type}/{entity_slug}", response_model=V2EntityResponse)
    async def get_entity(entity_type: str, entity_slug: str) -> V2EntityResponse:
        statement = sa.text(
            """with published as (
              select se.entity_id,
                     count(distinct p.story_id) as story_count,
                     count(distinct p.id) as article_count
              from story_entities se
              join publications p on p.story_id = se.story_id
              where p.status = 'PUBLISHED'
              group by se.entity_id
            )
            select e.id, e.entity_type::text as entity_type, e.name, e.slug,
                   published.story_count, published.article_count
            from entities e
            join published on published.entity_id = e.id
            where e.entity_type::text = upper(:entity_type) and e.slug = :entity_slug"""
        )
        with engine.connect() as connection:
            row = connection.execute(
                statement,
                {"entity_type": entity_type, "entity_slug": entity_slug},
            ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="entity not found")
        return V2EntityResponse.model_validate(row)

    @app.get(
        "/api/v2/entities/{entity_type}/{entity_slug}/stories",
        response_model=V2EntityStoriesResponse,
    )
    async def get_entity_stories(entity_type: str, entity_slug: str) -> V2EntityStoriesResponse:
        statement = sa.text(
            """select distinct p.story_id
            from publications p
            join story_entities se on se.story_id = p.story_id
            join entities e on e.id = se.entity_id
            where p.status = 'PUBLISHED'
              and e.entity_type::text = upper(:entity_type)
              and e.slug = :entity_slug
            order by p.story_id"""
        )
        with engine.connect() as connection:
            story_ids = [
                row["story_id"]
                for row in connection.execute(
                    statement,
                    {"entity_type": entity_type, "entity_slug": entity_slug},
                ).mappings().all()
            ]
        return V2EntityStoriesResponse(
            entity_type=entity_type.upper(),
            entity_slug=entity_slug,
            story_ids=story_ids,
        )

    @app.get("/api/v2/stories/{story_id}", response_model=V2StoryResponse)
    async def get_story(story_id: UUID) -> V2StoryResponse:
        statement = sa.text(
            """select s.id, s.title_en, s.title_vi, s.summary_en, s.summary_vi,
            s.event_type, s.status::text as status, s.confirmation::text as confirmation,
            s.first_seen_at, s.last_seen_at
            from stories s
            where s.id = :story_id
              and exists (
                select 1 from publications p
                where p.story_id = s.id and p.status = 'PUBLISHED'
              )"""
        )
        entity_statement = sa.text(
            """select entity_id from story_entities where story_id = :story_id order by entity_id"""
        )
        with engine.connect() as connection:
            row = connection.execute(statement, {"story_id": story_id}).mappings().one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="story not found")
            entity_ids = [
                item["entity_id"]
                for item in connection.execute(entity_statement, {"story_id": story_id}).mappings().all()
            ]
        return V2StoryResponse.model_validate({**row, "entity_ids": entity_ids})

    return app

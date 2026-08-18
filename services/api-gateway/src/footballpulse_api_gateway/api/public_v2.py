from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from fastapi import FastAPI, Query
from pydantic import BaseModel
from sqlalchemy.engine import Engine


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


def create_public_v2_app(engine: Engine) -> FastAPI:
    app = FastAPI(title="FootballPulse Public API v2", version="2.0.0")

    @app.get("/api/v2/articles", response_model=V2ArticleListResponse)
    async def list_articles(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> V2ArticleListResponse:
        statement = sa.text(
            """select id, slug, title_en, title_vi, excerpt_vi, body_en, body_vi,
            story_id, published_at from publications where status = 'PUBLISHED'
            order by published_at desc limit :limit offset :offset"""
        )
        with engine.connect() as connection:
            rows = connection.execute(statement, {"limit": limit, "offset": offset}).mappings().all()
        return V2ArticleListResponse(
            items=[V2ArticleResponse.model_validate(row) for row in rows],
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
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="article not found")
        return V2ArticleResponse.model_validate(row)

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
    async def get_story_timeline(story_id: UUID) -> V2TimelineResponse:
        statement = sa.text(
            """select story_id, happened_at, summary_en, summary_vi, confirmation
            from timeline_entries where story_id = :story_id
            order by happened_at desc limit 100"""
        )
        with engine.connect() as connection:
            rows = connection.execute(statement, {"story_id": story_id}).mappings().all()
        return V2TimelineResponse(items=[V2TimelineEntry.model_validate(row) for row in rows])

    return app

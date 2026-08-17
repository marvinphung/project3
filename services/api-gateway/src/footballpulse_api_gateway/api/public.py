from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import FastAPI, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True, slots=True)
class PublicArticle:
    id: UUID
    slug: str
    title_vi: str
    body_vi: str
    story_id: UUID
    story_version: int
    published_at: datetime
    entities: tuple[PublicEntityTag, ...] = ()


@dataclass(frozen=True, slots=True)
class PublicEntityTag:
    id: UUID
    entity_type: str
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class PublicTimelineEntry:
    story_id: UUID
    window_start: datetime
    summary_vi: str
    confirmation: str


@dataclass(frozen=True, slots=True)
class PublicEntityStories:
    entity_type: str
    entity_slug: str
    story_ids: tuple[UUID, ...]


class PublicReadRepository(Protocol):
    def get_article_by_slug(self, slug: str) -> PublicArticle | None: ...

    def list_articles(
        self, *, limit: int, offset: int, story_id: UUID | None
    ) -> list[PublicArticle]: ...

    def list_story_timeline(
        self,
        story_id: UUID,
        *,
        limit: int,
        offset: int,
        confirmation: str | None,
    ) -> list[PublicTimelineEntry]: ...

    def list_entity_stories(self, entity_type: str, entity_slug: str) -> PublicEntityStories: ...


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title_vi: str
    body_vi: str
    story_id: UUID
    story_version: int
    published_at: datetime
    entities: list[EntityTagResponse]


class EntityTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    name: str
    slug: str


class ArticleListResponse(BaseModel):
    items: list[ArticleResponse]


class TimelineEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    story_id: UUID
    window_start: datetime
    summary_vi: str
    confirmation: str


class TimelineResponse(BaseModel):
    items: list[TimelineEntryResponse]


class EntityStoriesResponse(BaseModel):
    entity_type: str
    entity_slug: str
    story_ids: list[UUID]


def create_public_app(repository: PublicReadRepository) -> FastAPI:
    app = FastAPI(title="FootballPulse Public API", version="0.1.0")

    @app.get("/api/v1/articles", response_model=ArticleListResponse)
    async def list_articles(
        response: Response,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        story_id: Annotated[UUID | None, Query()] = None,
    ) -> ArticleListResponse:
        response.headers["Cache-Control"] = "public, max-age=30"
        return ArticleListResponse(
            items=[
                ArticleResponse.model_validate(item)
                for item in repository.list_articles(limit=limit, offset=offset, story_id=story_id)
            ]
        )

    @app.get("/api/v1/articles/{slug}", response_model=ArticleResponse)
    async def get_article(slug: str, response: Response) -> ArticleResponse | JSONResponse:
        article = repository.get_article_by_slug(slug)
        if article is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "ARTICLE_NOT_FOUND", "message": "article not found"}},
            )
        response.headers["Cache-Control"] = "public, max-age=60"
        return ArticleResponse.model_validate(article)

    @app.get("/api/v1/stories/{story_id}/timeline", response_model=TimelineResponse)
    async def get_story_timeline(
        story_id: UUID,
        response: Response,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        confirmation: str | None = Query(None, min_length=1),
    ) -> TimelineResponse:
        response.headers["Cache-Control"] = "public, max-age=30"
        return TimelineResponse(
            items=[
                TimelineEntryResponse.model_validate(item)
                for item in repository.list_story_timeline(
                    story_id,
                    limit=limit,
                    offset=offset,
                    confirmation=confirmation,
                )
            ]
        )

    @app.get(
        "/api/v1/entities/{entity_type}/{entity_slug}/stories",
        response_model=EntityStoriesResponse,
    )
    async def get_entity_stories(entity_type: str, entity_slug: str) -> EntityStoriesResponse:
        result = repository.list_entity_stories(entity_type, entity_slug)
        return EntityStoriesResponse(
            entity_type=result.entity_type,
            entity_slug=result.entity_slug,
            story_ids=list(result.story_ids),
        )

    return app

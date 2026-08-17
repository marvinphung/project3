from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response
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
class PublicArticlePage:
    items: tuple[PublicArticle, ...]
    total: int


@dataclass(frozen=True, slots=True)
class PublicStory:
    id: UUID
    event_type: str
    status: str
    confidence_score: float
    version: int
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True, slots=True)
class PublicArticleSource:
    source_id: UUID
    source_name: str
    source_url: str
    published_at: datetime
    reliability_tier: int


@dataclass(frozen=True, slots=True)
class PublicEntityTag:
    id: UUID
    entity_type: str
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class PublicEntity:
    id: UUID
    entity_type: str
    name: str
    slug: str
    story_count: int
    article_count: int


@dataclass(frozen=True, slots=True)
class PublicEntityPage:
    items: tuple[PublicEntity, ...]
    total: int


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
    def get_story(self, story_id: UUID) -> PublicStory | None: ...

    def list_article_sources(self, slug: str) -> tuple[PublicArticleSource, ...]: ...

    def list_entities(
        self, *, entity_type: str | None, query: str | None, limit: int, offset: int
    ) -> PublicEntityPage: ...

    def get_entity(self, entity_type: str, entity_slug: str) -> PublicEntity | None: ...

    def get_article_by_slug(self, slug: str) -> PublicArticle | None: ...

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
    ) -> PublicArticlePage: ...

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


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    name: str
    slug: str
    story_count: int
    article_count: int


class EntityListResponse(BaseModel):
    items: list[EntityResponse]
    total: int
    limit: int
    offset: int
    next_offset: int | None


class ArticleListResponse(BaseModel):
    items: list[ArticleResponse]
    total: int
    limit: int
    offset: int
    next_offset: int | None


class StoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    status: str
    confidence_score: float
    version: int
    first_seen_at: datetime
    last_seen_at: datetime


class ArticleSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: UUID
    source_name: str
    source_url: str
    published_at: datetime
    reliability_tier: int


class ArticleSourceListResponse(BaseModel):
    items: list[ArticleSourceResponse]


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
        q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
        entity_type: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
        entity_slug: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
        sort: Literal["newest", "oldest"] = "newest",
    ) -> ArticleListResponse:
        if (entity_type is None) is not (entity_slug is None):
            raise HTTPException(422, "entity_type and entity_slug must be supplied together")
        response.headers["Cache-Control"] = "public, max-age=30"
        page = repository.list_articles(
            limit=limit,
            offset=offset,
            story_id=story_id,
            query=q,
            entity_type=entity_type,
            entity_slug=entity_slug,
            sort=sort,
        )
        next_offset = offset + len(page.items)
        return ArticleListResponse(
            items=[ArticleResponse.model_validate(item) for item in page.items],
            total=page.total,
            limit=limit,
            offset=offset,
            next_offset=next_offset if next_offset < page.total else None,
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

    @app.get("/api/v1/articles/{slug}/sources", response_model=ArticleSourceListResponse)
    async def get_article_sources(slug: str) -> ArticleSourceListResponse | JSONResponse:
        if repository.get_article_by_slug(slug) is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "ARTICLE_NOT_FOUND", "message": "article not found"}},
            )
        return ArticleSourceListResponse(
            items=[
                ArticleSourceResponse.model_validate(item)
                for item in repository.list_article_sources(slug)
            ]
        )

    @app.get("/api/v1/entities", response_model=EntityListResponse)
    async def list_entities(
        response: Response,
        entity_type: Annotated[str | None, Query(alias="type", max_length=32)] = None,
        q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> EntityListResponse:
        page = repository.list_entities(
            entity_type=entity_type,
            query=q,
            limit=limit,
            offset=offset,
        )
        response.headers["Cache-Control"] = "public, max-age=60"
        next_offset = offset + len(page.items)
        return EntityListResponse(
            items=[EntityResponse.model_validate(item) for item in page.items],
            total=page.total,
            limit=limit,
            offset=offset,
            next_offset=next_offset if next_offset < page.total else None,
        )

    @app.get("/api/v1/entities/{entity_type}/{entity_slug}", response_model=EntityResponse)
    async def get_entity(entity_type: str, entity_slug: str) -> EntityResponse | JSONResponse:
        entity = repository.get_entity(entity_type, entity_slug)
        if entity is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "ENTITY_NOT_FOUND", "message": "entity not found"}},
            )
        return EntityResponse.model_validate(entity)

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

    @app.get("/api/v1/stories/{story_id}", response_model=StoryResponse)
    async def get_story(story_id: UUID) -> StoryResponse | JSONResponse:
        story = repository.get_story(story_id)
        if story is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "STORY_NOT_FOUND", "message": "story not found"}},
            )
        return StoryResponse.model_validate(story)

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

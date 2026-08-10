from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
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


@dataclass(frozen=True, slots=True)
class PublicTimelineEntry:
    story_id: UUID
    window_start: datetime
    summary_vi: str
    confirmation: str


class PublicReadRepository(Protocol):
    def get_article_by_slug(self, slug: str) -> PublicArticle | None: ...

    def list_story_timeline(
        self,
        story_id: UUID,
        *,
        limit: int,
        offset: int,
        confirmation: str | None,
    ) -> list[PublicTimelineEntry]: ...


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title_vi: str
    body_vi: str
    story_id: UUID
    story_version: int
    published_at: datetime


class TimelineEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    story_id: UUID
    window_start: datetime
    summary_vi: str
    confirmation: str


class TimelineResponse(BaseModel):
    items: list[TimelineEntryResponse]


def create_public_app(repository: PublicReadRepository) -> FastAPI:
    app = FastAPI(title="FootballPulse Public API", version="0.1.0")

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

    return app

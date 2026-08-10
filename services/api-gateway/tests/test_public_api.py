from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from footballpulse_api_gateway.api.public import (
    PublicArticle,
    PublicTimelineEntry,
    create_public_app,
)

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
ARTICLE = PublicArticle(
    id=UUID(int=1),
    slug="arsenal-bid",
    title_vi="Arsenal hỏi mua Vinícius",
    body_vi="Arsenal đã gửi đề nghị.",
    story_id=UUID(int=2),
    story_version=4,
    published_at=NOW,
)
TIMELINE = PublicTimelineEntry(
    story_id=UUID(int=2),
    window_start=NOW,
    summary_vi="Arsenal đã gửi đề nghị.",
    confirmation="REPORTED",
)


class MemoryPublicRepository:
    def get_article_by_slug(self, slug: str) -> PublicArticle | None:
        return ARTICLE if slug == ARTICLE.slug else None

    def list_story_timeline(self, story_id: UUID) -> list[PublicTimelineEntry]:
        return [TIMELINE] if story_id == ARTICLE.story_id else []


@pytest.mark.asyncio
async def test_public_article_and_story_timeline_routes() -> None:
    transport = httpx.ASGITransport(app=create_public_app(MemoryPublicRepository()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        article = await client.get("/api/v1/articles/arsenal-bid")
        timeline = await client.get(f"/api/v1/stories/{ARTICLE.story_id}/timeline")

        assert article.status_code == 200
        assert article.json()["title_vi"] == "Arsenal hỏi mua Vinícius"
        assert timeline.status_code == 200
        assert timeline.json()["items"][0]["confirmation"] == "REPORTED"


@pytest.mark.asyncio
async def test_public_article_returns_not_found_envelope() -> None:
    transport = httpx.ASGITransport(app=create_public_app(MemoryPublicRepository()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/articles/missing")

        assert response.status_code == 404
        assert response.json() == {
            "error": {"code": "ARTICLE_NOT_FOUND", "message": "article not found"}
        }

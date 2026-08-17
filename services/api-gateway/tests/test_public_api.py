from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
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
    entities=(PublicEntityTag(UUID(int=3), "PLAYER", "Vinícius Júnior", "vinicius"),),
)
TIMELINE = PublicTimelineEntry(
    story_id=UUID(int=2),
    window_start=NOW,
    summary_vi="Arsenal đã gửi đề nghị.",
    confirmation="REPORTED",
)


class MemoryPublicRepository:
    last_article_query: dict[str, object] = {}

    def list_entity_stories(self, entity_type: str, entity_slug: str) -> PublicEntityStories:
        return PublicEntityStories(entity_type, entity_slug, (ARTICLE.story_id,))

    def list_entities(
        self, *, entity_type: str | None, query: str | None, limit: int, offset: int
    ) -> PublicEntityPage:
        entity = PublicEntity(UUID(int=3), "PLAYER", "Vinícius Júnior", "vinicius", 1, 1)
        return PublicEntityPage((entity,), 1)

    def get_entity(self, entity_type: str, entity_slug: str) -> PublicEntity | None:
        if entity_type.upper() != "PLAYER" or entity_slug != "vinicius":
            return None
        return PublicEntity(UUID(int=3), "PLAYER", "Vinícius Júnior", "vinicius", 1, 1)

    def get_story(self, story_id: UUID) -> PublicStory | None:
        return (
            PublicStory(story_id, "TRANSFER", "DEVELOPING", 0.75, 4, NOW, NOW)
            if story_id == ARTICLE.story_id
            else None
        )

    def list_article_sources(self, slug: str) -> tuple[PublicArticleSource, ...]:
        if slug != ARTICLE.slug:
            return ()
        return (PublicArticleSource(UUID(int=5), "BBC Sport", "https://bbc.example/rss", NOW, 1),)

    def get_article_by_slug(self, slug: str) -> PublicArticle | None:
        return ARTICLE if slug == ARTICLE.slug else None

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
        self.last_article_query = {
            "query": query,
            "entity_type": entity_type,
            "entity_slug": entity_slug,
            "sort": sort,
        }
        if story_id is not None and story_id != ARTICLE.story_id:
            return PublicArticlePage((), 0)
        items = [ARTICLE][offset : offset + limit]
        return PublicArticlePage(tuple(items), 1)

    def list_story_timeline(
        self, story_id: UUID, *, limit: int, offset: int, confirmation: str | None
    ) -> list[PublicTimelineEntry]:
        if story_id != ARTICLE.story_id or (confirmation and TIMELINE.confirmation != confirmation):
            return []
        return [TIMELINE][offset : offset + limit]


@pytest.mark.asyncio
async def test_public_article_and_story_timeline_routes() -> None:
    transport = httpx.ASGITransport(app=create_public_app(MemoryPublicRepository()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        article = await client.get("/api/v1/articles/arsenal-bid")
        timeline = await client.get(
            f"/api/v1/stories/{ARTICLE.story_id}/timeline?limit=10&offset=0&confirmation=REPORTED"
        )
        entity_stories = await client.get("/api/v1/entities/player/vinicius/stories")

        assert article.status_code == 200
        assert article.json()["title_vi"] == "Arsenal hỏi mua Vinícius"
        assert article.json()["entities"][0]["slug"] == "vinicius"
        assert article.headers["cache-control"] == "public, max-age=60"
        assert timeline.status_code == 200
        assert timeline.json()["items"][0]["confirmation"] == "REPORTED"
        assert timeline.headers["cache-control"] == "public, max-age=30"
        assert entity_stories.status_code == 200
        assert entity_stories.json()["story_ids"] == [str(ARTICLE.story_id)]


@pytest.mark.asyncio
async def test_public_article_returns_not_found_envelope() -> None:
    transport = httpx.ASGITransport(app=create_public_app(MemoryPublicRepository()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/articles/missing")

        assert response.status_code == 404
        assert response.json() == {
            "error": {"code": "ARTICLE_NOT_FOUND", "message": "article not found"}
        }


@pytest.mark.asyncio
async def test_public_entity_directory_and_detail_routes() -> None:
    transport = httpx.ASGITransport(app=create_public_app(MemoryPublicRepository()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        listing = await client.get("/api/v1/entities?type=PLAYER&q=Vini&limit=10&offset=0")
        detail = await client.get("/api/v1/entities/player/vinicius")
        missing = await client.get("/api/v1/entities/club/missing")

    assert listing.status_code == 200
    assert listing.json()["items"][0]["article_count"] == 1
    assert listing.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["story_count"] == 1
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_public_story_detail_and_article_sources_routes() -> None:
    transport = httpx.ASGITransport(app=create_public_app(MemoryPublicRepository()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        story = await client.get(f"/api/v1/stories/{ARTICLE.story_id}")
        sources = await client.get(f"/api/v1/articles/{ARTICLE.slug}/sources")

    assert story.status_code == 200
    assert story.json()["event_type"] == "TRANSFER"
    assert sources.status_code == 200
    assert sources.json()["items"][0]["source_name"] == "BBC Sport"


@pytest.mark.asyncio
async def test_public_article_list_supports_pagination_and_story_filter() -> None:
    repository = MemoryPublicRepository()
    transport = httpx.ASGITransport(app=create_public_app(repository))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/articles?limit=10&offset=0&story_id={ARTICLE.story_id}"
            "&q=Arsenal&entity_type=PLAYER&entity_slug=vinicius&sort=oldest"
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["slug"] == "arsenal-bid"
    assert response.json()["total"] == 1
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 0
    assert response.json()["next_offset"] is None
    assert repository.last_article_query == {
        "query": "Arsenal",
        "entity_type": "PLAYER",
        "entity_slug": "vinicius",
        "sort": "oldest",
    }


@pytest.mark.asyncio
async def test_public_article_list_rejects_entity_filter_without_complete_pair() -> None:
    transport = httpx.ASGITransport(app=create_public_app(MemoryPublicRepository()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/articles?entity_type=PLAYER")

    assert response.status_code == 422

from datetime import UTC, datetime
from uuid import UUID, uuid4
from unittest.mock import MagicMock

import httpx
import pytest
from footballpulse_api_gateway.api.public_v2 import create_public_v2_app


@pytest.mark.asyncio
async def test_top_entities_endpoint() -> None:
    engine_mock = MagicMock()
    conn_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value = conn_mock

    arsenal_id = UUID("11111111-1111-1111-1111-111111111111")
    conn_mock.execute.return_value.mappings.return_value.all.return_value = [
        {
            "id": arsenal_id,
            "entity_type": "CLUB",
            "canonical_name": "Arsenal",
            "slug": "arsenal",
            "aliases": ["Gunners"],
            "mention_count_24h": 5,
            "last_seen_at": datetime.now(UTC),
        }
    ]

    app = create_public_v2_app(engine_mock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v2/entities/top?limit=10")

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert len(data["items"]) == 1
    assert data["items"][0]["canonical_name"] == "Arsenal"
    assert data["items"][0]["mention_count_24h"] == 5


@pytest.mark.asyncio
async def test_search_entities_endpoint() -> None:
    engine_mock = MagicMock()
    conn_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value = conn_mock

    conn_mock.execute.return_value.mappings.return_value.all.return_value = []

    app = create_public_v2_app(engine_mock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v2/entities/search?q=NonExistent")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []


@pytest.mark.asyncio
async def test_entity_timeline_endpoint() -> None:
    engine_mock = MagicMock()
    conn_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value = conn_mock

    entity_id = UUID("11111111-1111-1111-1111-111111111111")
    item_id = uuid4()
    art_id = uuid4()

    # Sequence of queries: entity_info, timeline_rows, art_rows
    entity_result = MagicMock()
    entity_result.mappings.return_value.one_or_none.return_value = {
        "id": entity_id,
        "entity_type": "CLUB",
        "canonical_name": "Arsenal",
        "slug": "arsenal",
        "aliases": ["Gunners"],
        "mention_count_24h": 3,
        "last_seen_at": datetime.now(UTC),
    }

    timeline_result = MagicMock()
    timeline_result.mappings.return_value.all.return_value = [
        {
            "id": item_id,
            "entity_id": entity_id,
            "window_start": datetime(2026, 8, 20, 0, 0, tzinfo=UTC),
            "window_end": datetime(2026, 8, 20, 3, 0, tzinfo=UTC),
            "title": "Arsenal Victory",
            "summary": "Arsenal won 3-2 against opponent.",
            "article_count": 1,
            "key_entities_50": ["Arsenal"],
            "key_entities_80": ["Arsenal"],
        }
    ]

    articles_result = MagicMock()
    articles_result.mappings.return_value.all.return_value = [
        {
            "timeline_item_id": item_id,
            "id": art_id,
            "title": "Match Report",
            "url": "https://example.com/art",
            "canonical_url": "https://example.com/art",
            "source_name": "BBC Sport",
            "domain_name": "bbc.com",
            "description": "Report",
            "image_url": "https://example.com/img.png",
            "published_at": datetime(2026, 8, 20, 1, 0, tzinfo=UTC),
        }
    ]

    conn_mock.execute.side_effect = [entity_result, timeline_result, articles_result]

    app = create_public_v2_app(engine_mock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v2/entities/{entity_id}/timeline")

    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == str(entity_id)
    assert data["entity"]["canonical_name"] == "Arsenal"
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Arsenal Victory"
    assert len(data["items"][0]["source_articles"]) == 1
    assert data["items"][0]["source_articles"][0]["source_name"] == "BBC Sport"

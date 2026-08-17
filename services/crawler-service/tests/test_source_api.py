from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from footballpulse_crawler_service.api.app import create_app
from footballpulse_crawler_service.application.source_service import (
    CrawlBatchService,
    SourceService,
)
from footballpulse_crawler_service.domain.crawl_batch import CrawlBatch
from footballpulse_crawler_service.domain.errors import SourceConflictError
from footballpulse_crawler_service.domain.source import Source

NOW = datetime(2026, 8, 1, tzinfo=UTC)
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000101")
ADMIN_HEADERS = {"Authorization": "Bearer admin-test-token"}
INTERNAL_HEADERS = {"Authorization": "Bearer internal-test-token"}


class MemorySourceRepository:
    def __init__(self) -> None:
        self.sources: dict[UUID, Source] = {}

    def add(self, source: Source) -> Source:
        if any(item.rss_url == source.rss_url for item in self.sources.values()):
            raise SourceConflictError("source RSS URL already exists")
        self.sources[source.id] = source
        return source

    def get(self, source_id: UUID) -> Source | None:
        return self.sources.get(source_id)

    def list_sources(self, *, limit: int, offset: int) -> list[Source]:
        return list(self.sources.values())[offset : offset + limit]

    def save(self, source: Source, *, expected_version: int) -> Source:
        if self.sources[source.id].version != expected_version:
            raise SourceConflictError("source version changed before update")
        self.sources[source.id] = source
        return source

    def due(self, *, at: datetime, limit: int) -> list[Source]:
        return [source for source in self.sources.values() if source.is_due(at)][:limit]


class MemoryBatchRepository:
    def __init__(self) -> None:
        self.batches: dict[UUID, CrawlBatch] = {}
        self.keys: dict[str, UUID] = {}

    def open(self, batch: CrawlBatch) -> CrawlBatch:
        existing_id = self.keys.get(batch.idempotency_key)
        if existing_id is not None:
            return self.batches[existing_id]
        self.batches[batch.id] = batch
        self.keys[batch.idempotency_key] = batch.id
        return batch

    def get(self, batch_id: UUID) -> CrawlBatch | None:
        return self.batches.get(batch_id)

    def save(self, batch: CrawlBatch) -> CrawlBatch:
        self.batches[batch.id] = batch
        return batch


@pytest.mark.anyio
async def test_admin_source_flow_and_internal_due_query() -> None:
    sources = MemorySourceRepository()
    source_service = SourceService(sources, clock=lambda: NOW, id_factory=lambda: SOURCE_ID)
    batch_service = CrawlBatchService(
        sources,
        MemoryBatchRepository(),
        clock=lambda: NOW,
    )
    app = create_app(
            source_service=source_service,
            batch_service=batch_service,
            admin_token="admin-test-token",
            internal_token="internal-test-token",
    )
    payload = {
        "name": "BBC Sport",
        "rss_url": "https://www.bbc.com/sport/football/rss.xml",
        "allowed_domains": ["bbc.com"],
        "source_type": "RSS",
        "reliability_tier": 1,
        "crawl_interval_minutes": 360,
        "max_concurrency": 2,
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://crawler.test",
    ) as client:
        unauthorized = await client.post("/admin/v1/sources", json=payload)
        assert unauthorized.status_code == 401
        assert unauthorized.json()["error"]["code"] == "UNAUTHORIZED"
        created = await client.post("/admin/v1/sources", headers=ADMIN_HEADERS, json=payload)
        assert created.status_code == 201
        assert created.json()["id"] == str(SOURCE_ID)

        listed = await client.get("/admin/v1/sources", headers=ADMIN_HEADERS)
        assert listed.status_code == 200
        assert listed.json()["items"][0]["name"] == "BBC Sport"

        batch_payload = {
            "source_id": str(SOURCE_ID),
            "idempotency_key": "bbc:2026-08-01T00:00:00Z",
            "window_started_at": "2026-08-01T00:00:00Z",
        }
        first_batch = await client.post(
            "/internal/v1/crawl-batches", headers=INTERNAL_HEADERS, json=batch_payload
        )
        replayed_batch = await client.post(
            "/internal/v1/crawl-batches", headers=INTERNAL_HEADERS, json=batch_payload
        )
        assert first_batch.status_code == 201
        assert replayed_batch.json()["id"] == first_batch.json()["id"]

        manual_batch = await client.post(
            f"/admin/v1/sources/{SOURCE_ID}/crawl",
            headers=ADMIN_HEADERS,
            json={"idempotency_key": "manual:bbc:2026-08-01T00:00:00Z"},
        )
        assert manual_batch.status_code == 201

        disabled = await client.post(
            f"/admin/v1/sources/{SOURCE_ID}/toggle",
            headers=ADMIN_HEADERS,
            json={"enabled": False, "expected_version": 1},
        )
        assert disabled.status_code == 200
        assert disabled.json()["version"] == 2

        due = await client.get(
            "/internal/v1/sources/due?at=2026-08-01T00:00:00Z",
            headers=INTERNAL_HEADERS,
        )
        assert due.status_code == 200
        assert due.json() == {"items": []}

        stale = await client.post(
            f"/admin/v1/sources/{SOURCE_ID}/toggle",
            headers=ADMIN_HEADERS,
            json={"enabled": True, "expected_version": 1},
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "SOURCE_CONFLICT"


def test_openapi_exposes_admin_and_internal_bearer_boundaries() -> None:
    sources = MemorySourceRepository()
    app = create_app(
        source_service=SourceService(sources, clock=lambda: NOW),
        batch_service=CrawlBatchService(sources, MemoryBatchRepository(), clock=lambda: NOW),
        admin_token="admin-test-token",
        internal_token="internal-test-token",
    )
    schema = app.openapi()

    assert "/admin/v1/sources" in schema["paths"]
    assert "/internal/v1/sources/due" in schema["paths"]
    assert "HTTPBearer" in schema["components"]["securitySchemes"]

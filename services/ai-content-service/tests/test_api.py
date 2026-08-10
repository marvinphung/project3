from __future__ import annotations

import httpx
import pytest
from footballpulse_ai_content_service.api.app import create_app


@pytest.mark.asyncio
async def test_enrichment_batch_contract_requires_internal_token() -> None:
    transport = httpx.ASGITransport(app=create_app(internal_token="ai-internal"))
    payload = {"collection_batch_ids": ["crawl-1"], "window_started_at": "2026-08-10T06:00:00Z"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.post("/internal/v1/enrichment-batches", json=payload)
        accepted = await client.post(
            "/internal/v1/enrichment-batches",
            headers={"Authorization": "Bearer ai-internal"},
            json=payload,
        )

    assert unauthorized.status_code == 401
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "PREPARING"
    assert accepted.json()["collection_batch_ids"] == ["crawl-1"]

    batch_id = accepted.json()["id"]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status = await client.get(
            f"/internal/v1/enrichment-batches/{batch_id}",
            headers={"Authorization": "Bearer ai-internal"},
        )
    assert status.status_code == 200
    assert status.json()["id"] == batch_id

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        started = await client.post(
            f"/internal/v1/enrichment-batches/{batch_id}/start",
            headers={"Authorization": "Bearer ai-internal"},
        )
    assert started.status_code == 200
    assert started.json()["status"] == "RUNNING"

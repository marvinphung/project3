from __future__ import annotations

import hashlib

import httpx
import pytest
from footballpulse_ai_content_service.server import create_runtime_app


@pytest.mark.asyncio
async def test_runtime_app_uses_configured_deterministic_provider() -> None:
    app = create_runtime_app(
        {
            "FOOTBALLPULSE_ENV": "demo",
            "FOOTBALLPULSE_AI_INTERNAL_TOKEN": "test-token",
            "FOOTBALLPULSE_AI_PROVIDER": "mock",
            "FOOTBALLPULSE_AI_ALLOW_MOCK": "true",
            "FOOTBALLPULSE_AI_DETERMINISTIC_OFFLINE": "true",
        }
    )
    content = "Arsenal submitted an offer for a player."
    article = {
        "contract_version": "article-enrichment.v1",
        "article_version_id": "00000000-0000-4000-8000-000000000101",
        "input_hash": hashlib.sha256(content.encode()).hexdigest(),
        "title": "Arsenal submit offer",
        "cleaned_content": content,
        "published_at": "2026-08-17T06:00:00Z",
        "source_id": "00000000-0000-4000-8000-000000000201",
        "source_reliability_tier": 1,
        "canonical_entities": [],
        "unresolved_mentions": [],
    }
    headers = {"Authorization": "Bearer test-token"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/internal/v1/enrichment-batches",
            headers=headers,
            json={
                "collection_batch_ids": ["crawl-1"],
                "window_started_at": "2026-08-17T06:00:00Z",
            },
        )
        started = await client.post(
            f"/internal/v1/enrichment-batches/{created.json()['id']}/start",
            headers=headers,
            json={"articles": [article]},
        )

    assert started.status_code == 200
    payload = started.json()
    assert payload["status"] == "COMPLETED"
    assert payload["results"][0]["result"]["model_version"] == "offline-deterministic-v1"


def test_runtime_app_requires_internal_token() -> None:
    with pytest.raises(RuntimeError, match="AI_INTERNAL_TOKEN"):
        create_runtime_app(
            {
                "FOOTBALLPULSE_ENV": "demo",
                "FOOTBALLPULSE_AI_PROVIDER": "mock",
                "FOOTBALLPULSE_AI_ALLOW_MOCK": "true",
                "FOOTBALLPULSE_AI_DETERMINISTIC_OFFLINE": "true",
            }
        )

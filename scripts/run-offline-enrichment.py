#!/usr/bin/env python3
"""Run one complete enrichment lifecycle without Docker, Kaggle or a model."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from footballpulse_ai_content_service.api.app import create_app
from footballpulse_ai_content_service.providers.offline import DeterministicOfflineProvider
from footballpulse_runtime_config import configure_logging, log_event

LOGGER = logging.getLogger("footballpulse.offline_enrichment")


def article(article_id: UUID, source_id: UUID, content: str) -> dict[str, object]:
    return {
        "contract_version": "article-enrichment.v1",
        "article_version_id": str(article_id),
        "input_hash": hashlib.sha256(content.encode()).hexdigest(),
        "title": "Offline FootballPulse article",
        "cleaned_content": content,
        "published_at": datetime.now(UTC).isoformat(),
        "source_id": str(source_id),
        "source_reliability_tier": 1,
        "canonical_entities": [],
        "unresolved_mentions": [],
    }


async def main() -> None:
    configure_logging(service="offline-enrichment", level="INFO", force=True)
    log_event(LOGGER, "offline_enrichment_started")
    token = "offline-token"
    transport = httpx.ASGITransport(
        app=create_app(internal_token=token, provider=DeterministicOfflineProvider())
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://offline") as client:
        headers = {"Authorization": f"Bearer {token}"}
        created = await client.post(
            "/internal/v1/enrichment-batches",
            headers=headers,
            json={
                "collection_batch_ids": ["offline-collection-1"],
                "window_started_at": "2026-08-10T00:00:00Z",
            },
        )
        created.raise_for_status()
        batch_id = created.json()["id"]
        log_event(LOGGER, "offline_batch_created", batch_id=batch_id)
        content = "Real Madrid are negotiating a contract extension with Vinicius Junior."
        started = await client.post(
            f"/internal/v1/enrichment-batches/{batch_id}/start",
            headers=headers,
            json={
                "articles": [
                    article(
                        UUID("10000000-0000-0000-0000-000000000001"),
                        UUID("20000000-0000-0000-0000-000000000001"),
                        content,
                    )
                ]
            },
        )
        started.raise_for_status()
        log_event(
            LOGGER,
            "offline_enrichment_completed",
            batch_id=batch_id,
            status=started.json()["status"],
            success_count=started.json()["success_count"],
            error_count=started.json()["error_count"],
        )
        print(json.dumps(started.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

"""Manual, audited AI enrichment reprocess workflow."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("footballpulse.airflow.ai_reprocess")


def _request(ai_url: str, path: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    token = os.environ.get("FOOTBALLPULSE_AI_INTERNAL_TOKEN", "")
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(
        f"{ai_url.rstrip('/')}{path}",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - configured local URL
        return json.loads(response.read())


def reprocess_batch(
    *, ai_url: str, collection_batch_ids: list[str], window_started_at: datetime
) -> dict[str, object]:
    LOGGER.info("ai_reprocess_started collection_batch_count=%s", len(collection_batch_ids))
    created = _request(
        ai_url,
        "/internal/v1/enrichment-batches",
        method="POST",
        payload={
            "collection_batch_ids": collection_batch_ids,
            "window_started_at": window_started_at.isoformat(),
        },
    )
    batch_id = created["id"]
    LOGGER.info("ai_reprocess_created batch_id=%s", batch_id)
    _request(ai_url, f"/internal/v1/enrichment-batches/{batch_id}/start", method="POST")
    for attempt in range(12):
        status = _request(ai_url, f"/internal/v1/enrichment-batches/{batch_id}")
        LOGGER.info(
            "ai_reprocess_status_polled batch_id=%s attempt=%s status=%s",
            batch_id,
            attempt + 1,
            status.get("status"),
        )
        if status.get("status") in {"COMPLETED", "PARTIAL", "FAILED_RETRYABLE", "FAILED_TERMINAL"}:
            LOGGER.info(
                "ai_reprocess_completed batch_id=%s status=%s",
                batch_id,
                status.get("status"),
            )
            return status
        if attempt < 11:
            time.sleep(30)
    raise TimeoutError(f"AI enrichment reprocess {batch_id} timed out")

"""Manual, audited AI enrichment reprocess workflow."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from urllib.request import Request, urlopen


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
    _request(ai_url, f"/internal/v1/enrichment-batches/{batch_id}/start", method="POST")
    for attempt in range(12):
        status = _request(ai_url, f"/internal/v1/enrichment-batches/{batch_id}")
        if status.get("status") in {"COMPLETED", "PARTIAL", "FAILED_RETRYABLE", "FAILED_TERMINAL"}:
            return status
        if attempt < 11:
            time.sleep(30)
    raise TimeoutError(f"AI enrichment reprocess {batch_id} timed out")

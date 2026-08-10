"""Orchestrate enrichment after collection without processing articles in Airflow."""

from __future__ import annotations

import json
import os
from datetime import datetime
from urllib.request import Request, urlopen


def trigger_enrichment_batch(
    *, ai_url: str, collection_batch_ids: list[str], window_started_at: datetime
) -> str:
    """Ask the AI service to process a collection batch and return its batch ID."""
    token = os.environ.get("FOOTBALLPULSE_AI_INTERNAL_TOKEN", "")
    payload = json.dumps(
        {
            "collection_batch_ids": collection_batch_ids,
            "window_started_at": window_started_at.isoformat(),
        }
    ).encode()
    request = Request(
        f"{ai_url.rstrip('/')}/internal/v1/enrichment-batches",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - configured local URL
        return json.loads(response.read())["id"]


try:
    import pendulum
    from airflow.decorators import dag, task

    @dag(
        dag_id="footballpulse_ai_enrichment",
        schedule="30 */6 * * *",
        start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
        catchup=False,
        max_active_runs=1,
        tags=["footballpulse", "ai", "enrichment"],
    )
    def footballpulse_ai_enrichment():
        @task
        def load_collection_batches() -> list[str]:
            value = os.environ.get("FOOTBALLPULSE_COLLECTION_BATCH_IDS", "")
            return [item.strip() for item in value.split(",") if item.strip()]

        @task
        def submit_enrichment(batch_ids: list[str], **context) -> str:
            return trigger_enrichment_batch(
                ai_url=os.environ.get("FOOTBALLPULSE_AI_ENRICHMENT_URL", "http://ai-content:8000"),
                collection_batch_ids=batch_ids,
                window_started_at=context["data_interval_start"].in_timezone("Asia/Ho_Chi_Minh"),
            )

        submit_enrichment(load_collection_batches())

    footballpulse_ai_enrichment_dag = footballpulse_ai_enrichment()
except ImportError:
    footballpulse_ai_enrichment_dag = None

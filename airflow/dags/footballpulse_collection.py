"""Run the six-hour FootballPulse collection batch.

Airflow owns orchestration only: the crawler service remains responsible for
source selection, RSS/HTML fetching, normalization, and idempotent batches.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from urllib.request import Request, urlopen


def batch_idempotency_key(source_id: str, window_started_at: datetime) -> str:
    return f"{source_id}:{window_started_at.isoformat()}"


def trigger_crawler_batches(
    *, crawler_url: str, source_ids: list[str], window_started_at: datetime
) -> list[str]:
    """Open one idempotent batch per source and return created batch IDs."""
    token = os.environ.get("FOOTBALLPULSE_CRAWLER_ADMIN_TOKEN", "")
    created: list[str] = []
    for source_id in source_ids:
        payload = json.dumps(
            {"idempotency_key": batch_idempotency_key(source_id, window_started_at)}
        ).encode()
        request = Request(
            f"{crawler_url.rstrip('/')}/admin/v1/sources/{source_id}/crawl",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=30) as response:  # noqa: S310 - configured local URL
            created.append(json.loads(response.read())["id"])
    return created


try:
    import pendulum
    from airflow.decorators import dag, task

    @dag(
        dag_id="footballpulse_collection",
        schedule="0 */6 * * *",
        start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
        catchup=False,
        max_active_runs=1,
        tags=["footballpulse", "collection"],
    )
    def footballpulse_collection():
        @task
        def load_due_source_ids() -> list[str]:
            value = os.environ.get("FOOTBALLPULSE_DUE_SOURCE_IDS", "")
            return [item.strip() for item in value.split(",") if item.strip()]

        @task
        def open_crawl_batches(source_ids: list[str], **context) -> list[str]:
            return trigger_crawler_batches(
                crawler_url=os.environ.get("FOOTBALLPULSE_CRAWLER_URL", "http://crawler:8000"),
                source_ids=source_ids,
                window_started_at=context["data_interval_start"].in_timezone("Asia/Ho_Chi_Minh"),
            )

        open_crawl_batches(load_due_source_ids())

    footballpulse_collection_dag = footballpulse_collection()
except ImportError:  # Airflow is optional in the local Python workspace.
    footballpulse_collection_dag = None

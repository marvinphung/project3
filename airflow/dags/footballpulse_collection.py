"""Run the six-hour FootballPulse collection batch.

Airflow owns orchestration only: the crawler service remains responsible for
source selection, RSS/HTML fetching, normalization, and idempotent batches.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("footballpulse.airflow.collection")


def batch_idempotency_key(source_id: str, window_started_at: datetime) -> str:
    return f"{source_id}:{window_started_at.isoformat()}"


def trigger_crawler_batches(
    *, crawler_url: str, source_ids: list[str], window_started_at: datetime
) -> list[str]:
    """Open one idempotent batch per source and return created batch IDs."""
    token = os.environ.get("FOOTBALLPULSE_CRAWLER_ADMIN_TOKEN", "")
    created: list[str] = []
    LOGGER.info("crawl_batch_submission_started source_count=%s", len(source_ids))
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
        LOGGER.info("crawl_batch_submitted source_id=%s batch_id=%s", source_id, created[-1])
    LOGGER.info("crawl_batch_submission_completed batch_count=%s", len(created))
    return created


def fetch_due_source_ids(*, crawler_url: str, at: datetime) -> list[str]:
    """Read due enabled sources from the crawler service."""
    token = os.environ.get("FOOTBALLPULSE_CRAWLER_INTERNAL_TOKEN", "")
    query = urlencode({"at": at.isoformat(), "limit": 200})
    request = Request(
        f"{crawler_url.rstrip('/')}/internal/v1/sources/due?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - configured local URL
        source_ids = [item["id"] for item in json.loads(response.read())["items"]]
    LOGGER.info("due_sources_loaded source_count=%s", len(source_ids))
    return source_ids


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
        def load_due_source_ids(**context) -> list[str]:
            return fetch_due_source_ids(
                crawler_url=os.environ.get("FOOTBALLPULSE_CRAWLER_URL", "http://crawler:8000"),
                at=context["data_interval_start"].in_timezone("Asia/Ho_Chi_Minh"),
            )

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

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from footballpulse_runtime_config import bind_log_context, configure_logging
from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from footballpulse_ai_content_service.application.enrichment_worker import (
    EnrichmentWorker,
    EnrichmentWorkerReport,
)
from footballpulse_ai_content_service.batch.artifacts import BatchArtifactStore
from footballpulse_ai_content_service.batch.coordinator import KaggleBatchCoordinator
from footballpulse_ai_content_service.batch.domain import AiBatchJob, AiBatchStatus
from footballpulse_ai_content_service.batch.kaggle_cli import KaggleCli
from footballpulse_ai_content_service.batch.metadata import KaggleMetadataBuilder
from footballpulse_ai_content_service.persistence.mongo_batch_repository import (
    MongoBatchJobRepository,
    MongoEnrichmentResultSink,
)
from footballpulse_ai_content_service.persistence.mongo_enrichment_queue import (
    MongoEnrichmentQueue,
)
from footballpulse_ai_content_service.persistence.postgres_source_reliability import (
    PostgresSourceReliabilityRepository,
)
from footballpulse_ai_content_service.providers.factory import build_provider_from_environment
from footballpulse_ai_content_service.providers.service import ProviderEnrichmentService

LOGGER = logging.getLogger("footballpulse.ai.enrichment_worker")


class RuntimeWorker(Protocol):
    def run_once(self, *, limit: int = 10) -> EnrichmentWorkerReport: ...


class KaggleRuntimeWorker:
    def __init__(
        self,
        *,
        queue: MongoEnrichmentQueue,
        jobs: MongoBatchJobRepository,
        sink: MongoEnrichmentResultSink,
    ) -> None:
        self._queue = queue
        self._jobs = jobs
        self._sink = sink

    def run_once(self, *, limit: int = 10) -> EnrichmentWorkerReport:
        now = datetime.now(UTC)
        inputs = self._queue.claim_pending(limit=limit)
        if not inputs:
            _log("enrichment_batch_empty", limit=limit)
            return EnrichmentWorkerReport(0, 0, 0)
        batch_id = uuid4()
        root = Path(os.getenv("FOOTBALLPULSE_AI_BATCH_ROOT", ".footballpulse/ai-batches"))
        model_version = os.environ["FOOTBALLPULSE_KAGGLE_MODEL_SOURCE"]
        _log("enrichment_batch_claimed", batch_id=batch_id, article_count=len(inputs))
        artifacts = BatchArtifactStore(root).build(
            batch_id=batch_id,
            inputs=list(inputs),
            created_at=now,
            model_version=model_version,
            prompt_version="article-enrichment-v1",
        )
        _log(
            "batch_artifacts_created",
            batch_id=batch_id,
            article_count=len(inputs),
            artifact_directory=str(artifacts.directory),
        )
        self._jobs.create(
            AiBatchJob(
                batch_id=batch_id,
                status=AiBatchStatus.PREPARING,
                created_at=now,
                updated_at=now,
                article_count=len(inputs),
                artifact_directory=str(artifacts.directory),
            )
        )
        kernel_path = root / "kernels" / str(batch_id)
        KaggleMetadataBuilder().prepare_kernel(
            target=kernel_path,
            runner_source=Path("/workspace/kaggle/ai-enrichment/runner.py"),
            kernel_slug=os.environ["FOOTBALLPULSE_KAGGLE_KERNEL_SLUG"],
            dataset_slug=os.environ["FOOTBALLPULSE_KAGGLE_DATASET_SLUG"],
            model_source=model_version,
        )
        with bind_log_context(correlation_id=str(batch_id), batch_id=str(batch_id)):
            status = KaggleBatchCoordinator(
            jobs=self._jobs,
            cli=KaggleCli(),
            sink=self._sink,
            kernel_slug=os.environ["FOOTBALLPULSE_KAGGLE_KERNEL_SLUG"],
            dataset_slug=os.environ["FOOTBALLPULSE_KAGGLE_DATASET_SLUG"],
            worker_id=f"docker-{batch_id}",
            clock=lambda: datetime.now(UTC),
            ).run(
                batch_id=batch_id,
                artifacts=artifacts,
                kernel_path=kernel_path,
                accelerator="gpu",
            )
        terminal = status.value if status is not None else "LEASE_UNAVAILABLE"
        succeeded, failed = self._queue.complete_external(
            inputs,
            terminal_status=terminal,
            processed_at=datetime.now(UTC),
        )
        return EnrichmentWorkerReport(len(inputs), succeeded, failed)


def _database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
        password=os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only"),
        host=os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")),
        database=os.getenv("FOOTBALLPULSE_POSTGRES_DB", "footballpulse"),
    )


def _log(event: str, **fields: object) -> None:
    LOGGER.info(event, extra={"event_name": event, "event_fields": fields})


def create_worker() -> tuple[RuntimeWorker, MongoClient[dict[str, object]]]:
    mongo_client: MongoClient[dict[str, object]] = MongoClient(
        os.getenv(
            "FOOTBALLPULSE_MONGODB_URL",
            "mongodb://127.0.0.1:27017/?replicaSet=rs0",
        )
    )
    database = mongo_client[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse")]
    source_repository = PostgresSourceReliabilityRepository(
        create_engine(_database_url(), pool_pre_ping=True)
    )
    queue = MongoEnrichmentQueue(
        database,
        source_reliability=source_repository.get,
        clock=lambda: datetime.now(UTC),
    )
    queue.ensure_indexes()
    sink = MongoEnrichmentResultSink(database)
    sink.ensure_indexes()
    if os.getenv("FOOTBALLPULSE_AI_PROVIDER", "kaggle").casefold() == "kaggle":
        jobs = MongoBatchJobRepository(database)
        jobs.ensure_indexes()
        return KaggleRuntimeWorker(queue=queue, jobs=jobs, sink=sink), mongo_client
    service = ProviderEnrichmentService(
        provider=build_provider_from_environment(os.environ),
        sink=sink,
        clock=lambda: datetime.now(UTC),
    )
    return (
        EnrichmentWorker(
            queue=queue,
            service=service,
            clock=lambda: datetime.now(UTC),
        ),
        mongo_client,
    )


def main() -> None:
    configure_logging(
        service="ai-enrichment-worker",
        level=os.getenv("FOOTBALLPULSE_LOG_LEVEL", "INFO").upper(),
        force=True,
    )
    limit = int(os.getenv("FOOTBALLPULSE_ENRICHMENT_BATCH_SIZE", "10"))
    poll_seconds = float(os.getenv("FOOTBALLPULSE_ENRICHMENT_POLL_SECONDS", "30"))
    run_once = os.getenv("FOOTBALLPULSE_ENRICHMENT_RUN_ONCE", "false").casefold() == "true"
    worker, mongo_client = create_worker()
    _log("enrichment_worker_started", batch_size=limit, run_once=run_once)
    try:
        while True:
            report = worker.run_once(limit=limit)
            _log(
                "enrichment_batch_completed",
                claimed=report.claimed,
                succeeded=report.succeeded,
                failed=report.failed,
            )
            if run_once:
                break
            time.sleep(poll_seconds)
    finally:
        mongo_client.close()
        _log("enrichment_worker_stopped")


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from footballpulse_ai_content_service.batch.coordinator import GroundedEnrichment
from footballpulse_ai_content_service.batch.domain import AiBatchJob, AiBatchStatus
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentOutput
from footballpulse_ai_content_service.persistence.mongo_batch_repository import (
    MongoBatchJobRepository,
    MongoEnrichmentResultSink,
)
from footballpulse_ai_content_service.validation.grounding import (
    GroundingResult,
    GroundingStatus,
)
from pymongo import MongoClient
from pymongo.database import Database

BATCH_ID = UUID("00000000-0000-4000-8000-000000000901")
ARTICLE_ID = UUID("00000000-0000-4000-8000-000000000101")
NOW = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)


@pytest.fixture
def mongo_database() -> Iterator[Database[dict[str, object]]]:
    mongo_url = os.getenv(
        "FOOTBALLPULSE_MONGODB_URL",
        "mongodb://127.0.0.1:27017/?directConnection=true",
    )
    database_name = f"footballpulse_ai_batch_test_{uuid4().hex}"
    with MongoClient[dict[str, object]](mongo_url) as client:
        database = client[database_name]
        yield database
        client.drop_database(database_name)


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_MONGO_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_MONGO_INTEGRATION=1 with MongoDB running",
)
def test_job_transitions_single_flight_and_idempotent_enrichment(
    mongo_database: Database[dict[str, object]],
) -> None:
    jobs = MongoBatchJobRepository(mongo_database)
    jobs.ensure_indexes()
    jobs.create(
        AiBatchJob(
            batch_id=BATCH_ID,
            status=AiBatchStatus.PREPARING,
            created_at=NOW,
            updated_at=NOW,
            article_count=1,
            artifact_directory=f".footballpulse/ai-batches/{BATCH_ID}",
        )
    )
    assert jobs.get_status(BATCH_ID) is AiBatchStatus.PREPARING
    resumable = jobs.find_resumable()
    assert resumable is not None
    assert resumable.batch_id == BATCH_ID
    assert resumable.created_at.tzinfo is not None

    assert jobs.acquire_lease(owner="worker-1", now=NOW, lease_seconds=60) is True
    assert jobs.acquire_lease(owner="worker-2", now=NOW, lease_seconds=60) is False
    assert (
        jobs.acquire_lease(owner="worker-2", now=NOW + timedelta(seconds=61), lease_seconds=60)
        is True
    )

    jobs.transition(
        BATCH_ID,
        expected=AiBatchStatus.PREPARING,
        target=AiBatchStatus.DATASET_UPLOADED,
        now=NOW,
    )
    assert mongo_database.ai_batch_jobs.find_one({"_id": str(BATCH_ID)})["status"] == (
        "DATASET_UPLOADED"
    )

    output = ArticleEnrichmentOutput.model_validate(
        {
            "contract_version": "article-enrichment.v1",
            "article_version_id": str(ARTICLE_ID),
            "input_hash": "a" * 64,
            "event_type": "TRANSFER",
            "summary_en": "Arsenal submitted an offer.",
            "claims": [],
            "model_version": "model-v1",
            "prompt_version": "prompt-v1",
        }
    )
    sink = MongoEnrichmentResultSink(mongo_database)
    sink.ensure_indexes()
    grounded = GroundedEnrichment(
        output=output,
        validation=GroundingResult(
            status=GroundingStatus.NEEDS_CONTENT_REVIEW,
            valid_claims=(),
            rejected_claims=(),
            summary_en=None,
            top_level_errors=("SUMMARY_NOT_GROUNDED",),
        ),
        validated_at=NOW,
    )
    sink.persist((grounded,))
    sink.persist((grounded,))
    assert mongo_database.article_enrichments.count_documents({}) == 1

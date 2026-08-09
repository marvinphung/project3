from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from footballpulse_ai_content_service.batch.artifacts import BatchArtifacts
from footballpulse_ai_content_service.batch.coordinator import KaggleBatchCoordinator
from footballpulse_ai_content_service.batch.domain import (
    AiBatchManifest,
    AiBatchManifestRecord,
    AiBatchStatus,
)
from footballpulse_ai_content_service.batch.kaggle_cli import KaggleCliError, KaggleKernelState

BATCH_ID = UUID("00000000-0000-4000-8000-000000000901")
ARTICLE_ID = UUID("00000000-0000-4000-8000-000000000101")
INPUT_HASH = "a" * 64
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000201")


class MemoryJobs:
    def __init__(self, *, acquire: bool = True) -> None:
        self.acquire = acquire
        self.status = AiBatchStatus.PREPARING
        self.transitions: list[AiBatchStatus] = []
        self.released = False
        self.acquire_calls = 0

    def acquire_lease(self, *, owner: str, now: datetime, lease_seconds: int) -> bool:
        self.acquire_calls += 1
        return self.acquire

    def transition(
        self,
        batch_id: UUID,
        *,
        expected: AiBatchStatus,
        target: AiBatchStatus,
        now: datetime,
        success_count: int | None = None,
        error_count: int | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        assert batch_id == BATCH_ID
        assert self.status is expected
        self.status = target
        self.transitions.append(target)

    def release_lease(self, *, owner: str) -> None:
        self.released = True


class FakeCli:
    def __init__(self, statuses: list[KaggleKernelState]) -> None:
        self.statuses = statuses
        self.calls: list[str] = []
        self.failure: Exception | None = None

    def upload_dataset(self, dataset_path: Path, *, batch_id: str) -> None:
        self.calls.append("upload")
        if self.failure is not None:
            raise self.failure

    def submit_kernel(self, kernel_path: Path, *, accelerator: str) -> None:
        self.calls.append("submit")

    def kernel_status(self, kernel_slug: str) -> KaggleKernelState:
        self.calls.append("status")
        return self.statuses.pop(0)

    def download_output(self, kernel_slug: str, output_path: Path) -> None:
        self.calls.append("download")


class RecordingSink:
    def __init__(self) -> None:
        self.outputs: list[Any] = []

    def persist(self, outputs: tuple[Any, ...]) -> None:
        self.outputs.extend(outputs)


def prepare_artifacts(tmp_path: Path, records: list[dict[str, object]]) -> BatchArtifacts:
    directory = tmp_path / str(BATCH_ID)
    directory.mkdir()
    manifest = AiBatchManifest(
        contract_version="ai-batch.v1",
        batch_id=BATCH_ID,
        status=AiBatchStatus.PREPARING,
        created_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        model_version="model-v1",
        prompt_version="prompt-v1",
        article_count=1,
        articles_sha256="f" * 64,
        records=(AiBatchManifestRecord(article_version_id=ARTICLE_ID, input_hash=INPUT_HASH),),
    )
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    articles_path = directory / "articles.jsonl"
    articles_path.write_text(
        json.dumps(
            {
                "contract_version": "article-enrichment.v1",
                "article_version_id": str(ARTICLE_ID),
                "input_hash": INPUT_HASH,
                "title": "Arsenal submitted an offer",
                "cleaned_content": "Arsenal submitted an offer.",
                "published_at": "2026-08-10T08:00:00Z",
                "source_id": str(SOURCE_ID),
                "source_reliability_tier": 1,
                "canonical_entities": [],
                "unresolved_mentions": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    results_path = directory / "results.jsonl"
    results_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    report_path = directory / "job-report.json"
    report_path.write_text(
        json.dumps(
            {
                "contract_version": "ai-job-report.v1",
                "batch_id": str(BATCH_ID),
                "articles_sha256": "f" * 64,
                "model_version": "model-v1",
                "prompt_version": "prompt-v1",
                "success_count": len(
                    [record for record in records if record["status"] == "SUCCESS"]
                ),
                "error_count": len([record for record in records if record["status"] == "ERROR"]),
                "started_at": "2026-08-10T08:00:00Z",
                "finished_at": "2026-08-10T08:01:00Z",
            }
        ),
        encoding="utf-8",
    )
    return BatchArtifacts(
        directory=directory,
        manifest_path=manifest_path,
        articles_path=articles_path,
        results_path=results_path,
        report_path=report_path,
    )


def success() -> dict[str, object]:
    return {
        "article_version_id": str(ARTICLE_ID),
        "status": "SUCCESS",
        "result": {
            "contract_version": "article-enrichment.v1",
            "article_version_id": str(ARTICLE_ID),
            "input_hash": INPUT_HASH,
            "event_type": "TRANSFER",
            "summary_en": "Arsenal submitted an offer.",
            "claims": [],
            "model_version": "model-v1",
            "prompt_version": "prompt-v1",
        },
    }


def coordinator(jobs: MemoryJobs, cli: FakeCli, sink: RecordingSink) -> KaggleBatchCoordinator:
    return KaggleBatchCoordinator(
        jobs=jobs,
        cli=cli,
        sink=sink,
        kernel_slug="owner/footballpulse-ai",
        dataset_slug="owner/footballpulse-batches",
        worker_id="worker-1",
        clock=lambda: datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        monotonic_values=iter([0.0, 30.0, 60.0]).__next__,
        sleep=lambda _: None,
        poll_interval_seconds=30,
        poll_budget_seconds=90,
    )


def test_coordinator_runs_lifecycle_and_persists_success(tmp_path: Path) -> None:
    jobs = MemoryJobs()
    cli = FakeCli([KaggleKernelState.RUNNING, KaggleKernelState.COMPLETE])
    sink = RecordingSink()

    result = coordinator(jobs, cli, sink).run(
        batch_id=BATCH_ID,
        artifacts=prepare_artifacts(tmp_path, [success()]),
        kernel_path=tmp_path / "kernel",
        accelerator="NvidiaTeslaP100",
    )

    assert result is AiBatchStatus.COMPLETED
    assert jobs.transitions == [
        AiBatchStatus.DATASET_UPLOADED,
        AiBatchStatus.KERNEL_SUBMITTED,
        AiBatchStatus.RUNNING,
        AiBatchStatus.DOWNLOADING,
        AiBatchStatus.IMPORTING,
        AiBatchStatus.COMPLETED,
    ]
    assert cli.calls == ["upload", "submit", "status", "status", "download"]
    assert len(sink.outputs) == 1
    assert jobs.released is True
    assert jobs.acquire_calls == 3
    dataset_metadata = json.loads(
        (tmp_path / str(BATCH_ID) / "dataset-metadata.json").read_text(encoding="utf-8")
    )
    assert dataset_metadata["isPrivate"] is True


def test_coordinator_marks_cli_failure_retryable_and_releases_lease(tmp_path: Path) -> None:
    jobs = MemoryJobs()
    cli = FakeCli([])
    cli.failure = KaggleCliError("network unavailable")

    result = coordinator(jobs, cli, RecordingSink()).run(
        batch_id=BATCH_ID,
        artifacts=prepare_artifacts(tmp_path, [success()]),
        kernel_path=tmp_path / "kernel",
        accelerator="NvidiaTeslaP100",
    )

    assert result is AiBatchStatus.FAILED_RETRYABLE
    assert jobs.status is AiBatchStatus.FAILED_RETRYABLE
    assert jobs.released is True


def test_coordinator_refuses_second_concurrent_job(tmp_path: Path) -> None:
    jobs = MemoryJobs(acquire=False)
    cli = FakeCli([])

    result = coordinator(jobs, cli, RecordingSink()).run(
        batch_id=BATCH_ID,
        artifacts=prepare_artifacts(tmp_path, [success()]),
        kernel_path=tmp_path / "kernel",
        accelerator="NvidiaTeslaP100",
    )

    assert result is None
    assert cli.calls == []
    assert jobs.transitions == []

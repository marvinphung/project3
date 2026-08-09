from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Protocol
from uuid import UUID

from footballpulse_ai_content_service.batch.artifacts import BatchArtifacts
from footballpulse_ai_content_service.batch.domain import AiBatchManifest, AiBatchStatus
from footballpulse_ai_content_service.batch.importer import BatchResultImporter
from footballpulse_ai_content_service.batch.kaggle_cli import (
    KaggleCliError,
    KaggleKernelState,
)
from footballpulse_ai_content_service.batch.metadata import KaggleMetadataBuilder
from footballpulse_ai_content_service.contracts.enrichment import (
    ArticleEnrichmentInput,
    ArticleEnrichmentOutput,
)
from footballpulse_ai_content_service.validation.grounding import (
    GroundingResult,
    GroundingValidator,
)


@dataclass(frozen=True, slots=True)
class GroundedEnrichment:
    output: ArticleEnrichmentOutput
    validation: GroundingResult
    validated_at: datetime


class EnrichmentPersistenceConflict(RuntimeError):
    pass


class EnrichmentPersistenceUnavailable(RuntimeError):
    pass


class BatchJobRepository(Protocol):
    def acquire_lease(self, *, owner: str, now: datetime, lease_seconds: int) -> bool: ...

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
    ) -> None: ...

    def release_lease(self, *, owner: str) -> None: ...


class KaggleGateway(Protocol):
    def upload_dataset(self, dataset_path: Path, *, batch_id: str) -> None: ...

    def submit_kernel(self, kernel_path: Path, *, accelerator: str) -> None: ...

    def kernel_status(self, kernel_slug: str) -> KaggleKernelState: ...

    def download_output(self, kernel_slug: str, output_path: Path) -> None: ...


class EnrichmentResultSink(Protocol):
    def persist(self, outputs: tuple[GroundedEnrichment, ...]) -> None: ...


class KaggleBatchCoordinator:
    def __init__(
        self,
        *,
        jobs: BatchJobRepository,
        cli: KaggleGateway,
        sink: EnrichmentResultSink,
        kernel_slug: str,
        dataset_slug: str,
        worker_id: str,
        clock: Callable[[], datetime],
        monotonic_values: Callable[[], float] = monotonic,
        sleep: Callable[[float], None] = sleep,
        poll_interval_seconds: int = 30,
        poll_budget_seconds: int = 5_400,
        lease_seconds: int = 5_700,
    ) -> None:
        if poll_interval_seconds <= 0 or poll_budget_seconds <= 0 or lease_seconds <= 0:
            raise ValueError("coordinator timing values must be positive")
        self._jobs = jobs
        self._cli = cli
        self._sink = sink
        self._kernel_slug = kernel_slug
        self._dataset_slug = dataset_slug
        self._worker_id = worker_id
        self._clock = clock
        self._monotonic = monotonic_values
        self._sleep = sleep
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_budget_seconds = poll_budget_seconds
        self._lease_seconds = lease_seconds
        self._importer = BatchResultImporter()
        self._grounding = GroundingValidator()
        self._metadata = KaggleMetadataBuilder()
        self._metadata.validate_resource_slug(dataset_slug)

    def run(
        self,
        *,
        batch_id: UUID,
        artifacts: BatchArtifacts,
        kernel_path: Path,
        accelerator: str,
    ) -> AiBatchStatus | None:
        if not self._jobs.acquire_lease(
            owner=self._worker_id,
            now=self._clock(),
            lease_seconds=self._lease_seconds,
        ):
            return None

        current = AiBatchStatus.PREPARING
        try:
            self._metadata.write_dataset_metadata(
                target=artifacts.directory,
                dataset_slug=self._dataset_slug,
            )
            self._cli.upload_dataset(artifacts.directory, batch_id=str(batch_id))
            current = self._transition(batch_id, current, AiBatchStatus.DATASET_UPLOADED)

            self._cli.submit_kernel(kernel_path, accelerator=accelerator)
            current = self._transition(batch_id, current, AiBatchStatus.KERNEL_SUBMITTED)

            current = self._await_kernel(batch_id, current)
            current = self._transition(batch_id, current, AiBatchStatus.DOWNLOADING)
            self._cli.download_output(self._kernel_slug, artifacts.directory)
            current = self._transition(batch_id, current, AiBatchStatus.IMPORTING)

            manifest = AiBatchManifest.model_validate_json(
                artifacts.manifest_path.read_text(encoding="utf-8")
            )
            outcome = self._importer.inspect(
                manifest,
                artifacts.results_path,
                artifacts.report_path,
            )
            if outcome.terminal_errors:
                return self._transition(
                    batch_id,
                    current,
                    AiBatchStatus.FAILED_TERMINAL,
                    success_count=0,
                    error_count=len(outcome.retry_article_ids),
                    error_code="OUTPUT_INTEGRITY_FAILED",
                    error_detail="; ".join(outcome.terminal_errors)[:500],
                )

            try:
                sources = self._load_sources(artifacts.articles_path)
                grounded = tuple(
                    GroundedEnrichment(
                        output=output,
                        validation=self._grounding.validate(
                            sources[output.article_version_id], output
                        ),
                        validated_at=self._clock(),
                    )
                    for output in outcome.successes
                )
            except (OSError, KeyError, ValueError) as error:
                return self._transition(
                    batch_id,
                    current,
                    AiBatchStatus.FAILED_TERMINAL,
                    success_count=0,
                    error_count=manifest.article_count,
                    error_code="INPUT_ARTIFACT_INVALID",
                    error_detail=str(error)[:500],
                )
            self._sink.persist(grounded)
            target = AiBatchStatus.PARTIAL if outcome.retry_article_ids else AiBatchStatus.COMPLETED
            return self._transition(
                batch_id,
                current,
                target,
                success_count=len(outcome.successes),
                error_count=len(outcome.retry_article_ids),
            )
        except EnrichmentPersistenceConflict as error:
            return self._transition(
                batch_id,
                current,
                AiBatchStatus.FAILED_TERMINAL,
                error_code="ENRICHMENT_CONFLICT",
                error_detail=str(error)[:500],
            )
        except (KaggleCliError, TimeoutError, EnrichmentPersistenceUnavailable, OSError) as error:
            return self._transition(
                batch_id,
                current,
                AiBatchStatus.FAILED_RETRYABLE,
                error_code=type(error).__name__.upper(),
                error_detail=str(error)[:500],
            )
        finally:
            self._jobs.release_lease(owner=self._worker_id)

    def _await_kernel(self, batch_id: UUID, current: AiBatchStatus) -> AiBatchStatus:
        started_at = self._monotonic()
        while True:
            if not self._jobs.acquire_lease(
                owner=self._worker_id,
                now=self._clock(),
                lease_seconds=self._lease_seconds,
            ):
                raise KaggleCliError("Kaggle single-flight lease was lost")
            state = self._cli.kernel_status(self._kernel_slug)
            if state is KaggleKernelState.COMPLETE:
                return current
            if state is KaggleKernelState.ERROR:
                raise KaggleCliError("Kaggle kernel failed")
            if state is KaggleKernelState.UNKNOWN:
                raise KaggleCliError("Kaggle kernel returned an unknown status")
            if state is KaggleKernelState.RUNNING and current is AiBatchStatus.KERNEL_SUBMITTED:
                current = self._transition(batch_id, current, AiBatchStatus.RUNNING)
            if self._monotonic() - started_at >= self._poll_budget_seconds:
                raise TimeoutError("Kaggle kernel exceeded poll budget")
            self._sleep(self._poll_interval_seconds)

    def _transition(
        self,
        batch_id: UUID,
        expected: AiBatchStatus,
        target: AiBatchStatus,
        *,
        success_count: int | None = None,
        error_count: int | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> AiBatchStatus:
        self._jobs.transition(
            batch_id,
            expected=expected,
            target=target,
            now=self._clock(),
            success_count=success_count,
            error_count=error_count,
            error_code=error_code,
            error_detail=error_detail,
        )
        return target

    @staticmethod
    def _load_sources(path: Path) -> dict[UUID, ArticleEnrichmentInput]:
        sources: dict[UUID, ArticleEnrichmentInput] = {}
        with path.open(encoding="utf-8") as source_file:
            for line in source_file:
                if not line.strip():
                    continue
                source = ArticleEnrichmentInput.model_validate_json(line)
                if source.article_version_id in sources:
                    raise ValueError("duplicate article input in batch artifact")
                sources[source.article_version_id] = source
        return sources

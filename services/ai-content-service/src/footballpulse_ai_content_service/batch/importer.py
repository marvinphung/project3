from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from footballpulse_ai_content_service.batch.domain import AiBatchManifest, AiJobReport
from footballpulse_ai_content_service.contracts.batch import (
    BATCH_RECORD_ADAPTER,
    BatchRecord,
    FailedBatchRecord,
    SuccessfulBatchRecord,
)
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentOutput


@dataclass(frozen=True, slots=True)
class BatchImportOutcome:
    successes: tuple[ArticleEnrichmentOutput, ...]
    retry_article_ids: tuple[UUID, ...]
    warnings: tuple[str, ...]
    record_errors: tuple[str, ...]
    terminal_errors: tuple[str, ...]


class BatchResultImporter:
    def inspect(
        self,
        manifest: AiBatchManifest,
        results_path: Path,
        report_path: Path | None = None,
    ) -> BatchImportOutcome:
        expected = {record.article_version_id: record for record in manifest.records}
        accepted: dict[UUID, BatchRecord] = {}
        retry_ids: set[UUID] = set()
        warnings: list[str] = []
        record_errors: list[str] = []
        terminal_errors: list[str] = []

        if report_path is not None:
            report_error = self._validate_report(manifest, report_path)
            if report_error is not None:
                return BatchImportOutcome(
                    successes=(),
                    retry_article_ids=tuple(expected),
                    warnings=(),
                    record_errors=(),
                    terminal_errors=(report_error,),
                )

        if not results_path.is_file():
            return BatchImportOutcome(
                successes=(),
                retry_article_ids=tuple(expected),
                warnings=(),
                record_errors=(),
                terminal_errors=("results.jsonl is missing",),
            )

        with results_path.open(encoding="utf-8") as results:
            for line_number, line in enumerate(results, start=1):
                if not line.strip():
                    continue
                try:
                    record = BATCH_RECORD_ADAPTER.validate_json(line)
                except (ValidationError, ValueError) as error:
                    record_errors.append(
                        self._bounded(f"line {line_number}: invalid record: {error}")
                    )
                    continue

                article_id = record.article_version_id
                manifest_record = expected.get(article_id)
                if manifest_record is None:
                    warnings.append(
                        f"line {line_number}: article {article_id} not present in manifest"
                    )
                    continue

                input_hash = self._input_hash(record)
                if input_hash != manifest_record.input_hash:
                    retry_ids.add(article_id)
                    record_errors.append(
                        f"line {line_number}: input_hash mismatch for article {article_id}"
                    )
                    continue

                previous = accepted.get(article_id)
                if previous is not None:
                    if previous != record:
                        terminal_errors.append(f"conflicting duplicate for article {article_id}")
                    continue
                accepted[article_id] = record
                if isinstance(record, FailedBatchRecord):
                    retry_ids.add(article_id)

        missing = set(expected) - set(accepted)
        retry_ids.update(missing)

        if terminal_errors:
            successes: tuple[ArticleEnrichmentOutput, ...] = ()
        else:
            successful_outputs: list[ArticleEnrichmentOutput] = []
            for article_id in expected:
                accepted_record = accepted.get(article_id)
                if isinstance(accepted_record, SuccessfulBatchRecord):
                    successful_outputs.append(accepted_record.result)
            successes = tuple(successful_outputs)

        return BatchImportOutcome(
            successes=successes,
            retry_article_ids=tuple(
                article_id for article_id in expected if article_id in retry_ids
            ),
            warnings=tuple(warnings),
            record_errors=tuple(record_errors),
            terminal_errors=tuple(terminal_errors),
        )

    @staticmethod
    def _input_hash(record: BatchRecord) -> str:
        if isinstance(record, SuccessfulBatchRecord):
            return record.result.input_hash
        return record.input_hash

    @staticmethod
    def _bounded(message: str) -> str:
        return " ".join(message.split())[:400]

    @classmethod
    def _validate_report(cls, manifest: AiBatchManifest, report_path: Path) -> str | None:
        try:
            report = AiJobReport.model_validate_json(report_path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError) as error:
            return cls._bounded(f"invalid job report: {error}")
        bindings = (
            (report.batch_id, manifest.batch_id, "batch_id"),
            (report.articles_sha256, manifest.articles_sha256, "articles_sha256"),
            (report.model_version, manifest.model_version, "model_version"),
            (report.prompt_version, manifest.prompt_version, "prompt_version"),
            (report.success_count + report.error_count, manifest.article_count, "article_count"),
        )
        for actual, expected, name in bindings:
            if actual != expected:
                return f"job report {name} does not match manifest"
        return None

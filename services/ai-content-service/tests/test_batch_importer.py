from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from footballpulse_ai_content_service.batch.domain import (
    AiBatchManifest,
    AiBatchManifestRecord,
    AiBatchStatus,
)
from footballpulse_ai_content_service.batch.importer import BatchResultImporter

BATCH_ID = UUID("00000000-0000-4000-8000-000000000901")
ARTICLE_ONE = UUID("00000000-0000-4000-8000-000000000101")
ARTICLE_TWO = UUID("00000000-0000-4000-8000-000000000102")
UNKNOWN_ARTICLE = UUID("00000000-0000-4000-8000-000000000199")
HASH_ONE = "a" * 64
HASH_TWO = "b" * 64


def manifest() -> AiBatchManifest:
    return AiBatchManifest(
        contract_version="ai-batch.v1",
        batch_id=BATCH_ID,
        status=AiBatchStatus.PREPARING,
        created_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        model_version="model-v1",
        prompt_version="prompt-v1",
        article_count=2,
        articles_sha256="f" * 64,
        records=(
            AiBatchManifestRecord(article_version_id=ARTICLE_ONE, input_hash=HASH_ONE),
            AiBatchManifestRecord(article_version_id=ARTICLE_TWO, input_hash=HASH_TWO),
        ),
    )


def success_record(article_id: UUID = ARTICLE_ONE, input_hash: str = HASH_ONE) -> dict[str, object]:
    return {
        "article_version_id": str(article_id),
        "status": "SUCCESS",
        "result": {
            "contract_version": "article-enrichment.v1",
            "article_version_id": str(article_id),
            "input_hash": input_hash,
            "event_type": "TRANSFER",
            "summary_en": "Arsenal submitted an offer.",
            "claims": [],
            "model_version": "model-v1",
            "prompt_version": "prompt-v1",
        },
    }


def error_record(article_id: UUID = ARTICLE_TWO, input_hash: str = HASH_TWO) -> dict[str, object]:
    return {
        "article_version_id": str(article_id),
        "input_hash": input_hash,
        "status": "ERROR",
        "error_code": "MODEL_TIMEOUT",
        "error": "Generation exceeded its budget",
    }


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_importer_accepts_success_and_retries_article_error(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    write_jsonl(results, [success_record(), error_record()])

    outcome = BatchResultImporter().inspect(manifest(), results)

    assert [item.article_version_id for item in outcome.successes] == [ARTICLE_ONE]
    assert outcome.retry_article_ids == (ARTICLE_TWO,)
    assert outcome.terminal_errors == ()
    assert outcome.warnings == ()


def test_importer_rejects_hash_mismatch_and_marks_missing_record_for_retry(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    write_jsonl(results, [success_record(input_hash="c" * 64)])

    outcome = BatchResultImporter().inspect(manifest(), results)

    assert outcome.successes == ()
    assert set(outcome.retry_article_ids) == {ARTICLE_ONE, ARTICLE_TWO}
    assert any("input_hash mismatch" in error for error in outcome.record_errors)


def test_importer_ignores_unknown_record_and_reports_warning(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    write_jsonl(
        results,
        [success_record(), error_record(), success_record(UNKNOWN_ARTICLE, "c" * 64)],
    )

    outcome = BatchResultImporter().inspect(manifest(), results)

    assert len(outcome.successes) == 1
    assert any("not present in manifest" in warning for warning in outcome.warnings)


def test_importer_fails_terminally_on_conflicting_duplicate(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    changed = success_record()
    changed_result = changed["result"]
    assert isinstance(changed_result, dict)
    changed_result["summary_en"] = "A different result."
    write_jsonl(results, [success_record(), changed])

    outcome = BatchResultImporter().inspect(manifest(), results)

    assert outcome.successes == ()
    assert any("conflicting duplicate" in error for error in outcome.terminal_errors)


def test_importer_bounds_invalid_lines_and_retries_missing_articles(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    results.write_text("not-json " + "x" * 20_000 + "\n", encoding="utf-8")

    outcome = BatchResultImporter().inspect(manifest(), results)

    assert set(outcome.retry_article_ids) == {ARTICLE_ONE, ARTICLE_TWO}
    assert len(outcome.record_errors[0]) < 500


def test_importer_fails_terminally_when_report_is_bound_to_another_batch(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    write_jsonl(results, [success_record(), error_record()])
    report = tmp_path / "job-report.json"
    report.write_text(
        json.dumps(
            {
                "contract_version": "ai-job-report.v1",
                "batch_id": "00000000-0000-4000-8000-000000000999",
                "articles_sha256": "f" * 64,
                "model_version": "model-v1",
                "prompt_version": "prompt-v1",
                "success_count": 1,
                "error_count": 1,
                "started_at": "2026-08-10T08:00:00Z",
                "finished_at": "2026-08-10T08:01:00Z",
            }
        ),
        encoding="utf-8",
    )

    outcome = BatchResultImporter().inspect(manifest(), results, report)

    assert outcome.successes == ()
    assert set(outcome.retry_article_ids) == {ARTICLE_ONE, ARTICLE_TWO}
    assert outcome.terminal_errors == ("job report batch_id does not match manifest",)

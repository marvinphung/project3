from __future__ import annotations

from pathlib import Path
from uuid import UUID

from footballpulse_ai_content_service.contracts.batch import (
    BATCH_RECORD_ADAPTER,
    BatchRecord,
    FailedBatchRecord,
    SuccessfulBatchRecord,
)
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput
from footballpulse_ai_content_service.providers.base import ProviderName

FixtureKey = tuple[UUID, str]


class FixtureMockProvider:
    name = ProviderName.MOCK

    def __init__(self, fixtures: dict[FixtureKey, BatchRecord]) -> None:
        self._fixtures = dict(fixtures)

    @classmethod
    def from_jsonl(cls, path: Path) -> FixtureMockProvider:
        fixtures: dict[FixtureKey, BatchRecord] = {}
        with path.open(encoding="utf-8") as fixture_file:
            for line_number, line in enumerate(fixture_file, start=1):
                if not line.strip():
                    continue
                record = BATCH_RECORD_ADAPTER.validate_json(line)
                key = cls._record_key(record)
                previous = fixtures.get(key)
                if previous is not None and previous != record:
                    raise ValueError(f"conflicting mock fixture at line {line_number}")
                fixtures[key] = record
        return cls(fixtures)

    def enrich(self, inputs: tuple[ArticleEnrichmentInput, ...]) -> tuple[BatchRecord, ...]:
        records: list[BatchRecord] = []
        for source in inputs:
            fixture = self._fixtures.get((source.article_version_id, source.input_hash))
            if fixture is None:
                fixture = FailedBatchRecord(
                    article_version_id=source.article_version_id,
                    input_hash=source.input_hash,
                    status="ERROR",
                    error_code="MOCK_RESULT_NOT_FOUND",
                    error="No deterministic fixture exists for this article input",
                )
            records.append(fixture)
        return tuple(records)

    @staticmethod
    def _record_key(record: BatchRecord) -> FixtureKey:
        if isinstance(record, SuccessfulBatchRecord):
            return record.article_version_id, record.result.input_hash
        return record.article_version_id, record.input_hash

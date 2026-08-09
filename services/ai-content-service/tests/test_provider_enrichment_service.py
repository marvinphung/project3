from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from footballpulse_ai_content_service.contracts.batch import BatchRecord, FailedBatchRecord
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput
from footballpulse_ai_content_service.providers.base import ProviderName
from footballpulse_ai_content_service.providers.mock import FixtureMockProvider
from footballpulse_ai_content_service.providers.service import ProviderEnrichmentService
from footballpulse_ai_content_service.validation.grounding import GroundingStatus

ARTICLE_ID = UUID("00000000-0000-4000-8000-000000000101")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000201")
NOW = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)


def article_input() -> ArticleEnrichmentInput:
    return ArticleEnrichmentInput.model_validate(
        {
            "contract_version": "article-enrichment.v1",
            "article_version_id": str(ARTICLE_ID),
            "input_hash": "a" * 64,
            "title": "Arsenal submit offer",
            "cleaned_content": "Arsenal submitted an offer.",
            "published_at": "2026-08-10T08:00:00Z",
            "source_id": str(SOURCE_ID),
            "source_reliability_tier": 1,
            "canonical_entities": [],
            "unresolved_mentions": [],
        }
    )


class RecordingSink:
    def __init__(self) -> None:
        self.items: list[Any] = []

    def persist(self, outputs: tuple[Any, ...]) -> None:
        self.items.extend(outputs)


def mock_provider(tmp_path: Path) -> FixtureMockProvider:
    fixture = tmp_path / "mock.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "article_version_id": str(ARTICLE_ID),
                "status": "SUCCESS",
                "result": {
                    "contract_version": "article-enrichment.v1",
                    "article_version_id": str(ARTICLE_ID),
                    "input_hash": "a" * 64,
                    "event_type": "TRANSFER",
                    "summary_en": "Arsenal submitted an offer.",
                    "claims": [],
                    "model_version": "mock-v1",
                    "prompt_version": "article-enrichment-v1",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return FixtureMockProvider.from_jsonl(fixture)


def test_service_grounds_and_persists_success_from_mock(tmp_path: Path) -> None:
    sink = RecordingSink()
    service = ProviderEnrichmentService(
        provider=mock_provider(tmp_path),
        sink=sink,
        clock=lambda: NOW,
    )

    records = service.enrich((article_input(),))

    assert records[0].status == "SUCCESS"
    assert len(sink.items) == 1
    assert sink.items[0].validation.status is GroundingStatus.NEEDS_CONTENT_REVIEW
    assert sink.items[0].validated_at == NOW


class UnknownIdentityProvider:
    name = ProviderName.LOCAL

    def enrich(self, inputs: tuple[ArticleEnrichmentInput, ...]) -> tuple[BatchRecord, ...]:
        return (
            FailedBatchRecord(
                article_version_id=UUID(int=999),
                input_hash="b" * 64,
                status="ERROR",
                error_code="LOCAL_OUTPUT_INVALID",
                error="wrong identity",
            ),
        )


def test_service_rejects_provider_record_not_present_in_input_batch() -> None:
    service = ProviderEnrichmentService(
        provider=UnknownIdentityProvider(),
        sink=RecordingSink(),
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError, match="not present"):
        service.enrich((article_input(),))

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput
from footballpulse_ai_content_service.providers.base import (
    FallbackReason,
    ProviderName,
    ProviderPolicy,
)
from footballpulse_ai_content_service.providers.mock import FixtureMockProvider

ARTICLE_ID = UUID("00000000-0000-4000-8000-000000000101")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000201")
INPUT_HASH = "a" * 64


def article_input(*, input_hash: str = INPUT_HASH) -> ArticleEnrichmentInput:
    return ArticleEnrichmentInput.model_validate(
        {
            "contract_version": "article-enrichment.v1",
            "article_version_id": str(ARTICLE_ID),
            "input_hash": input_hash,
            "title": "Arsenal submit offer",
            "cleaned_content": "Arsenal submitted an offer.",
            "published_at": "2026-08-10T08:00:00Z",
            "source_id": str(SOURCE_ID),
            "source_reliability_tier": 1,
            "canonical_entities": [],
            "unresolved_mentions": [],
        }
    )


def success_record() -> dict[str, object]:
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
            "model_version": "mock-v1",
            "prompt_version": "article-enrichment-v1",
        },
    }


def write_fixture(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_mock_returns_fixture_by_article_and_input_hash(tmp_path: Path) -> None:
    fixture = tmp_path / "results.jsonl"
    write_fixture(fixture, [success_record()])
    provider = FixtureMockProvider.from_jsonl(fixture)

    records = provider.enrich((article_input(),))

    assert len(records) == 1
    assert records[0].status == "SUCCESS"
    assert records[0].article_version_id == ARTICLE_ID


def test_mock_fails_closed_for_unknown_input(tmp_path: Path) -> None:
    fixture = tmp_path / "results.jsonl"
    write_fixture(fixture, [success_record()])
    provider = FixtureMockProvider.from_jsonl(fixture)

    records = provider.enrich((article_input(input_hash="b" * 64),))

    record = records[0]
    assert record.status == "ERROR"
    assert record.error_code == "MOCK_RESULT_NOT_FOUND"
    assert record.input_hash == "b" * 64


def test_mock_rejects_conflicting_fixture_identity(tmp_path: Path) -> None:
    fixture = tmp_path / "results.jsonl"
    changed = success_record()
    changed_result = changed["result"]
    assert isinstance(changed_result, dict)
    changed_result["summary_en"] = "Different output."
    write_fixture(fixture, [success_record(), changed])

    with pytest.raises(ValueError, match="conflicting mock fixture"):
        FixtureMockProvider.from_jsonl(fixture)


@pytest.mark.parametrize(
    "reason",
    [
        FallbackReason.NETWORK_UNAVAILABLE,
        FallbackReason.SERVICE_UNAVAILABLE,
        FallbackReason.QUOTA_EXHAUSTED,
        FallbackReason.GPU_UNAVAILABLE,
        FallbackReason.KERNEL_TIMEOUT,
        FallbackReason.KERNEL_INFRASTRUCTURE,
    ],
)
def test_policy_allows_local_only_for_approved_infrastructure_failures(
    reason: FallbackReason,
) -> None:
    policy = ProviderPolicy(primary=ProviderName.KAGGLE, allow_local_fallback=True)

    assert policy.should_use_local(reason) is True


@pytest.mark.parametrize(
    "reason",
    [
        FallbackReason.CREDENTIAL_INVALID,
        FallbackReason.RESOURCE_PUBLIC,
        FallbackReason.INPUT_INTEGRITY,
        FallbackReason.OUTPUT_SCHEMA,
        FallbackReason.OUTPUT_GROUNDING,
        FallbackReason.CONFLICTING_OUTPUT,
    ],
)
def test_policy_never_hides_configuration_or_integrity_failure(reason: FallbackReason) -> None:
    policy = ProviderPolicy(primary=ProviderName.KAGGLE, allow_local_fallback=True)

    assert policy.should_use_local(reason) is False


def test_mock_requires_explicit_demo_permission() -> None:
    with pytest.raises(ValueError, match="mock provider"):
        ProviderPolicy(primary=ProviderName.MOCK)

    assert ProviderPolicy(primary=ProviderName.MOCK, allow_mock=True).primary is ProviderName.MOCK

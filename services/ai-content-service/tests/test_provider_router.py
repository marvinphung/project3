from __future__ import annotations

from uuid import UUID

import pytest
from footballpulse_ai_content_service.batch.kaggle_cli import KaggleFailureKind
from footballpulse_ai_content_service.contracts.batch import BatchRecord, FailedBatchRecord
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput
from footballpulse_ai_content_service.providers.base import (
    FallbackReason,
    ProviderFailure,
    ProviderName,
    ProviderPolicy,
)
from footballpulse_ai_content_service.providers.router import (
    FallbackProviderRouter,
    fallback_reason_from_kaggle_error,
)

ARTICLE_ID = UUID("00000000-0000-4000-8000-000000000101")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000201")


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


class StubProvider:
    def __init__(
        self,
        name: ProviderName,
        *,
        records: tuple[BatchRecord, ...] = (),
        failure: Exception | None = None,
    ) -> None:
        self.name = name
        self.records = records
        self.failure = failure
        self.calls = 0

    def enrich(self, inputs: tuple[ArticleEnrichmentInput, ...]) -> tuple[BatchRecord, ...]:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return self.records


def local_record() -> FailedBatchRecord:
    return FailedBatchRecord(
        article_version_id=ARTICLE_ID,
        input_hash="a" * 64,
        status="ERROR",
        error_code="LOCAL_OUTPUT_INVALID",
        error="fixture",
    )


def test_router_falls_back_to_local_for_typed_infrastructure_failure() -> None:
    kaggle = StubProvider(
        ProviderName.KAGGLE,
        failure=ProviderFailure(FallbackReason.QUOTA_EXHAUSTED, "quota unavailable"),
    )
    local = StubProvider(ProviderName.LOCAL, records=(local_record(),))
    router = FallbackProviderRouter(
        primary=kaggle,
        local=local,
        policy=ProviderPolicy(ProviderName.KAGGLE, allow_local_fallback=True),
    )

    result = router.enrich((article_input(),))

    assert result == (local_record(),)
    assert kaggle.calls == 1
    assert local.calls == 1


def test_router_does_not_hide_integrity_failure() -> None:
    failure = ProviderFailure(FallbackReason.INPUT_INTEGRITY, "checksum mismatch")
    kaggle = StubProvider(ProviderName.KAGGLE, failure=failure)
    local = StubProvider(ProviderName.LOCAL, records=(local_record(),))
    router = FallbackProviderRouter(
        primary=kaggle,
        local=local,
        policy=ProviderPolicy(ProviderName.KAGGLE, allow_local_fallback=True),
    )

    with pytest.raises(ProviderFailure) as raised:
        router.enrich((article_input(),))

    assert raised.value is failure
    assert local.calls == 0


def test_router_never_falls_back_on_untyped_programming_error() -> None:
    kaggle = StubProvider(ProviderName.KAGGLE, failure=RuntimeError("bug"))
    local = StubProvider(ProviderName.LOCAL, records=(local_record(),))
    router = FallbackProviderRouter(
        primary=kaggle,
        local=local,
        policy=ProviderPolicy(ProviderName.KAGGLE, allow_local_fallback=True),
    )

    with pytest.raises(RuntimeError, match="bug"):
        router.enrich((article_input(),))

    assert local.calls == 0


def test_router_requires_local_provider_when_fallback_enabled() -> None:
    with pytest.raises(ValueError, match="local provider"):
        FallbackProviderRouter(
            primary=StubProvider(ProviderName.KAGGLE),
            local=None,
            policy=ProviderPolicy(ProviderName.KAGGLE, allow_local_fallback=True),
        )


def test_kaggle_job_error_mapping_is_fail_closed() -> None:
    assert (
        fallback_reason_from_kaggle_error(KaggleFailureKind.QUOTA_EXHAUSTED.value)
        is FallbackReason.QUOTA_EXHAUSTED
    )
    assert fallback_reason_from_kaggle_error("TIMEOUTERROR") is FallbackReason.KERNEL_TIMEOUT
    assert fallback_reason_from_kaggle_error(KaggleFailureKind.UNKNOWN.value) is None
    assert fallback_reason_from_kaggle_error("OUTPUT_INTEGRITY_FAILED") is None

from __future__ import annotations

from footballpulse_ai_content_service.batch.kaggle_cli import KaggleFailureKind
from footballpulse_ai_content_service.contracts.batch import BatchRecord
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput
from footballpulse_ai_content_service.providers.base import (
    EnrichmentProvider,
    FallbackReason,
    ProviderFailure,
    ProviderPolicy,
)

_KAGGLE_FALLBACK_REASONS = {
    KaggleFailureKind.NETWORK_UNAVAILABLE: FallbackReason.NETWORK_UNAVAILABLE,
    KaggleFailureKind.SERVICE_UNAVAILABLE: FallbackReason.SERVICE_UNAVAILABLE,
    KaggleFailureKind.QUOTA_EXHAUSTED: FallbackReason.QUOTA_EXHAUSTED,
    KaggleFailureKind.GPU_UNAVAILABLE: FallbackReason.GPU_UNAVAILABLE,
    KaggleFailureKind.CREDENTIAL_INVALID: FallbackReason.CREDENTIAL_INVALID,
}


def fallback_reason_from_kaggle_error(error_code: str) -> FallbackReason | None:
    if error_code == "TIMEOUTERROR":
        return FallbackReason.KERNEL_TIMEOUT
    try:
        kind = KaggleFailureKind(error_code)
    except ValueError:
        return None
    return _KAGGLE_FALLBACK_REASONS.get(kind)


class FallbackProviderRouter:
    def __init__(
        self,
        *,
        primary: EnrichmentProvider,
        local: EnrichmentProvider | None,
        policy: ProviderPolicy,
    ) -> None:
        if primary.name is not policy.primary:
            raise ValueError("primary provider does not match configured policy")
        if policy.allow_local_fallback and local is None:
            raise ValueError("local provider is required when local fallback is enabled")
        self.name = primary.name
        self._primary = primary
        self._local = local
        self._policy = policy

    def enrich(self, inputs: tuple[ArticleEnrichmentInput, ...]) -> tuple[BatchRecord, ...]:
        try:
            return self._primary.enrich(inputs)
        except ProviderFailure as error:
            if not self._policy.should_use_local(error.reason):
                raise
            if self._local is None:
                raise RuntimeError("local fallback provider is unavailable") from error
            return self._local.enrich(inputs)

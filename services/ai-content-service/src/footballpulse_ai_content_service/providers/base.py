from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from footballpulse_ai_content_service.contracts.batch import BatchRecord
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput


class ProviderName(StrEnum):
    KAGGLE = "kaggle"
    LOCAL = "local"
    MOCK = "mock"


class FallbackReason(StrEnum):
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    GPU_UNAVAILABLE = "GPU_UNAVAILABLE"
    KERNEL_TIMEOUT = "KERNEL_TIMEOUT"
    KERNEL_INFRASTRUCTURE = "KERNEL_INFRASTRUCTURE"
    CREDENTIAL_INVALID = "CREDENTIAL_INVALID"
    RESOURCE_PUBLIC = "RESOURCE_PUBLIC"
    INPUT_INTEGRITY = "INPUT_INTEGRITY"
    OUTPUT_SCHEMA = "OUTPUT_SCHEMA"
    OUTPUT_GROUNDING = "OUTPUT_GROUNDING"
    CONFLICTING_OUTPUT = "CONFLICTING_OUTPUT"


class ProviderFailure(RuntimeError):
    def __init__(self, reason: FallbackReason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


_LOCAL_FALLBACK_REASONS = frozenset(
    {
        FallbackReason.NETWORK_UNAVAILABLE,
        FallbackReason.SERVICE_UNAVAILABLE,
        FallbackReason.QUOTA_EXHAUSTED,
        FallbackReason.GPU_UNAVAILABLE,
        FallbackReason.KERNEL_TIMEOUT,
        FallbackReason.KERNEL_INFRASTRUCTURE,
    }
)


class EnrichmentProvider(Protocol):
    name: ProviderName

    def enrich(self, inputs: tuple[ArticleEnrichmentInput, ...]) -> tuple[BatchRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class ProviderPolicy:
    primary: ProviderName
    allow_local_fallback: bool = False
    allow_mock: bool = False

    def __post_init__(self) -> None:
        if self.primary is ProviderName.MOCK and not self.allow_mock:
            raise ValueError("mock provider requires explicit demo/test permission")

    def should_use_local(self, reason: FallbackReason) -> bool:
        return self.allow_local_fallback and reason in _LOCAL_FALLBACK_REASONS

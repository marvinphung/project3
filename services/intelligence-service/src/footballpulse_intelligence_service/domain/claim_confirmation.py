from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ClaimConfirmation(StrEnum):
    RUMOUR = "RUMOUR"
    REPORTED = "REPORTED"
    MULTI_SOURCE = "MULTI_SOURCE"
    OFFICIAL = "OFFICIAL"


@dataclass(frozen=True, slots=True)
class ClaimEvidenceSource:
    source_id: UUID
    source_cluster_id: UUID | None
    is_official: bool
    supports_claim: bool


@dataclass(frozen=True, slots=True)
class ClaimConfirmationResult:
    level: ClaimConfirmation
    independent_source_count: int


def calculate_claim_confirmation(
    evidence_sources: tuple[ClaimEvidenceSource, ...],
) -> ClaimConfirmationResult:
    supporting = tuple(item for item in evidence_sources if item.supports_claim)
    independent_clusters = {
        item.source_cluster_id if item.source_cluster_id is not None else item.source_id
        for item in supporting
    }
    if any(item.is_official for item in supporting):
        level = ClaimConfirmation.OFFICIAL
    elif len(independent_clusters) >= 2:
        level = ClaimConfirmation.MULTI_SOURCE
    elif supporting:
        level = ClaimConfirmation.REPORTED
    else:
        level = ClaimConfirmation.RUMOUR
    return ClaimConfirmationResult(level, len(independent_clusters))

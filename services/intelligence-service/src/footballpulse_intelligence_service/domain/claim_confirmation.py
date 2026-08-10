from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from footballpulse_intelligence_service.domain.story import ClaimEvidence, StorySource


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


def calculate_claim_confirmation_from_evidence(
    evidence: tuple[ClaimEvidence, ...],
    sources: tuple[StorySource, ...],
) -> ClaimConfirmationResult:
    source_by_link = {source.id: source for source in sources}
    evidence_sources: list[ClaimEvidenceSource] = []
    for item in evidence:
        source = source_by_link.get(item.story_source_id)
        if source is None:
            raise ValueError("claim evidence references an unknown StorySource")
        evidence_sources.append(
            ClaimEvidenceSource(
                source_id=source.source_id,
                source_cluster_id=source.source_cluster_id,
                is_official=source.is_official,
                supports_claim=True,
            )
        )
    return calculate_claim_confirmation(tuple(evidence_sources))

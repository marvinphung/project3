from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_intelligence_service.domain.claim_confirmation import (
    ClaimConfirmation,
    ClaimEvidenceSource,
    calculate_claim_confirmation,
    calculate_claim_confirmation_from_evidence,
)
from footballpulse_intelligence_service.domain.story import ClaimEvidence, StorySource

SOURCE_A = UUID(int=1)
SOURCE_B = UUID(int=2)
SOURCE_C = UUID(int=3)
CLUSTER_NEWS = UUID(int=10)
CLUSTER_OFFICIAL = UUID(int=20)


def evidence(
    source_id: UUID,
    *,
    cluster_id: UUID | None = None,
    official: bool = False,
    supports: bool = True,
) -> ClaimEvidenceSource:
    return ClaimEvidenceSource(
        source_id=source_id,
        source_cluster_id=cluster_id,
        is_official=official,
        supports_claim=supports,
    )


def test_single_report_is_reported() -> None:
    result = calculate_claim_confirmation((evidence(SOURCE_A),))

    assert result.level is ClaimConfirmation.REPORTED
    assert result.independent_source_count == 1


def test_syndicated_sources_count_as_one_independent_source() -> None:
    result = calculate_claim_confirmation(
        (
            evidence(SOURCE_A, cluster_id=CLUSTER_NEWS),
            evidence(SOURCE_B, cluster_id=CLUSTER_NEWS),
        )
    )

    assert result.level is ClaimConfirmation.REPORTED
    assert result.independent_source_count == 1


def test_two_independent_sources_are_multi_source() -> None:
    result = calculate_claim_confirmation(
        (
            evidence(SOURCE_A, cluster_id=CLUSTER_NEWS),
            evidence(SOURCE_B, cluster_id=CLUSTER_OFFICIAL),
        )
    )

    assert result.level is ClaimConfirmation.MULTI_SOURCE
    assert result.independent_source_count == 2


def test_official_support_takes_precedence() -> None:
    result = calculate_claim_confirmation(
        (
            evidence(SOURCE_A, cluster_id=CLUSTER_NEWS),
            evidence(SOURCE_C, cluster_id=CLUSTER_OFFICIAL, official=True),
        )
    )

    assert result.level is ClaimConfirmation.OFFICIAL


def test_denial_does_not_confirm_the_positive_claim() -> None:
    result = calculate_claim_confirmation((evidence(SOURCE_A, supports=False),))

    assert result.level is ClaimConfirmation.RUMOUR
    assert result.independent_source_count == 0


def test_confirmation_can_be_calculated_from_story_evidence_and_sources() -> None:
    evidence_a = ClaimEvidence.create(
        evidence_id=UUID(int=100),
        claim_id=UUID(int=101),
        story_source_id=UUID(int=102),
        quote="reported",
        start=0,
        end=8,
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )
    evidence_b = ClaimEvidence.create(
        evidence_id=UUID(int=103),
        claim_id=evidence_a.claim_id,
        story_source_id=UUID(int=104),
        quote="confirmed",
        start=0,
        end=9,
        now=evidence_a.created_at,
    )
    sources = (
        StorySource.create(
            link_id=evidence_a.story_source_id,
            story_id=UUID(int=105),
            article_version_id=UUID(int=106),
            source_id=SOURCE_A,
            source_reliability_tier=1,
            published_at=evidence_a.created_at,
            observed_at=evidence_a.created_at,
            source_cluster_id=CLUSTER_NEWS,
        ),
        StorySource.create(
            link_id=evidence_b.story_source_id,
            story_id=UUID(int=105),
            article_version_id=UUID(int=107),
            source_id=SOURCE_B,
            source_reliability_tier=1,
            published_at=evidence_b.created_at,
            observed_at=evidence_b.created_at,
            source_cluster_id=CLUSTER_OFFICIAL,
            is_official=True,
        ),
    )

    result = calculate_claim_confirmation_from_evidence((evidence_a, evidence_b), sources)

    assert result.level is ClaimConfirmation.OFFICIAL

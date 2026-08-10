from __future__ import annotations

from uuid import UUID

from footballpulse_intelligence_service.domain.claim_confirmation import (
    ClaimConfirmation,
    ClaimEvidenceSource,
    calculate_claim_confirmation,
)

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

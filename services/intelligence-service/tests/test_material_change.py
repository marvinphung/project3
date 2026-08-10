from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.material_change import detect_material_change
from footballpulse_intelligence_service.domain.story import Claim, ClaimPredicate

NOW = datetime(2026, 8, 1, tzinfo=UTC)
STORY_ID = UUID(int=1)
PLAYER_ID = UUID(int=2)
CLUB_ID = UUID(int=3)


def claim(
    claim_id: int,
    *,
    predicate: ClaimPredicate = ClaimPredicate.SUBMITTED_BID,
    amount: int = 180_000_000,
    statement: str = "Arsenal submitted a bid.",
    confirmation: ClaimConfirmation = ClaimConfirmation.REPORTED,
) -> Claim:
    return Claim.create(
        claim_id=UUID(int=claim_id),
        story_id=STORY_ID,
        subject_entity_id=CLUB_ID,
        predicate=predicate,
        object_entity_id=PLAYER_ID,
        object_value={"amount": amount, "currency": "EUR"},
        statement_en=statement,
        certainty=Decimal("0.8"),
        occurred_at=NOW,
        occurred_at_bucket=NOW,
        now=NOW,
        confirmation=confirmation,
    )


def test_00h_first_claim_is_material() -> None:
    result = detect_material_change((), (claim(10),))

    assert result.changed is True
    assert result.reason_codes == ("NEW_CLAIM",)


def test_06h_wording_only_change_is_not_material() -> None:
    result = detect_material_change(
        (claim(10, statement="Arsenal submitted a bid."),),
        (claim(11, statement="A bid was submitted by Arsenal."),),
    )

    assert result.changed is False
    assert result.reason_codes == ()


def test_12h_qualifier_change_is_material() -> None:
    result = detect_material_change((claim(10),), (claim(11, amount=150_000_000),))

    assert result.changed is True
    assert result.reason_codes == ("CLAIM_SEMANTICS_CHANGED",)


def test_18h_unchanged_claim_is_not_material() -> None:
    result = detect_material_change(
        (claim(10, amount=150_000_000),),
        (claim(11, amount=150_000_000),),
    )

    assert result.changed is False


def test_confirmation_transition_is_material() -> None:
    result = detect_material_change(
        (claim(10, confirmation=ClaimConfirmation.REPORTED),),
        (claim(11, confirmation=ClaimConfirmation.MULTI_SOURCE),),
    )

    assert result.changed is True
    assert result.reason_codes == ("CONFIRMATION_CHANGED",)


def test_denial_as_new_predicate_is_material() -> None:
    result = detect_material_change(
        (claim(10),),
        (
            claim(
                11,
                predicate=ClaimPredicate.DENIED_REPORT,
                statement="Real Madrid denied the report.",
            ),
        ),
    )

    assert result.changed is True
    assert result.reason_codes == ("NEW_CLAIM",)

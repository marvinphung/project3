from __future__ import annotations

from uuid import UUID

from footballpulse_ai_content_service.contracts.enrichment import (
    ClaimCertainty,
    ClaimOutput,
    ClaimQualifiers,
    Predicate,
)
from footballpulse_ai_content_service.contracts.presentation import VietnameseProjection
from footballpulse_ai_content_service.processing.claims import merge_claims
from footballpulse_ai_content_service.validation.translation import (
    TranslationRejectionCode,
    TranslationValidator,
)

ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")


def valid_claim() -> ClaimOutput:
    quote = "Arsenal reportedly submitted a 180 million euro offer for Vinicius Junior."
    return ClaimOutput(
        subject_entity_id=ARSENAL_ID,
        predicate=Predicate.SUBMITTED_BID,
        object_entity_id=PLAYER_ID,
        object_text=None,
        qualifiers=ClaimQualifiers(amount=180_000_000, currency="EUR"),
        certainty=ClaimCertainty.REPORTED,
        evidence_quote=quote,
        evidence_start=0,
        evidence_end=len(quote),
    )


def test_vietnamese_projection_accepts_same_claim_and_factual_anchors() -> None:
    claim = merge_claims([valid_claim()])[0]
    projection = VietnameseProjection(
        summary_vi="Arsenal được cho là đã gửi đề nghị 180 triệu EUR cho Vinicius Junior.",
        used_claim_ids=(claim.claim_id,),
    )

    result = TranslationValidator().validate(
        projection,
        (claim,),
        entity_names={ARSENAL_ID: "Arsenal", PLAYER_ID: "Vinícius Júnior"},
    )

    assert result.is_valid is True
    assert result.codes == ()


def test_vietnamese_projection_rejects_unknown_claim_and_added_amount() -> None:
    claim = merge_claims([valid_claim()])[0]
    unknown_claim = claim.claim_id.__class__("018f8b45-b634-7c81-a47d-9a7c2f3c9999")
    projection = VietnameseProjection(
        summary_vi="Arsenal đã gửi đề nghị 200 triệu EUR cho Vinicius Junior.",
        used_claim_ids=(claim.claim_id, unknown_claim),
    )

    result = TranslationValidator().validate(
        projection,
        (claim,),
        entity_names={ARSENAL_ID: "Arsenal", PLAYER_ID: "Vinicius Junior"},
    )

    assert result.is_valid is False
    assert TranslationRejectionCode.UNKNOWN_CLAIM_ID in result.codes
    assert TranslationRejectionCode.FACTUAL_ANCHOR_MISMATCH in result.codes


def test_vietnamese_projection_cannot_add_denial() -> None:
    claim = merge_claims([valid_claim()])[0]
    projection = VietnameseProjection(
        summary_vi="Arsenal phủ nhận đã gửi đề nghị cho Vinicius Junior.",
        used_claim_ids=(claim.claim_id,),
    )

    result = TranslationValidator().validate(
        projection,
        (claim,),
        entity_names={ARSENAL_ID: "Arsenal", PLAYER_ID: "Vinicius Junior"},
    )

    assert TranslationRejectionCode.NEGATION_MISMATCH in result.codes


def test_vietnamese_projection_cannot_strengthen_report_to_official_confirmation() -> None:
    claim = merge_claims([valid_claim()])[0]
    projection = VietnameseProjection(
        summary_vi="Arsenal chính thức xác nhận đề nghị cho Vinicius Junior.",
        used_claim_ids=(claim.claim_id,),
    )

    result = TranslationValidator().validate(
        projection,
        (claim,),
        entity_names={ARSENAL_ID: "Arsenal", PLAYER_ID: "Vinicius Junior"},
    )

    assert TranslationRejectionCode.CERTAINTY_MISMATCH in result.codes


def test_vietnamese_projection_rejects_unbounded_numeric_anchor_without_crashing() -> None:
    claim = merge_claims([valid_claim()])[0]
    projection = VietnameseProjection(
        summary_vi=f"Arsenal đề nghị {'9' * 100} triệu EUR.",
        used_claim_ids=(claim.claim_id,),
    )

    result = TranslationValidator().validate(
        projection,
        (claim,),
        entity_names={ARSENAL_ID: "Arsenal", PLAYER_ID: "Vinicius Junior"},
    )

    assert TranslationRejectionCode.FACTUAL_ANCHOR_MISMATCH in result.codes

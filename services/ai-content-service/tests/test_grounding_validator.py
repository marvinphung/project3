from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_ai_content_service.contracts.enrichment import (
    ArticleEnrichmentInput,
    ArticleEnrichmentOutput,
    CanonicalEntityInput,
    ClaimCertainty,
    ClaimOutput,
    ClaimQualifiers,
    EntityType,
    EventType,
    Predicate,
)
from footballpulse_ai_content_service.validation.grounding import (
    ClaimRejectionCode,
    GroundingStatus,
    GroundingValidator,
)

ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c3101")
PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")
ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
CONTENT = "Arsenal reportedly submitted a 180 million euro offer for Vinicius Junior."


def valid_input() -> ArticleEnrichmentInput:
    return ArticleEnrichmentInput(
        contract_version="article-enrichment.v1",
        article_version_id=ARTICLE_ID,
        input_hash="a" * 64,
        title="Arsenal submit offer for Vinicius Junior",
        cleaned_content=CONTENT,
        published_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        source_id=UUID("018f8b45-b634-7c81-a47d-9a7c2f3c1101"),
        source_reliability_tier=2,
        canonical_entities=(
            CanonicalEntityInput(
                entity_id=ARSENAL_ID,
                entity_type=EntityType.CLUB,
                canonical_name="Arsenal",
            ),
            CanonicalEntityInput(
                entity_id=PLAYER_ID,
                entity_type=EntityType.PLAYER,
                canonical_name="Vinícius Júnior",
            ),
        ),
        unresolved_mentions=(),
    )


def valid_claim() -> ClaimOutput:
    return ClaimOutput(
        subject_entity_id=ARSENAL_ID,
        predicate=Predicate.SUBMITTED_BID,
        object_entity_id=PLAYER_ID,
        object_text=None,
        qualifiers=ClaimQualifiers(amount=180_000_000, currency="EUR"),
        certainty=ClaimCertainty.REPORTED,
        evidence_quote=CONTENT,
        evidence_start=0,
        evidence_end=len(CONTENT),
    )


def valid_output() -> ArticleEnrichmentOutput:
    return ArticleEnrichmentOutput(
        contract_version="article-enrichment.v1",
        article_version_id=ARTICLE_ID,
        input_hash="a" * 64,
        event_type=EventType.TRANSFER,
        summary_en="Arsenal reportedly submitted an offer for Vinicius Junior.",
        claims=(valid_claim(),),
        model_version="qwen3-8b-fixture",
        prompt_version="article-enrichment-v1",
    )


def test_grounding_accepts_exact_evidence_entities_qualifiers_and_reported_certainty() -> None:
    result = GroundingValidator().validate(valid_input(), valid_output())

    assert result.status is GroundingStatus.VALIDATED
    assert result.valid_claims == valid_output().claims
    assert result.rejected_claims == ()
    assert result.summary_en == valid_output().summary_en


def test_grounding_rejects_claims_independently_and_preserves_valid_claims() -> None:
    valid = valid_claim()
    invalid_evidence = valid.model_copy(
        update={"evidence_quote": "fabricated quote"},
    )
    invalid_entity = valid.model_copy(
        update={"subject_entity_id": "018f8b45-b634-7c81-a47d-9a7c2f3c8999"},
    )
    output = valid_output().model_copy(update={"claims": (valid, invalid_evidence, invalid_entity)})

    result = GroundingValidator().validate(valid_input(), output)

    assert result.status is GroundingStatus.PARTIAL
    assert result.valid_claims == (valid,)
    assert len(result.rejected_claims) == 2
    assert result.summary_en is None
    codes = {code for rejected in result.rejected_claims for code in rejected.codes}
    assert ClaimRejectionCode.EVIDENCE_MISMATCH in codes
    assert ClaimRejectionCode.UNKNOWN_ENTITY in codes


def test_grounding_rejects_unsupported_qualifier_event_and_overstated_certainty() -> None:
    claim = valid_claim().model_copy(
        update={
            "qualifiers": ClaimQualifiers(amount=200_000_000, currency="GBP"),
            "certainty": ClaimCertainty.CONFIRMED,
        }
    )
    output = valid_output().model_copy(update={"event_type": EventType.INJURY, "claims": (claim,)})

    result = GroundingValidator().validate(valid_input(), output)

    assert result.status is GroundingStatus.NEEDS_CONTENT_REVIEW
    codes = set(result.rejected_claims[0].codes)
    assert ClaimRejectionCode.EVENT_PREDICATE_MISMATCH in codes
    assert ClaimRejectionCode.QUALIFIER_NOT_IN_EVIDENCE in codes
    assert ClaimRejectionCode.CERTAINTY_OVERSTATED in codes


def test_manifest_identity_mismatch_invalidates_whole_output() -> None:
    output = valid_output().model_copy(update={"input_hash": "b" * 64})

    result = GroundingValidator().validate(valid_input(), output)

    assert result.status is GroundingStatus.AI_OUTPUT_INVALID
    assert result.valid_claims == ()
    assert result.top_level_errors == ("INPUT_HASH_MISMATCH",)


def test_empty_claims_or_summary_with_added_fact_requires_content_review() -> None:
    empty = valid_output().model_copy(update={"claims": ()})
    assert (
        GroundingValidator().validate(valid_input(), empty).status
        is GroundingStatus.NEEDS_CONTENT_REVIEW
    )

    hallucinated_summary = valid_output().model_copy(
        update={"summary_en": "Arsenal reportedly submitted a 200 million euro offer."}
    )
    result = GroundingValidator().validate(valid_input(), hallucinated_summary)
    assert result.status is GroundingStatus.NEEDS_CONTENT_REVIEW
    assert result.valid_claims == (valid_claim(),)
    assert result.top_level_errors == ("SUMMARY_NOT_GROUNDED",)


def test_denial_must_use_denial_predicate_and_certainty() -> None:
    quote = "Real Madrid officially denied the report."
    content = f"{CONTENT} {quote}"
    source = valid_input().model_copy(update={"cleaned_content": content})
    start = content.index(quote)
    denial = valid_claim().model_copy(
        update={
            "predicate": Predicate.DENIED_REPORT,
            "certainty": ClaimCertainty.DENIED,
            "qualifiers": ClaimQualifiers(),
            "evidence_quote": quote,
            "evidence_start": start,
            "evidence_end": start + len(quote),
        }
    )
    output = valid_output().model_copy(update={"claims": (denial,)})

    result = GroundingValidator().validate(source, output)

    assert result.status is GroundingStatus.VALIDATED


def test_other_event_cannot_bypass_predicate_compatibility() -> None:
    output = valid_output().model_copy(update={"event_type": EventType.OTHER})

    result = GroundingValidator().validate(valid_input(), output)

    assert result.status is GroundingStatus.NEEDS_CONTENT_REVIEW
    assert ClaimRejectionCode.EVENT_PREDICATE_MISMATCH in result.rejected_claims[0].codes

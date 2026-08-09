from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
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
    UnresolvedMentionInput,
)
from pydantic import ValidationError

ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c3101")
PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")
ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
PUBLISHED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
CONTENT = "Arsenal reportedly submitted a 180 million euro offer for Vinicius Junior."


def valid_input() -> ArticleEnrichmentInput:
    return ArticleEnrichmentInput(
        contract_version="article-enrichment.v1",
        article_version_id=ARTICLE_ID,
        input_hash="a" * 64,
        title="Arsenal submit offer for Vinicius Junior",
        cleaned_content=CONTENT,
        published_at=PUBLISHED_AT,
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
        unresolved_mentions=(
            UnresolvedMentionInput(
                text="180 million euro",
                predicted_type=EntityType.COMPETITION,
                start=31,
                end=47,
                score=0.51,
            ),
        ),
    )


def valid_claim() -> ClaimOutput:
    start = CONTENT.index("Arsenal")
    return ClaimOutput(
        subject_entity_id=ARSENAL_ID,
        predicate=Predicate.SUBMITTED_BID,
        object_entity_id=PLAYER_ID,
        object_text=None,
        qualifiers=ClaimQualifiers(amount=180_000_000, currency="EUR"),
        certainty=ClaimCertainty.REPORTED,
        evidence_quote=CONTENT,
        evidence_start=start,
        evidence_end=start + len(CONTENT),
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


def test_strict_input_and_output_contract_accept_valid_payloads() -> None:
    assert valid_input().article_version_id == ARTICLE_ID
    assert valid_output().claims[0].predicate is Predicate.SUBMITTED_BID


def test_contract_forbids_unknown_fields_and_dangerous_numeric_coercion() -> None:
    payload = valid_output().model_dump(mode="json")
    payload["claims"][0]["qualifiers"]["amount"] = "180000000"
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        ArticleEnrichmentOutput.model_validate_json(json.dumps(payload))


def test_claim_requires_exactly_one_object_representation() -> None:
    payload = valid_claim().model_dump()
    payload["object_text"] = "Vinicius Junior"

    with pytest.raises(ValidationError, match="exactly one"):
        ClaimOutput.model_validate(payload)


def test_contract_rejects_unknown_predicate_and_unbounded_evidence() -> None:
    payload = valid_claim().model_dump(mode="json")
    payload["predicate"] = "MODEL_INVENTED_PREDICATE"
    with pytest.raises(ValidationError):
        ClaimOutput.model_validate(payload)


def test_contract_accepts_source_tier_five_and_rejects_impossible_date() -> None:
    payload = valid_input().model_dump()
    payload["source_reliability_tier"] = 5
    assert ArticleEnrichmentInput.model_validate(payload).source_reliability_tier == 5

    with pytest.raises(ValidationError, match="calendar date"):
        ClaimQualifiers(date="2026-99-99")

    with pytest.raises(ValidationError):
        ArticleEnrichmentOutput.model_validate({**valid_output().model_dump(), "summary_en": "   "})

    payload = valid_claim().model_dump(mode="json")
    payload["evidence_quote"] = "x" * 4_001
    with pytest.raises(ValidationError):
        ClaimOutput.model_validate(payload)

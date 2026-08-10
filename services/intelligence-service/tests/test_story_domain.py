from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.entity import EntityType
from footballpulse_intelligence_service.domain.story import (
    Claim,
    ClaimEvidence,
    ClaimPredicate,
    Story,
    StoryEntity,
    StoryEventType,
    StorySource,
    StoryStatus,
)

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
STORY_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb001")
SOURCE_LINK_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb002")
ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb003")
SOURCE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb004")
PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")
CLUB_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
CLAIM_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb005")


def test_story_create_and_update_preserve_optimistic_version_invariants() -> None:
    story = Story.create(
        story_id=STORY_ID,
        event_type=StoryEventType.TRANSFER,
        first_seen_at=NOW,
        confidence_score=Decimal("0.6500"),
    )

    updated = story.observe(at=NOW + timedelta(hours=6), confidence_score=Decimal("0.8000"))
    confirmed = updated.change_status(StoryStatus.CONFIRMED, now=NOW + timedelta(hours=6))

    assert story.status is StoryStatus.DEVELOPING
    assert story.version == 1
    assert updated.last_seen_at == NOW + timedelta(hours=6)
    assert updated.version == 2
    assert confirmed.status is StoryStatus.CONFIRMED
    assert confirmed.version == 3


@pytest.mark.parametrize("score", [Decimal("-0.0001"), Decimal("1.0001")])
def test_story_rejects_confidence_outside_closed_unit_interval(score: Decimal) -> None:
    with pytest.raises(ValueError, match="confidence"):
        Story.create(
            story_id=STORY_ID,
            event_type=StoryEventType.TRANSFER,
            first_seen_at=NOW,
            confidence_score=score,
        )


def test_story_rejects_naive_or_backward_observation_time() -> None:
    story = Story.create(
        story_id=STORY_ID,
        event_type=StoryEventType.TRANSFER,
        first_seen_at=NOW,
        confidence_score=Decimal("0.5"),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        Story.create(
            story_id=STORY_ID,
            event_type=StoryEventType.TRANSFER,
            first_seen_at=NOW.replace(tzinfo=None),
            confidence_score=Decimal("0.5"),
        )
    with pytest.raises(ValueError, match="before"):
        story.observe(at=NOW - timedelta(seconds=1), confidence_score=Decimal("0.5"))


def test_source_and_entity_links_enforce_database_contract() -> None:
    source = StorySource.create(
        link_id=SOURCE_LINK_ID,
        story_id=STORY_ID,
        article_version_id=ARTICLE_ID,
        source_id=SOURCE_ID,
        source_reliability_tier=1,
        published_at=NOW - timedelta(hours=1),
        observed_at=NOW,
    )
    entity = StoryEntity.create(
        link_id=UUID(int=9),
        story_id=STORY_ID,
        entity_id=PLAYER_ID,
        entity_type=EntityType.PLAYER,
        now=NOW,
    )

    assert source.source_reliability_tier == 1
    assert source.source_cluster_id is None
    assert entity.entity_type is EntityType.PLAYER
    with pytest.raises(ValueError, match="reliability"):
        StorySource.create(
            link_id=UUID(int=10),
            story_id=STORY_ID,
            article_version_id=ARTICLE_ID,
            source_id=SOURCE_ID,
            source_reliability_tier=0,
            published_at=NOW,
            observed_at=NOW,
        )

    clustered = StorySource.create(
        link_id=UUID(int=14),
        story_id=STORY_ID,
        article_version_id=ARTICLE_ID,
        source_id=SOURCE_ID,
        source_cluster_id=UUID(int=15),
        source_reliability_tier=1,
        published_at=NOW,
        observed_at=NOW,
    )
    assert clustered.source_cluster_id == UUID(int=15)


def test_claim_fingerprint_is_deterministic_for_equivalent_object_values() -> None:
    first = Claim.create(
        claim_id=CLAIM_ID,
        story_id=STORY_ID,
        subject_entity_id=PLAYER_ID,
        predicate=ClaimPredicate.SUBMITTED_BID,
        object_entity_id=CLUB_ID,
        object_value={"currency": "EUR", "amount": 180_000_000},
        statement_en="Arsenal submitted a €180m bid.",
        certainty=Decimal("0.7000"),
        occurred_at=NOW,
        occurred_at_bucket=NOW,
        now=NOW,
    )
    second = Claim.create(
        claim_id=UUID(int=11),
        story_id=STORY_ID,
        subject_entity_id=PLAYER_ID,
        predicate=ClaimPredicate.SUBMITTED_BID,
        object_entity_id=CLUB_ID,
        object_value={"amount": 180_000_000, "currency": "EUR"},
        statement_en="A bid worth €180m was submitted by Arsenal.",
        certainty=Decimal("0.9000"),
        occurred_at=NOW,
        occurred_at_bucket=NOW,
        now=NOW,
    )

    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64


def test_claim_confirmation_defaults_to_rumour_and_can_be_set() -> None:
    arguments = {
        "claim_id": CLAIM_ID,
        "story_id": STORY_ID,
        "subject_entity_id": PLAYER_ID,
        "predicate": ClaimPredicate.SUBMITTED_BID,
        "object_entity_id": CLUB_ID,
        "object_value": {"amount": 180_000_000},
        "statement_en": "Arsenal submitted a bid.",
        "certainty": Decimal("0.7"),
        "occurred_at": NOW,
        "occurred_at_bucket": NOW,
        "now": NOW,
    }

    assert Claim.create(**arguments).confirmation is ClaimConfirmation.RUMOUR
    assert (
        Claim.create(**arguments, confirmation=ClaimConfirmation.MULTI_SOURCE).confirmation
        is ClaimConfirmation.MULTI_SOURCE
    )


def test_claim_can_transition_confirmation_without_changing_fingerprint() -> None:
    claim = Claim.create(
        claim_id=CLAIM_ID,
        story_id=STORY_ID,
        subject_entity_id=PLAYER_ID,
        predicate=ClaimPredicate.SUBMITTED_BID,
        object_entity_id=CLUB_ID,
        object_value={"amount": 180_000_000},
        statement_en="Arsenal submitted a bid.",
        certainty=Decimal("0.7"),
        occurred_at=NOW,
        occurred_at_bucket=NOW,
        now=NOW,
    )

    updated = claim.with_confirmation(ClaimConfirmation.MULTI_SOURCE)

    assert updated.confirmation is ClaimConfirmation.MULTI_SOURCE
    assert updated.fingerprint == claim.fingerprint
    assert updated.created_at == claim.created_at


def test_claim_requires_grounded_object_statement_and_valid_certainty() -> None:
    arguments = {
        "claim_id": CLAIM_ID,
        "story_id": STORY_ID,
        "subject_entity_id": PLAYER_ID,
        "predicate": ClaimPredicate.SUBMITTED_BID,
        "object_entity_id": None,
        "object_value": None,
        "statement_en": "Arsenal submitted a bid.",
        "certainty": Decimal("0.7"),
        "occurred_at": NOW,
        "occurred_at_bucket": NOW,
        "now": NOW,
    }
    with pytest.raises(ValueError, match="object"):
        Claim.create(**arguments)
    with pytest.raises(ValueError, match="statement"):
        Claim.create(**{**arguments, "object_value": {"amount": 1}, "statement_en": " "})
    with pytest.raises(ValueError, match="certainty"):
        Claim.create(**{**arguments, "object_value": {"amount": 1}, "certainty": Decimal("2")})


def test_claim_evidence_requires_non_empty_quote_and_half_open_range() -> None:
    evidence = ClaimEvidence.create(
        evidence_id=UUID(int=12),
        claim_id=CLAIM_ID,
        story_source_id=SOURCE_LINK_ID,
        quote="submitted a €180m bid",
        start=8,
        end=30,
        now=NOW,
    )

    assert evidence.start == 8
    assert evidence.end == 30
    with pytest.raises(ValueError, match="range"):
        ClaimEvidence.create(
            evidence_id=UUID(int=13),
            claim_id=CLAIM_ID,
            story_source_id=SOURCE_LINK_ID,
            quote="invalid",
            start=8,
            end=8,
            now=NOW,
        )

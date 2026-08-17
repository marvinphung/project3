from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_intelligence_service.domain.embedding import (
    EMBEDDING_DIMENSIONS,
    EmbeddingVector,
)
from footballpulse_intelligence_service.domain.story import ClaimPredicate, StoryEventType
from footballpulse_intelligence_service.domain.story_embedding import (
    StoryEmbeddingClaim,
    StoryEmbeddingInput,
    StoryEmbeddingRecord,
    build_story_embedding_text,
)

STORY_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb001")
ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def bid_claim(*, amount: int = 180_000_000) -> StoryEmbeddingClaim:
    return StoryEmbeddingClaim(
        subject_entity_id=ARSENAL_ID,
        subject_name="Arsenal",
        predicate=ClaimPredicate.SUBMITTED_BID,
        object_entity_id=PLAYER_ID,
        object_name="Vinícius Júnior",
        object_value={"currency": "EUR", "amount": amount},
    )


def test_story_embedding_input_is_canonical_and_order_independent() -> None:
    first = StoryEmbeddingInput(
        story_id=STORY_ID,
        story_version=2,
        event_type=StoryEventType.TRANSFER,
        canonical_entities=("Vinícius Júnior", "Arsenal", "arsenal", "Real Madrid"),
        claims=(bid_claim(),),
    )
    second = StoryEmbeddingInput(
        story_id=STORY_ID,
        story_version=2,
        event_type=StoryEventType.TRANSFER,
        canonical_entities=("Real Madrid", "Arsenal", "Vinícius Júnior"),
        claims=(bid_claim(),),
    )

    built_first = build_story_embedding_text(first)
    built_second = build_story_embedding_text(second)

    assert built_first == built_second
    assert built_first.text == (
        "event_type: TRANSFER\n"
        "entities: Arsenal | Real Madrid | Vinícius Júnior\n"
        "claims:\n"
        "Arsenal SUBMITTED_BID Vinícius Júnior "
        '{"amount":180000000,"currency":"EUR"}'
    )


def test_story_embedding_hash_changes_with_story_version_or_material_claim() -> None:
    baseline = StoryEmbeddingInput(
        STORY_ID,
        2,
        StoryEventType.TRANSFER,
        ("Arsenal", "Vinícius Júnior"),
        (bid_claim(),),
    )
    next_version = StoryEmbeddingInput(
        STORY_ID,
        3,
        StoryEventType.TRANSFER,
        baseline.canonical_entities,
        baseline.claims,
    )
    changed_claim = StoryEmbeddingInput(
        STORY_ID,
        2,
        StoryEventType.TRANSFER,
        baseline.canonical_entities,
        (bid_claim(amount=150_000_000),),
    )

    assert (
        build_story_embedding_text(baseline).input_hash
        != build_story_embedding_text(next_version).input_hash
    )
    assert (
        build_story_embedding_text(baseline).input_hash
        != build_story_embedding_text(changed_claim).input_hash
    )


def test_story_embedding_record_binds_vector_to_story_version_and_model() -> None:
    built = build_story_embedding_text(
        StoryEmbeddingInput(
            STORY_ID,
            2,
            StoryEventType.TRANSFER,
            ("Arsenal", "Vinícius Júnior"),
            (bid_claim(),),
        )
    )
    vector = EmbeddingVector.create([1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1))

    record = StoryEmbeddingRecord.create(
        story_id=STORY_ID,
        story_version=2,
        input_hash=built.input_hash,
        input_builder_version="story-embedding-input-v1",
        model_name="BAAI/bge-small-en-v1.5",
        model_version="pinned-revision",
        vector=vector,
        token_count=40,
        now=NOW,
    )

    assert record.story_id == STORY_ID
    assert record.story_version == 2
    assert record.dimensions == 384

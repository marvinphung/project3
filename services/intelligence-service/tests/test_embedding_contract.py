from __future__ import annotations

import math
from uuid import UUID

from footballpulse_intelligence_service.domain.embedding import (
    EMBEDDING_DIMENSIONS,
    EmbeddingInput,
    EmbeddingVector,
    build_embedding_text,
)

ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3ca101")


def test_input_builder_is_english_deterministic_and_entity_order_independent() -> None:
    first = EmbeddingInput(
        article_version_id=ARTICLE_ID,
        title="  Arsenal   submit an offer  ",
        canonical_entities=("Vinícius Júnior", "Arsenal", "arsenal", "Real Madrid"),
        cleaned_content=" Arsenal have submitted a bid.\nReal Madrid are considering it. ",
    )
    second = EmbeddingInput(
        article_version_id=ARTICLE_ID,
        title="Arsenal submit an offer",
        canonical_entities=("Real Madrid", "Arsenal", "Vinícius Júnior"),
        cleaned_content="Arsenal have submitted a bid. Real Madrid are considering it.",
    )

    built_first = build_embedding_text(first)
    built_second = build_embedding_text(second)

    assert built_first == built_second
    assert built_first.text == (
        "title: Arsenal submit an offer\n"
        "entities: Arsenal | Real Madrid | Vinícius Júnior\n"
        "content: Arsenal have submitted a bid. Real Madrid are considering it."
    )
    assert len(built_first.input_hash) == 64


def test_input_builder_rejects_missing_evidence_and_unbounded_content() -> None:
    try:
        build_embedding_text(EmbeddingInput(ARTICLE_ID, "", (), ""))
    except ValueError as error:
        assert "title" in str(error)
    else:
        raise AssertionError("embedding input requires a title")

    try:
        build_embedding_text(EmbeddingInput(ARTICLE_ID, "Title", (), "x" * 500_001))
    except ValueError as error:
        assert "length" in str(error)
    else:
        raise AssertionError("embedding content must be bounded")


def test_embedding_vector_requires_finite_normalized_384_dimensions() -> None:
    normalized = 1 / math.sqrt(EMBEDDING_DIMENSIONS)
    vector = EmbeddingVector.create([normalized] * EMBEDDING_DIMENSIONS)
    assert len(vector.values) == EMBEDDING_DIMENSIONS

    for invalid in (
        [0.0] * (EMBEDDING_DIMENSIONS - 1),
        [0.0] * EMBEDDING_DIMENSIONS,
        [math.nan] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
    ):
        try:
            EmbeddingVector.create(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid embedding vector must be rejected")

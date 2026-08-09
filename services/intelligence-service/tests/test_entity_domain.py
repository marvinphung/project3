from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_intelligence_service.domain.entity import (
    AliasReviewStatus,
    Entity,
    EntityAlias,
    EntityStatus,
    EntityType,
    normalize_alias,
)

NOW = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
ENTITY_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")
ALIAS_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8201")


def test_normalizes_diacritics_punctuation_case_and_whitespace() -> None:
    assert normalize_alias("  VINÍCIUS---Júnior  ") == "vinicius junior"
    assert normalize_alias("Vini Jr.") == "vini jr"


def test_creates_active_entity_with_stable_identity_and_slug() -> None:
    entity = Entity.create(
        entity_id=ENTITY_ID,
        entity_type=EntityType.PLAYER,
        canonical_name="  Vinícius Júnior  ",
        slug="vinicius-junior",
        now=NOW,
    )

    assert entity.id == ENTITY_ID
    assert entity.canonical_name == "Vinícius Júnior"
    assert entity.status is EntityStatus.ACTIVE
    assert entity.created_at == entity.updated_at == NOW


@pytest.mark.parametrize("slug", ["Vinicius-Junior", "vinicius junior", "vinícius"])
def test_rejects_unstable_or_non_ascii_slug(slug: str) -> None:
    with pytest.raises(ValueError, match="slug"):
        Entity.create(
            entity_id=ENTITY_ID,
            entity_type=EntityType.PLAYER,
            canonical_name="Vinícius Júnior",
            slug=slug,
            now=NOW,
        )


def test_seed_alias_is_approved_and_pipeline_alias_requires_review() -> None:
    approved = EntityAlias.create(
        alias_id=ALIAS_ID,
        entity_id=ENTITY_ID,
        alias="Vinicius Junior",
        review_status=AliasReviewStatus.APPROVED,
        resolver_version="seed-v1",
        source="SEED",
        actor="system:seed",
        now=NOW,
    )
    pending = EntityAlias.create(
        alias_id=ALIAS_ID,
        entity_id=ENTITY_ID,
        alias="Vini Jr",
        review_status=AliasReviewStatus.PENDING_REVIEW,
        resolver_version="resolver-v1",
        source="PIPELINE",
        actor="service:intelligence",
        now=NOW,
    )

    assert approved.normalized_alias == "vinicius junior"
    assert pending.normalized_alias == "vini jr"
    assert approved.is_resolvable is True
    assert pending.is_resolvable is False


def test_pipeline_cannot_create_an_approved_alias() -> None:
    with pytest.raises(ValueError, match="pipeline"):
        EntityAlias.create(
            alias_id=ALIAS_ID,
            entity_id=ENTITY_ID,
            alias="Unreviewed nickname",
            review_status=AliasReviewStatus.APPROVED,
            resolver_version="resolver-v1",
            source="PIPELINE",
            actor="service:intelligence",
            now=NOW,
        )


def test_rejects_values_that_exceed_postgres_contract_lengths() -> None:
    with pytest.raises(ValueError, match="canonical_name"):
        Entity.create(
            entity_id=ENTITY_ID,
            entity_type=EntityType.PLAYER,
            canonical_name="x" * 201,
            slug="valid-slug",
            now=NOW,
        )
    with pytest.raises(ValueError, match="alias"):
        EntityAlias.create(
            alias_id=ALIAS_ID,
            entity_id=ENTITY_ID,
            alias="x" * 201,
            review_status=AliasReviewStatus.PENDING_REVIEW,
            resolver_version="resolver-v1",
            source="PIPELINE",
            actor="service:intelligence",
            now=NOW,
        )

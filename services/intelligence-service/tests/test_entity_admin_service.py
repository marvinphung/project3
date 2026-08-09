from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from footballpulse_intelligence_service.application.entity_catalog import (
    AliasDecision,
    EntityCatalogService,
)
from footballpulse_intelligence_service.domain.entity import (
    AliasReviewStatus,
    Entity,
    EntityAlias,
    EntityAuditRecord,
    EntityType,
    normalize_alias,
)
from footballpulse_intelligence_service.domain.errors import EntityConflictError

NOW = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)


class InMemoryEntityCatalog:
    def __init__(self) -> None:
        self.entities: dict[UUID, Entity] = {}
        self.aliases: dict[UUID, EntityAlias] = {}
        self.audit: list[EntityAuditRecord] = []

    def create_entity(
        self,
        entity: Entity,
        canonical_alias: EntityAlias,
        audit: EntityAuditRecord,
    ) -> Entity:
        if any(existing.slug == entity.slug for existing in self.entities.values()):
            raise EntityConflictError("entity slug already exists")
        self._assert_alias_available(canonical_alias)
        self.entities[entity.id] = entity
        self.aliases[canonical_alias.id] = canonical_alias
        self.audit.append(audit)
        return entity

    def get_entity(self, entity_id: UUID) -> Entity | None:
        return self.entities.get(entity_id)

    def find_entity_by_slug(self, slug: str) -> Entity | None:
        return next((entity for entity in self.entities.values() if entity.slug == slug), None)

    def save_entity(
        self,
        entity: Entity,
        *,
        expected_version: int,
        audit: EntityAuditRecord,
    ) -> Entity:
        if self.entities[entity.id].version != expected_version:
            raise EntityConflictError("entity version conflict")
        self.entities[entity.id] = entity
        self.audit.append(audit)
        return entity

    def rename_entity(
        self,
        entity: Entity,
        canonical_alias: EntityAlias,
        *,
        expected_version: int,
        audit: EntityAuditRecord,
    ) -> Entity:
        self._assert_alias_available(canonical_alias)
        saved = self.save_entity(entity, expected_version=expected_version, audit=audit)
        self.aliases[canonical_alias.id] = canonical_alias
        return saved

    def add_alias(self, alias: EntityAlias, audit: EntityAuditRecord) -> EntityAlias:
        self._assert_alias_available(alias)
        self.aliases[alias.id] = alias
        self.audit.append(audit)
        return alias

    def get_alias(self, alias_id: UUID) -> EntityAlias | None:
        return self.aliases.get(alias_id)

    def save_alias(
        self,
        alias: EntityAlias,
        *,
        expected_version: int,
        audit: EntityAuditRecord,
    ) -> EntityAlias:
        if self.aliases[alias.id].version != expected_version:
            raise EntityConflictError("alias version conflict")
        self._assert_alias_available(alias, exclude_id=alias.id)
        self.aliases[alias.id] = alias
        self.audit.append(audit)
        return alias

    def resolve_alias(self, normalized_alias: str) -> Entity | None:
        alias = next(
            (
                candidate
                for candidate in self.aliases.values()
                if candidate.normalized_alias == normalized_alias and candidate.is_resolvable
            ),
            None,
        )
        if alias is None:
            return None
        entity = self.entities[alias.entity_id]
        return entity if entity.is_active else None

    def list_pending_aliases(self, *, limit: int, offset: int) -> list[EntityAlias]:
        pending = sorted(
            (
                alias
                for alias in self.aliases.values()
                if alias.review_status is AliasReviewStatus.PENDING_REVIEW
            ),
            key=lambda alias: (alias.created_at, alias.id),
        )
        return pending[offset : offset + limit]

    def _assert_alias_available(
        self,
        alias: EntityAlias,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        if not alias.is_resolvable:
            return
        if any(
            existing.id != exclude_id
            and existing.normalized_alias == alias.normalized_alias
            and existing.is_resolvable
            for existing in self.aliases.values()
        ):
            raise EntityConflictError("approved normalized alias already exists")


def _service(repository: InMemoryEntityCatalog) -> EntityCatalogService:
    return EntityCatalogService(repository, clock=lambda: NOW, id_factory=uuid4)


def test_create_entity_also_creates_resolvable_canonical_alias_and_audit() -> None:
    repository = InMemoryEntityCatalog()
    service = _service(repository)

    entity = service.create_entity(
        entity_type=EntityType.PLAYER,
        canonical_name="Vinícius Júnior",
        slug="vinicius-junior",
        actor="admin:vũ",
        reason="Seed trusted player",
    )

    assert service.resolve("VINICIUS Junior") == entity
    assert repository.audit[-1].action == "CREATE_ENTITY"
    assert repository.audit[-1].actor == "admin:vũ"
    assert repository.audit[-1].reason == "Seed trusted player"


def test_rename_keeps_slug_stable_and_uses_optimistic_version() -> None:
    repository = InMemoryEntityCatalog()
    service = _service(repository)
    entity = service.create_entity(
        entity_type=EntityType.COACH,
        canonical_name="Xabi Alonso",
        slug="xabi-alonso",
        actor="admin:1",
        reason="Initial catalog",
    )

    renamed = service.rename_entity(
        entity.id,
        canonical_name="Xabier Alonso",
        expected_version=1,
        actor="admin:1",
        reason="Use full legal name",
    )

    assert renamed.canonical_name == "Xabier Alonso"
    assert renamed.slug == "xabi-alonso"
    assert renamed.version == 2
    assert service.resolve("Xabier Alonso") == renamed

    restored = service.rename_entity(
        entity.id,
        canonical_name="Xabi Alonso",
        expected_version=2,
        actor="admin:1",
        reason="Restore prior catalog name",
    )
    assert restored.canonical_name == "Xabi Alonso"
    assert restored.version == 3
    assert service.resolve("Xabi Alonso") == restored


def test_pipeline_alias_is_unresolved_until_admin_approves_it() -> None:
    repository = InMemoryEntityCatalog()
    service = _service(repository)
    entity = service.create_entity(
        entity_type=EntityType.PLAYER,
        canonical_name="Vinícius Júnior",
        slug="vinicius-junior",
        actor="admin:1",
        reason="Initial catalog",
    )
    pending = service.propose_pipeline_alias(
        entity.id,
        alias="Vini Jr",
        resolver_version="resolver-v1",
        actor="service:intelligence",
        reason="Mention extracted from article",
    )

    assert service.resolve("Vini Jr") is None
    assert service.list_pending_aliases() == [pending]

    approved = service.review_alias(
        pending.id,
        decision=AliasDecision.APPROVE,
        expected_version=1,
        actor="admin:1",
        reason="Known player nickname",
    )

    assert approved.review_status is AliasReviewStatus.APPROVED
    assert approved.version == 2
    assert service.resolve("vini jr") == entity


def test_cannot_approve_alias_already_owned_by_an_active_entity() -> None:
    repository = InMemoryEntityCatalog()
    service = _service(repository)
    first = service.create_entity(
        entity_type=EntityType.CLUB,
        canonical_name="Arsenal",
        slug="arsenal",
        actor="admin:1",
        reason="Initial catalog",
    )
    second = service.create_entity(
        entity_type=EntityType.CLUB,
        canonical_name="Arsenal Women",
        slug="arsenal-women",
        actor="admin:1",
        reason="Initial catalog",
    )
    assert normalize_alias(first.canonical_name) == "arsenal"
    pending = service.propose_pipeline_alias(
        second.id,
        alias="Arsenal",
        resolver_version="resolver-v1",
        actor="service:intelligence",
        reason="Ambiguous mention",
    )

    with pytest.raises(EntityConflictError, match="already exists"):
        service.review_alias(
            pending.id,
            decision=AliasDecision.APPROVE,
            expected_version=1,
            actor="admin:1",
            reason="Incorrect approval attempt",
        )


def test_explicit_slug_change_and_disable_operations_are_audited() -> None:
    repository = InMemoryEntityCatalog()
    service = _service(repository)
    entity = service.create_entity(
        entity_type=EntityType.CLUB,
        canonical_name="Athletic Club",
        slug="athletic-club",
        actor="admin:1",
        reason="Initial catalog",
    )
    alias = service.add_approved_alias(
        entity.id,
        alias="Athletic Bilbao",
        resolver_version="catalog-v1",
        actor="admin:1",
        reason="Known historical name",
    )

    changed = service.change_slug(
        entity.id,
        slug="athletic-club-bilbao",
        expected_version=1,
        actor="admin:1",
        reason="Explicit public URL change",
    )
    service.disable_alias(
        alias.id,
        expected_version=1,
        actor="admin:1",
        reason="Retire ambiguous alias",
    )

    assert changed.slug == "athletic-club-bilbao"
    assert service.find_by_slug("athletic-club-bilbao") == changed
    assert service.resolve("Athletic Bilbao") is None

    disabled = service.disable_entity(
        entity.id,
        expected_version=2,
        actor="admin:1",
        reason="Entity no longer selectable",
    )
    assert disabled.is_active is False
    assert service.resolve("Athletic Club") is None
    assert {record.action for record in repository.audit} >= {
        "CHANGE_ENTITY_SLUG",
        "DISABLE_ALIAS",
        "DISABLE_ENTITY",
    }

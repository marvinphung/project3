from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from footballpulse_intelligence_service.application.ports import EntityCatalogRepository
from footballpulse_intelligence_service.domain.entity import (
    AliasReviewStatus,
    AliasSource,
    Entity,
    EntityAlias,
    EntityAuditRecord,
    EntityType,
    normalize_alias,
)
from footballpulse_intelligence_service.domain.errors import (
    AliasNotFoundError,
    EntityConflictError,
    EntityNotFoundError,
)


class AliasDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class EntityCatalogService:
    def __init__(
        self,
        repository: EntityCatalogRepository,
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._id_factory = id_factory

    def create_entity(
        self,
        *,
        entity_type: EntityType,
        canonical_name: str,
        slug: str,
        actor: str,
        reason: str,
    ) -> Entity:
        now = self._clock()
        entity = Entity.create(
            entity_id=self._id_factory(),
            entity_type=entity_type,
            canonical_name=canonical_name,
            slug=slug,
            now=now,
        )
        canonical_alias = EntityAlias.create(
            alias_id=self._id_factory(),
            entity_id=entity.id,
            alias=entity.canonical_name,
            review_status=AliasReviewStatus.APPROVED,
            resolver_version="catalog-v1",
            source=AliasSource.ADMIN,
            actor=actor,
            now=now,
        )
        audit = self._audit(
            "ENTITY",
            entity.id,
            "CREATE_ENTITY",
            actor,
            reason,
            {"entity_type": entity.entity_type.value, "slug": entity.slug},
            now,
        )
        return self._repository.create_entity(entity, canonical_alias, audit)

    def rename_entity(
        self,
        entity_id: UUID,
        *,
        canonical_name: str,
        expected_version: int,
        actor: str,
        reason: str,
    ) -> Entity:
        entity = self._entity(entity_id)
        self._check_version(entity.version, expected_version, "entity")
        now = self._clock()
        renamed = entity.rename(canonical_name, now=now)
        if renamed.canonical_name == entity.canonical_name:
            return entity
        existing_owner = self._repository.resolve_alias(normalize_alias(renamed.canonical_name))
        audit = self._audit(
            "ENTITY",
            entity.id,
            "RENAME_ENTITY",
            actor,
            reason,
            {"from": entity.canonical_name, "to": renamed.canonical_name},
            now,
        )
        if existing_owner is not None:
            if existing_owner.id != entity.id:
                raise EntityConflictError("canonical name alias belongs to another entity")
            return self._repository.save_entity(
                renamed,
                expected_version=expected_version,
                audit=audit,
            )
        canonical_alias = EntityAlias.create(
            alias_id=self._id_factory(),
            entity_id=entity.id,
            alias=renamed.canonical_name,
            review_status=AliasReviewStatus.APPROVED,
            resolver_version="catalog-v1",
            source=AliasSource.ADMIN,
            actor=actor,
            now=now,
        )
        return self._repository.rename_entity(
            renamed,
            canonical_alias,
            expected_version=expected_version,
            audit=audit,
        )

    def change_slug(
        self,
        entity_id: UUID,
        *,
        slug: str,
        expected_version: int,
        actor: str,
        reason: str,
    ) -> Entity:
        entity = self._entity(entity_id)
        self._check_version(entity.version, expected_version, "entity")
        now = self._clock()
        changed = entity.change_slug(slug, now=now)
        return self._repository.save_entity(
            changed,
            expected_version=expected_version,
            audit=self._audit(
                "ENTITY",
                entity.id,
                "CHANGE_ENTITY_SLUG",
                actor,
                reason,
                {"from": entity.slug, "to": changed.slug},
                now,
            ),
        )

    def disable_entity(
        self,
        entity_id: UUID,
        *,
        expected_version: int,
        actor: str,
        reason: str,
    ) -> Entity:
        entity = self._entity(entity_id)
        self._check_version(entity.version, expected_version, "entity")
        disabled = entity.disable(now=self._clock())
        if disabled is entity:
            return entity
        return self._repository.save_entity(
            disabled,
            expected_version=expected_version,
            audit=self._audit(
                "ENTITY",
                entity.id,
                "DISABLE_ENTITY",
                actor,
                reason,
                {},
                disabled.updated_at,
            ),
        )

    def add_approved_alias(
        self,
        entity_id: UUID,
        *,
        alias: str,
        resolver_version: str,
        actor: str,
        reason: str,
    ) -> EntityAlias:
        self._entity(entity_id)
        now = self._clock()
        approved = EntityAlias.create(
            alias_id=self._id_factory(),
            entity_id=entity_id,
            alias=alias,
            review_status=AliasReviewStatus.APPROVED,
            resolver_version=resolver_version,
            source=AliasSource.ADMIN,
            actor=actor,
            now=now,
        )
        return self._repository.add_alias(
            approved,
            self._audit(
                "ALIAS",
                approved.id,
                "ADD_APPROVED_ALIAS",
                actor,
                reason,
                {"entity_id": str(entity_id), "alias": approved.alias},
                now,
            ),
        )

    def propose_pipeline_alias(
        self,
        entity_id: UUID,
        *,
        alias: str,
        resolver_version: str,
        actor: str,
        reason: str,
    ) -> EntityAlias:
        self._entity(entity_id)
        now = self._clock()
        candidate = EntityAlias.create(
            alias_id=self._id_factory(),
            entity_id=entity_id,
            alias=alias,
            review_status=AliasReviewStatus.PENDING_REVIEW,
            resolver_version=resolver_version,
            source=AliasSource.PIPELINE,
            actor=actor,
            now=now,
        )
        return self._repository.add_alias(
            candidate,
            self._audit(
                "ALIAS",
                candidate.id,
                "PROPOSE_ALIAS",
                actor,
                reason,
                {"entity_id": str(entity_id), "alias": candidate.alias},
                now,
            ),
        )

    def review_alias(
        self,
        alias_id: UUID,
        *,
        decision: AliasDecision,
        expected_version: int,
        actor: str,
        reason: str,
    ) -> EntityAlias:
        alias = self._alias(alias_id)
        self._check_version(alias.version, expected_version, "alias")
        now = self._clock()
        status = (
            AliasReviewStatus.APPROVED
            if AliasDecision(decision) is AliasDecision.APPROVE
            else AliasReviewStatus.REJECTED
        )
        reviewed = alias.review(status, actor=actor, now=now)
        return self._repository.save_alias(
            reviewed,
            expected_version=expected_version,
            audit=self._audit(
                "ALIAS",
                alias.id,
                f"{decision.value}_ALIAS",
                actor,
                reason,
                {"normalized_alias": alias.normalized_alias},
                now,
            ),
        )

    def resolve(self, alias: str) -> Entity | None:
        normalized = normalize_alias(alias)
        if not normalized:
            return None
        return self._repository.resolve_alias(normalized)

    def get_entity(self, entity_id: UUID) -> Entity:
        return self._entity(entity_id)

    def find_by_slug(self, slug: str) -> Entity | None:
        return self._repository.find_entity_by_slug(slug)

    def disable_alias(
        self,
        alias_id: UUID,
        *,
        expected_version: int,
        actor: str,
        reason: str,
    ) -> EntityAlias:
        alias = self._alias(alias_id)
        self._check_version(alias.version, expected_version, "alias")
        disabled = alias.disable(now=self._clock())
        if disabled is alias:
            return alias
        return self._repository.save_alias(
            disabled,
            expected_version=expected_version,
            audit=self._audit(
                "ALIAS",
                alias.id,
                "DISABLE_ALIAS",
                actor,
                reason,
                {"normalized_alias": alias.normalized_alias},
                disabled.updated_at,
            ),
        )

    def list_pending_aliases(self, *, limit: int = 100, offset: int = 0) -> list[EntityAlias]:
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError("alias pagination is outside allowed bounds")
        return self._repository.list_pending_aliases(limit=limit, offset=offset)

    def _entity(self, entity_id: UUID) -> Entity:
        entity = self._repository.get_entity(entity_id)
        if entity is None:
            raise EntityNotFoundError(f"entity {entity_id} was not found")
        return entity

    def _alias(self, alias_id: UUID) -> EntityAlias:
        alias = self._repository.get_alias(alias_id)
        if alias is None:
            raise AliasNotFoundError(f"alias {alias_id} was not found")
        return alias

    @staticmethod
    def _check_version(current: int, expected: int, resource: str) -> None:
        if current != expected:
            raise EntityConflictError(
                f"{resource} version conflict: expected {expected}, current {current}"
            )

    def _audit(
        self,
        resource_type: str,
        resource_id: UUID,
        action: str,
        actor: str,
        reason: str,
        details: dict[str, object],
        now: datetime,
    ) -> EntityAuditRecord:
        return EntityAuditRecord.create(
            audit_id=self._id_factory(),
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            actor=actor,
            reason=reason,
            details=details,
            now=now,
        )

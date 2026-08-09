from __future__ import annotations

from typing import Protocol
from uuid import UUID

from footballpulse_intelligence_service.domain.entity import (
    Entity,
    EntityAlias,
    EntityAuditRecord,
)


class EntityCatalogRepository(Protocol):
    def create_entity(
        self,
        entity: Entity,
        canonical_alias: EntityAlias,
        audit: EntityAuditRecord,
    ) -> Entity: ...

    def get_entity(self, entity_id: UUID) -> Entity | None: ...

    def find_entity_by_slug(self, slug: str) -> Entity | None: ...

    def save_entity(
        self,
        entity: Entity,
        *,
        expected_version: int,
        audit: EntityAuditRecord,
    ) -> Entity: ...

    def rename_entity(
        self,
        entity: Entity,
        canonical_alias: EntityAlias,
        *,
        expected_version: int,
        audit: EntityAuditRecord,
    ) -> Entity: ...

    def add_alias(self, alias: EntityAlias, audit: EntityAuditRecord) -> EntityAlias: ...

    def get_alias(self, alias_id: UUID) -> EntityAlias | None: ...

    def save_alias(
        self,
        alias: EntityAlias,
        *,
        expected_version: int,
        audit: EntityAuditRecord,
    ) -> EntityAlias: ...

    def resolve_alias(self, normalized_alias: str) -> Entity | None: ...

    def list_pending_aliases(self, *, limit: int, offset: int) -> list[EntityAlias]: ...

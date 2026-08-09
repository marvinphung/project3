from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from footballpulse_intelligence_service.domain.embedding import (
    EmbeddingRecord,
    EmbeddingVector,
)
from footballpulse_intelligence_service.domain.entity import (
    AliasReviewStatus,
    AliasSource,
    Entity,
    EntityAlias,
    EntityAuditRecord,
    EntityStatus,
    EntityType,
)
from footballpulse_intelligence_service.domain.errors import EntityConflictError
from footballpulse_intelligence_service.domain.extraction import SourceField
from footballpulse_intelligence_service.domain.unresolved import (
    UnresolvedEntityMention,
    UnresolvedReviewStatus,
)
from footballpulse_intelligence_service.persistence.postgres_tables import (
    article_embeddings,
    entities,
    entity_aliases,
    entity_audit_log,
    unresolved_entity_mentions,
)


def _entity_values(entity: Entity) -> dict[str, object]:
    return {
        "id": entity.id,
        "entity_type": entity.entity_type.value,
        "canonical_name": entity.canonical_name,
        "slug": entity.slug,
        "status": entity.status.value,
        "version": entity.version,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


def _entity_from_row(row: RowMapping) -> Entity:
    return Entity(
        id=row["id"],
        entity_type=EntityType(row["entity_type"]),
        canonical_name=row["canonical_name"],
        slug=row["slug"],
        status=EntityStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=row["version"],
    )


def _alias_values(alias: EntityAlias) -> dict[str, object]:
    return {
        "id": alias.id,
        "entity_id": alias.entity_id,
        "alias": alias.alias,
        "normalized_alias": alias.normalized_alias,
        "review_status": alias.review_status.value,
        "resolver_version": alias.resolver_version,
        "source": alias.source.value,
        "created_by": alias.actor,
        "reviewed_by": alias.reviewed_by,
        "reviewed_at": alias.reviewed_at,
        "disabled_at": alias.disabled_at,
        "version": alias.version,
        "created_at": alias.created_at,
        "updated_at": alias.updated_at,
    }


def _alias_from_row(row: RowMapping) -> EntityAlias:
    return EntityAlias(
        id=row["id"],
        entity_id=row["entity_id"],
        alias=row["alias"],
        normalized_alias=row["normalized_alias"],
        review_status=AliasReviewStatus(row["review_status"]),
        resolver_version=row["resolver_version"],
        source=AliasSource(row["source"]),
        actor=row["created_by"],
        created_at=row["created_at"],
        reviewed_at=row["reviewed_at"],
        reviewed_by=row["reviewed_by"],
        disabled_at=row["disabled_at"],
        updated_at=row["updated_at"],
        version=row["version"],
    )


def _audit_values(audit: EntityAuditRecord) -> dict[str, object]:
    return {
        "id": audit.id,
        "resource_type": audit.resource_type,
        "resource_id": audit.resource_id,
        "action": audit.action,
        "actor": audit.actor,
        "reason": audit.reason,
        "details": audit.details,
        "occurred_at": audit.occurred_at,
    }


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    value = getattr(diagnostic, "constraint_name", None)
    return value if isinstance(value, str) else None


def _raise_conflict(error: IntegrityError) -> None:
    constraint = _constraint_name(error)
    if constraint == "uq_entity_aliases_resolvable_normalized":
        raise EntityConflictError("approved normalized alias already exists") from error
    if constraint == "uq_entities_slug":
        raise EntityConflictError("entity slug already exists") from error
    raise EntityConflictError("entity catalog write conflicts with existing data") from error


class PostgresEntityCatalogRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_entity(
        self,
        entity: Entity,
        canonical_alias: EntityAlias,
        audit: EntityAuditRecord,
    ) -> Entity:
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        entities.insert().values(**_entity_values(entity)).returning(*entities.c)
                    )
                    .mappings()
                    .one()
                )
                connection.execute(entity_aliases.insert().values(**_alias_values(canonical_alias)))
                self._insert_audit(connection, audit)
        except IntegrityError as error:
            _raise_conflict(error)
        assert row is not None
        return _entity_from_row(row)

    def get_entity(self, entity_id: UUID) -> Entity | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(sa.select(entities).where(entities.c.id == entity_id))
                .mappings()
                .one_or_none()
            )
        return None if row is None else _entity_from_row(row)

    def find_entity_by_slug(self, slug: str) -> Entity | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(sa.select(entities).where(entities.c.slug == slug))
                .mappings()
                .one_or_none()
            )
        return None if row is None else _entity_from_row(row)

    def save_entity(
        self,
        entity: Entity,
        *,
        expected_version: int,
        audit: EntityAuditRecord,
    ) -> Entity:
        values = _entity_values(entity)
        values.pop("id")
        values.pop("created_at")
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        entities.update()
                        .where(entities.c.id == entity.id, entities.c.version == expected_version)
                        .values(**values)
                        .returning(*entities.c)
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise EntityConflictError("entity version changed before update")
                self._insert_audit(connection, audit)
        except IntegrityError as error:
            _raise_conflict(error)
        assert row is not None
        return _entity_from_row(row)

    def rename_entity(
        self,
        entity: Entity,
        canonical_alias: EntityAlias,
        *,
        expected_version: int,
        audit: EntityAuditRecord,
    ) -> Entity:
        values = _entity_values(entity)
        values.pop("id")
        values.pop("created_at")
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        entities.update()
                        .where(entities.c.id == entity.id, entities.c.version == expected_version)
                        .values(**values)
                        .returning(*entities.c)
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise EntityConflictError("entity version changed before update")
                connection.execute(entity_aliases.insert().values(**_alias_values(canonical_alias)))
                self._insert_audit(connection, audit)
        except IntegrityError as error:
            _raise_conflict(error)
        assert row is not None
        return _entity_from_row(row)

    def add_alias(self, alias: EntityAlias, audit: EntityAuditRecord) -> EntityAlias:
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        entity_aliases.insert()
                        .values(**_alias_values(alias))
                        .returning(*entity_aliases.c)
                    )
                    .mappings()
                    .one()
                )
                self._insert_audit(connection, audit)
        except IntegrityError as error:
            _raise_conflict(error)
        assert row is not None
        return _alias_from_row(row)

    def get_alias(self, alias_id: UUID) -> EntityAlias | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(sa.select(entity_aliases).where(entity_aliases.c.id == alias_id))
                .mappings()
                .one_or_none()
            )
        return None if row is None else _alias_from_row(row)

    def save_alias(
        self,
        alias: EntityAlias,
        *,
        expected_version: int,
        audit: EntityAuditRecord,
    ) -> EntityAlias:
        values = _alias_values(alias)
        for immutable_field in ("id", "entity_id", "created_by", "created_at"):
            values.pop(immutable_field)
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        entity_aliases.update()
                        .where(
                            entity_aliases.c.id == alias.id,
                            entity_aliases.c.version == expected_version,
                        )
                        .values(**values)
                        .returning(*entity_aliases.c)
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise EntityConflictError("alias version changed before update")
                self._insert_audit(connection, audit)
        except IntegrityError as error:
            _raise_conflict(error)
        assert row is not None
        return _alias_from_row(row)

    def resolve_alias(self, normalized_alias: str) -> Entity | None:
        statement = (
            sa.select(entities)
            .join(entity_aliases, entity_aliases.c.entity_id == entities.c.id)
            .where(
                entity_aliases.c.normalized_alias == normalized_alias,
                entity_aliases.c.review_status == AliasReviewStatus.APPROVED.value,
                entity_aliases.c.disabled_at.is_(None),
                entities.c.status == EntityStatus.ACTIVE.value,
            )
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return None if row is None else _entity_from_row(row)

    def list_pending_aliases(self, *, limit: int, offset: int) -> list[EntityAlias]:
        statement = (
            sa.select(entity_aliases)
            .where(entity_aliases.c.review_status == AliasReviewStatus.PENDING_REVIEW.value)
            .order_by(entity_aliases.c.created_at, entity_aliases.c.id)
            .limit(limit)
            .offset(offset)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [_alias_from_row(row) for row in rows]

    @staticmethod
    def _insert_audit(connection: Connection, audit: EntityAuditRecord) -> None:
        connection.execute(entity_audit_log.insert().values(**_audit_values(audit)))


def _unresolved_values(mention: UnresolvedEntityMention) -> dict[str, object]:
    return {
        "id": mention.id,
        "article_version_id": mention.article_version_id,
        "source_field": mention.source_field.value,
        "mention_text": mention.mention_text,
        "normalized_alias": mention.normalized_alias,
        "predicted_type": mention.predicted_type.value,
        "start_offset": mention.start,
        "end_offset": mention.end,
        "score": mention.score,
        "model_name": mention.model_name,
        "model_version": mention.model_version,
        "status": mention.status.value,
        "resolved_entity_id": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "resolution_note": None,
        "created_at": mention.created_at,
    }


def _unresolved_from_row(row: RowMapping) -> UnresolvedEntityMention:
    return UnresolvedEntityMention(
        id=row["id"],
        article_version_id=row["article_version_id"],
        source_field=SourceField(row["source_field"]),
        mention_text=row["mention_text"],
        normalized_alias=row["normalized_alias"],
        predicted_type=EntityType(row["predicted_type"]),
        start=row["start_offset"],
        end=row["end_offset"],
        score=row["score"],
        model_name=row["model_name"],
        model_version=row["model_version"],
        status=UnresolvedReviewStatus(row["status"]),
        created_at=row["created_at"],
    )


class PostgresUnresolvedMentionRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_once(self, mention: UnresolvedEntityMention) -> UnresolvedEntityMention:
        statement = (
            insert(unresolved_entity_mentions)
            .values(**_unresolved_values(mention))
            .on_conflict_do_nothing(index_elements=[unresolved_entity_mentions.c.id])
            .returning(*unresolved_entity_mentions.c)
        )
        with self._engine.begin() as connection:
            row = connection.execute(statement).mappings().one_or_none()
            if row is None:
                row = (
                    connection.execute(
                        sa.select(unresolved_entity_mentions).where(
                            unresolved_entity_mentions.c.id == mention.id
                        )
                    )
                    .mappings()
                    .one()
                )
        return _unresolved_from_row(row)


def _embedding_values(record: EmbeddingRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "article_version_id": record.article_version_id,
        "input_hash": record.input_hash,
        "input_builder_version": record.input_builder_version,
        "model_name": record.model_name,
        "model_version": record.model_version,
        "dimensions": record.dimensions,
        "embedding": list(record.vector.values),
        "token_count": record.token_count,
        "embedded_token_count": record.embedded_token_count,
        "truncated": record.truncated,
        "created_at": record.created_at,
    }


def _embedding_from_row(row: RowMapping) -> EmbeddingRecord:
    return EmbeddingRecord(
        id=row["id"],
        article_version_id=row["article_version_id"],
        input_hash=row["input_hash"],
        input_builder_version=row["input_builder_version"],
        model_name=row["model_name"],
        model_version=row["model_version"],
        vector=EmbeddingVector.create(list(row["embedding"])),
        dimensions=row["dimensions"],
        token_count=row["token_count"],
        embedded_token_count=row["embedded_token_count"],
        truncated=row["truncated"],
        created_at=row["created_at"],
    )


class PostgresEmbeddingRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_once(self, record: EmbeddingRecord) -> EmbeddingRecord:
        statement = (
            insert(article_embeddings)
            .values(**_embedding_values(record))
            .on_conflict_do_nothing(index_elements=[article_embeddings.c.id])
            .returning(*article_embeddings.c)
        )
        with self._engine.begin() as connection:
            row = connection.execute(statement).mappings().one_or_none()
            if row is None:
                row = (
                    connection.execute(
                        sa.select(article_embeddings).where(article_embeddings.c.id == record.id)
                    )
                    .mappings()
                    .one()
                )
        return _embedding_from_row(row)

    def get(self, embedding_id: UUID) -> EmbeddingRecord | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    sa.select(article_embeddings).where(article_embeddings.c.id == embedding_id)
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else _embedding_from_row(row)

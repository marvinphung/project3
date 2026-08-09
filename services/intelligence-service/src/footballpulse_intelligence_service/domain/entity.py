from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NON_ALPHANUMERIC_PATTERN = re.compile(r"[^a-z0-9]+")


class EntityType(StrEnum):
    PLAYER = "PLAYER"
    CLUB = "CLUB"
    COACH = "COACH"
    COMPETITION = "COMPETITION"


class EntityStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class AliasReviewStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AliasSource(StrEnum):
    SEED = "SEED"
    ADMIN = "ADMIN"
    PIPELINE = "PIPELINE"


def normalize_alias(value: str) -> str:
    folded = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    return _NON_ALPHANUMERIC_PATTERN.sub(" ", folded).strip()


def _required_text(value: str, field: str, *, max_length: int | None = None) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    if max_length is not None and len(normalized) > max_length:
        raise ValueError(f"{field} must contain at most {max_length} characters")
    return normalized


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class Entity:
    id: UUID
    entity_type: EntityType
    canonical_name: str
    slug: str
    status: EntityStatus
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def create(
        cls,
        *,
        entity_id: UUID,
        entity_type: EntityType,
        canonical_name: str,
        slug: str,
        now: datetime,
    ) -> Entity:
        canonical_name = _required_text(canonical_name, "canonical_name", max_length=200)
        if len(slug) > 200 or not _SLUG_PATTERN.fullmatch(slug):
            raise ValueError("slug must be lowercase ASCII words separated by hyphens")
        timestamp = _aware(now)
        return cls(
            entity_id,
            EntityType(entity_type),
            canonical_name,
            slug,
            EntityStatus.ACTIVE,
            timestamp,
            timestamp,
            1,
        )

    @property
    def is_active(self) -> bool:
        return self.status is EntityStatus.ACTIVE

    def rename(self, canonical_name: str, *, now: datetime) -> Entity:
        return replace(
            self,
            canonical_name=_required_text(canonical_name, "canonical_name", max_length=200),
            updated_at=_aware(now),
            version=self.version + 1,
        )

    def change_slug(self, slug: str, *, now: datetime) -> Entity:
        if len(slug) > 200 or not _SLUG_PATTERN.fullmatch(slug):
            raise ValueError("slug must be lowercase ASCII words separated by hyphens")
        return replace(self, slug=slug, updated_at=_aware(now), version=self.version + 1)

    def disable(self, *, now: datetime) -> Entity:
        if not self.is_active:
            return self
        return replace(
            self,
            status=EntityStatus.DISABLED,
            updated_at=_aware(now),
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class EntityAlias:
    id: UUID
    entity_id: UUID
    alias: str
    normalized_alias: str
    review_status: AliasReviewStatus
    resolver_version: str
    source: AliasSource
    actor: str
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by: str | None
    disabled_at: datetime | None
    updated_at: datetime
    version: int

    @classmethod
    def create(
        cls,
        *,
        alias_id: UUID,
        entity_id: UUID,
        alias: str,
        review_status: AliasReviewStatus,
        resolver_version: str,
        source: AliasSource,
        actor: str,
        now: datetime,
    ) -> EntityAlias:
        alias = _required_text(alias, "alias", max_length=200)
        normalized = normalize_alias(alias)
        if not normalized:
            raise ValueError("alias must contain letters or digits")
        status = AliasReviewStatus(review_status)
        alias_source = AliasSource(source)
        if alias_source is AliasSource.PIPELINE and status is AliasReviewStatus.APPROVED:
            raise ValueError("pipeline aliases must be reviewed before approval")
        resolver_version = _required_text(resolver_version, "resolver_version", max_length=100)
        actor = _required_text(actor, "actor", max_length=200)
        timestamp = _aware(now)
        is_approved = status is AliasReviewStatus.APPROVED
        return cls(
            alias_id,
            entity_id,
            alias,
            normalized,
            status,
            resolver_version,
            alias_source,
            actor,
            timestamp,
            timestamp if is_approved else None,
            actor if is_approved else None,
            None,
            timestamp,
            1,
        )

    @property
    def is_resolvable(self) -> bool:
        return self.review_status is AliasReviewStatus.APPROVED and self.disabled_at is None

    def review(
        self,
        status: AliasReviewStatus,
        *,
        actor: str,
        now: datetime,
    ) -> EntityAlias:
        if self.review_status is not AliasReviewStatus.PENDING_REVIEW:
            raise ValueError("only pending aliases can be reviewed")
        status = AliasReviewStatus(status)
        if status is AliasReviewStatus.PENDING_REVIEW:
            raise ValueError("review decision must approve or reject")
        timestamp = _aware(now)
        return replace(
            self,
            review_status=status,
            reviewed_at=timestamp,
            reviewed_by=_required_text(actor, "actor", max_length=200),
            updated_at=timestamp,
            version=self.version + 1,
        )

    def disable(self, *, now: datetime) -> EntityAlias:
        if self.disabled_at is not None:
            return self
        timestamp = _aware(now)
        return replace(
            self,
            disabled_at=timestamp,
            updated_at=timestamp,
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class EntityAuditRecord:
    id: UUID
    resource_type: str
    resource_id: UUID
    action: str
    actor: str
    reason: str
    details: dict[str, object]
    occurred_at: datetime

    @classmethod
    def create(
        cls,
        *,
        audit_id: UUID,
        resource_type: str,
        resource_id: UUID,
        action: str,
        actor: str,
        reason: str,
        details: dict[str, object],
        now: datetime,
    ) -> EntityAuditRecord:
        if resource_type not in {"ENTITY", "ALIAS"}:
            raise ValueError("invalid audit resource type")
        return cls(
            audit_id,
            resource_type,
            resource_id,
            _required_text(action, "action", max_length=64),
            _required_text(actor, "actor", max_length=200),
            _required_text(reason, "reason"),
            details,
            _aware(now),
        )

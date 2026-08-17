from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.entity import EntityType


class StoryEventType(StrEnum):
    TRANSFER = "TRANSFER"
    CONTRACT = "CONTRACT"
    INJURY = "INJURY"
    MATCH = "MATCH"
    MANAGERIAL = "MANAGERIAL"
    DISCIPLINARY = "DISCIPLINARY"
    OTHER = "OTHER"


class StoryStatus(StrEnum):
    DEVELOPING = "DEVELOPING"
    CONFIRMED = "CONFIRMED"
    STALE = "STALE"
    CLOSED = "CLOSED"


class ClaimPredicate(StrEnum):
    EXPRESSED_INTEREST = "EXPRESSED_INTEREST"
    CONTACTED = "CONTACTED"
    SUBMITTED_BID = "SUBMITTED_BID"
    ACCEPTED_BID = "ACCEPTED_BID"
    REJECTED_BID = "REJECTED_BID"
    COMPLETED_TRANSFER = "COMPLETED_TRANSFER"
    NEGOTIATING_CONTRACT = "NEGOTIATING_CONTRACT"
    SIGNED_CONTRACT = "SIGNED_CONTRACT"
    SUFFERED_INJURY = "SUFFERED_INJURY"
    EXPECTED_RETURN = "EXPECTED_RETURN"
    MATCH_SCHEDULED = "MATCH_SCHEDULED"
    MATCH_RESULT = "MATCH_RESULT"
    APPOINTED_COACH = "APPOINTED_COACH"
    DISMISSED_COACH = "DISMISSED_COACH"
    DENIED_REPORT = "DENIED_REPORT"


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


def _required_text(value: str, field: str, *, max_length: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    if len(normalized) > max_length:
        raise ValueError(f"{field} must contain at most {max_length} characters")
    return normalized


def _score(value: Decimal, field: str) -> Decimal:
    score = Decimal(value)
    if not math.isfinite(float(score)) or score < 0 or score > 1:
        raise ValueError(f"{field} must be between 0 and 1")
    return score


@dataclass(frozen=True, slots=True)
class Story:
    id: UUID
    event_type: StoryEventType
    status: StoryStatus
    confidence_score: Decimal
    first_seen_at: datetime
    last_seen_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        story_id: UUID,
        event_type: StoryEventType,
        first_seen_at: datetime,
        confidence_score: Decimal,
    ) -> Story:
        observed_at = _aware(first_seen_at, "first_seen_at")
        return cls(
            story_id,
            StoryEventType(event_type),
            StoryStatus.DEVELOPING,
            _score(confidence_score, "confidence_score"),
            observed_at,
            observed_at,
            1,
            observed_at,
            observed_at,
        )

    def observe(self, *, at: datetime, confidence_score: Decimal) -> Story:
        observed_at = _aware(at, "observation timestamp")
        if observed_at < self.last_seen_at:
            raise ValueError("observation timestamp cannot be before last_seen_at")
        return replace(
            self,
            confidence_score=_score(confidence_score, "confidence_score"),
            last_seen_at=observed_at,
            updated_at=observed_at,
            version=self.version + 1,
        )

    def change_status(self, status: StoryStatus, *, now: datetime) -> Story:
        next_status = StoryStatus(status)
        if next_status is self.status:
            return self
        changed_at = _aware(now, "status timestamp")
        if changed_at < self.updated_at:
            raise ValueError("status timestamp cannot be before updated_at")
        return replace(
            self,
            status=next_status,
            updated_at=changed_at,
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class StorySource:
    id: UUID
    story_id: UUID
    article_version_id: UUID
    source_id: UUID
    source_cluster_id: UUID | None
    source_reliability_tier: int
    is_official: bool
    published_at: datetime
    observed_at: datetime

    @classmethod
    def create(
        cls,
        *,
        link_id: UUID,
        story_id: UUID,
        article_version_id: UUID,
        source_id: UUID,
        source_reliability_tier: int,
        published_at: datetime,
        observed_at: datetime,
        source_cluster_id: UUID | None = None,
        is_official: bool = False,
    ) -> StorySource:
        if not 1 <= source_reliability_tier <= 5:
            raise ValueError("source reliability tier must be between 1 and 5")
        return cls(
            link_id,
            story_id,
            article_version_id,
            source_id,
            source_cluster_id,
            source_reliability_tier,
            is_official,
            _aware(published_at, "published_at"),
            _aware(observed_at, "observed_at"),
        )


@dataclass(frozen=True, slots=True)
class StoryEntity:
    id: UUID
    story_id: UUID
    entity_id: UUID
    entity_type: EntityType
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        link_id: UUID,
        story_id: UUID,
        entity_id: UUID,
        entity_type: EntityType,
        now: datetime,
    ) -> StoryEntity:
        return cls(link_id, story_id, entity_id, EntityType(entity_type), _aware(now, "created_at"))


@dataclass(frozen=True, slots=True)
class Claim:
    id: UUID
    story_id: UUID
    fingerprint: str
    subject_entity_id: UUID
    predicate: ClaimPredicate
    object_entity_id: UUID | None
    object_value: dict[str, object] | None
    statement_en: str
    certainty: Decimal
    occurred_at: datetime | None
    occurred_at_bucket: datetime | None
    created_at: datetime
    confirmation: ClaimConfirmation = ClaimConfirmation.RUMOUR

    @classmethod
    def create(
        cls,
        *,
        claim_id: UUID,
        story_id: UUID,
        subject_entity_id: UUID,
        predicate: ClaimPredicate,
        object_entity_id: UUID | None,
        object_value: dict[str, object] | None,
        statement_en: str,
        certainty: Decimal,
        occurred_at: datetime | None,
        occurred_at_bucket: datetime | None,
        now: datetime,
        confirmation: ClaimConfirmation = ClaimConfirmation.RUMOUR,
    ) -> Claim:
        if object_entity_id is None and object_value is None:
            raise ValueError("claim requires an object entity or object value")
        if (occurred_at is None) is not (occurred_at_bucket is None):
            raise ValueError("occurred_at and occurred_at_bucket must be provided together")
        occurred = None if occurred_at is None else _aware(occurred_at, "occurred_at")
        bucket = (
            None if occurred_at_bucket is None else _aware(occurred_at_bucket, "occurred_at_bucket")
        )
        if occurred is not None and bucket is not None and bucket > occurred:
            raise ValueError("occurred_at_bucket cannot be after occurred_at")
        normalized_object = None if object_value is None else dict(object_value)
        fingerprint = _claim_fingerprint(
            story_id=story_id,
            subject_entity_id=subject_entity_id,
            predicate=ClaimPredicate(predicate),
            object_entity_id=object_entity_id,
            object_value=normalized_object,
            occurred_at_bucket=bucket,
        )
        return cls(
            claim_id,
            story_id,
            fingerprint,
            subject_entity_id,
            ClaimPredicate(predicate),
            object_entity_id,
            normalized_object,
            _required_text(statement_en, "statement_en", max_length=4_000),
            _score(certainty, "certainty"),
            occurred,
            bucket,
            _aware(now, "created_at"),
            ClaimConfirmation(confirmation),
        )

    def with_confirmation(self, confirmation: ClaimConfirmation) -> Claim:
        return replace(self, confirmation=ClaimConfirmation(confirmation))


def _claim_fingerprint(
    *,
    story_id: UUID,
    subject_entity_id: UUID,
    predicate: ClaimPredicate,
    object_entity_id: UUID | None,
    object_value: dict[str, object] | None,
    occurred_at_bucket: datetime | None,
) -> str:
    identity = {
        "story_id": str(story_id),
        "subject_entity_id": str(subject_entity_id),
        "predicate": predicate.value,
        "object_entity_id": None if object_entity_id is None else str(object_entity_id),
        "object_value": object_value,
        "occurred_at_bucket": (
            None if occurred_at_bucket is None else occurred_at_bucket.isoformat()
        ),
    }
    try:
        encoded = json.dumps(identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as error:
        raise ValueError("claim object_value must be JSON serializable") from error
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    id: UUID
    claim_id: UUID
    story_source_id: UUID
    quote: str
    start: int
    end: int
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        evidence_id: UUID,
        claim_id: UUID,
        story_source_id: UUID,
        quote: str,
        start: int,
        end: int,
        now: datetime,
    ) -> ClaimEvidence:
        if start < 0 or end <= start:
            raise ValueError("evidence range must be a non-empty half-open interval")
        return cls(
            evidence_id,
            claim_id,
            story_source_id,
            _required_text(quote, "evidence quote", max_length=2_000),
            start,
            end,
            _aware(now, "created_at"),
        )

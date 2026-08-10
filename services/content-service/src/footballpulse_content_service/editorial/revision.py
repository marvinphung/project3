from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class RevisionState(StrEnum):
    DRAFT = "DRAFT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


def _text(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class EditorialRevision:
    id: UUID
    generated_article_id: UUID
    story_id: UUID
    story_version: int
    revision_number: int
    title_en: str
    body_en: str
    title_vi: str
    body_vi: str
    state: RevisionState
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        revision_id: UUID,
        generated_article_id: UUID,
        story_id: UUID,
        story_version: int,
        revision_number: int,
        title_en: str,
        body_en: str,
        title_vi: str,
        body_vi: str,
        created_at: datetime,
    ) -> EditorialRevision:
        if story_version < 1 or revision_number < 1:
            raise ValueError("story and revision versions must be at least 1")
        timestamp = _aware(created_at, "created_at")
        return cls(
            revision_id,
            generated_article_id,
            story_id,
            story_version,
            revision_number,
            _text(title_en, "title_en"),
            _text(body_en, "body_en"),
            _text(title_vi, "title_vi"),
            _text(body_vi, "body_vi"),
            RevisionState.DRAFT,
            timestamp,
            timestamp,
        )

    def submit_for_review(self, now: datetime) -> EditorialRevision:
        if self.state is not RevisionState.DRAFT:
            raise ValueError("only DRAFT revision can move to NEEDS_REVIEW")
        return replace(self, state=RevisionState.NEEDS_REVIEW, updated_at=_aware(now, "updated_at"))

    def approve(self, now: datetime) -> EditorialRevision:
        if self.state is not RevisionState.NEEDS_REVIEW:
            raise ValueError("only NEEDS_REVIEW revision can be APPROVED")
        return replace(self, state=RevisionState.APPROVED, updated_at=_aware(now, "updated_at"))

    def reject(self, now: datetime) -> EditorialRevision:
        if self.state is not RevisionState.NEEDS_REVIEW:
            raise ValueError("only NEEDS_REVIEW revision can be REJECTED")
        return replace(self, state=RevisionState.REJECTED, updated_at=_aware(now, "updated_at"))

    def mark_stale(self, *, story_version: int, now: datetime) -> EditorialRevision:
        if story_version <= self.story_version:
            raise ValueError("new Story version must be greater than revision version")
        return replace(
            self,
            state=RevisionState.STALE,
            story_version=story_version,
            updated_at=_aware(now, "updated_at"),
        )

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from footballpulse_intelligence_service.domain.story import ClaimPredicate


@dataclass(frozen=True, slots=True)
class StoryCandidateContext:
    story_id: UUID
    story_version: int
    primary_entity_ids: tuple[UUID, ...]
    entity_ids: tuple[UUID, ...]
    predicates: tuple[ClaimPredicate, ...]

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from footballpulse_intelligence_service.domain.story_candidate_scoring import (
    StoryCandidateScore,
)

_IDENTITY_SAFETY_REASONS = frozenset(
    {
        "QUERY_PRIMARY_ENTITY_MISSING",
        "CANDIDATE_PRIMARY_ENTITY_MISSING",
        "PRIMARY_ENTITY_CONFLICT",
        "IDENTITY_CONTEXT_MISSING",
        "IDENTITY_CONTEXT_CONFLICT",
    }
)


class MatchAction(StrEnum):
    ATTACH = "ATTACH"
    CREATE = "CREATE"
    REVIEW = "REVIEW"


class StoryCandidateRetryableError(Exception):
    def __init__(self, story_ids: tuple[UUID, ...]) -> None:
        self.story_ids = story_ids
        super().__init__("current Story embeddings are missing; generate them and retry")


@dataclass(frozen=True, slots=True)
class StoryCandidatePolicyConfig:
    review_threshold: float
    attach_threshold: float
    near_tie_margin: float
    matcher_version: str

    def __post_init__(self) -> None:
        values = (self.review_threshold, self.attach_threshold, self.near_tie_margin)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Story matcher thresholds must be finite")
        if not 0 <= self.review_threshold < self.attach_threshold <= 100:
            raise ValueError("thresholds must satisfy 0 <= review < attach <= 100")
        if not 0 <= self.near_tie_margin <= 100:
            raise ValueError("near_tie_margin must be between 0 and 100")
        normalized_version = " ".join(self.matcher_version.split())
        if not normalized_version or len(normalized_version) > 100:
            raise ValueError("matcher_version is invalid")
        object.__setattr__(self, "matcher_version", normalized_version)


@dataclass(frozen=True, slots=True)
class CandidateDecisionInput:
    story_id: UUID
    story_version: int
    score: StoryCandidateScore

    def __post_init__(self) -> None:
        if self.story_version < 1:
            raise ValueError("candidate Story version must be positive")
        if not math.isfinite(self.score.total) or not 0 <= self.score.total <= 100:
            raise ValueError("candidate score total must be between 0 and 100")
        component_total = sum(
            (
                self.score.components.vector_similarity,
                self.score.components.primary_entity,
                self.score.components.entity_overlap,
                self.score.components.predicate_compatibility,
                self.score.components.time_distance,
            )
        )
        if not math.isclose(self.score.total, component_total, abs_tol=1e-9):
            raise ValueError("candidate score total must equal its component sum")


@dataclass(frozen=True, slots=True)
class StoryMatchDecision:
    action: MatchAction
    selected_story_id: UUID | None
    selected_story_version: int | None
    ranked_candidates: tuple[CandidateDecisionInput, ...]
    reason_codes: tuple[str, ...]
    matcher_version: str
    review_threshold: float
    attach_threshold: float
    near_tie_margin: float
    embedding_model_name: str
    embedding_model_version: str


def _model_identity(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 200:
        raise ValueError(f"{field} is invalid")
    return normalized


class StoryCandidateDecisionPolicy:
    def __init__(self, config: StoryCandidatePolicyConfig) -> None:
        self._config = config

    def decide(
        self,
        *,
        candidates: tuple[CandidateDecisionInput, ...],
        missing_current_embedding_story_ids: tuple[UUID, ...],
        embedding_model_name: str,
        embedding_model_version: str,
    ) -> StoryMatchDecision:
        model_name = _model_identity(embedding_model_name, "embedding_model_name")
        model_version = _model_identity(embedding_model_version, "embedding_model_version")
        if len(set(missing_current_embedding_story_ids)) != len(
            missing_current_embedding_story_ids
        ):
            raise ValueError("missing embedding Story IDs must be unique")
        if missing_current_embedding_story_ids:
            raise StoryCandidateRetryableError(missing_current_embedding_story_ids)
        if len({candidate.story_id for candidate in candidates}) != len(candidates):
            raise ValueError("candidate Story IDs must be unique")

        ranked = tuple(sorted(candidates, key=lambda item: (-item.score.total, str(item.story_id))))
        if not ranked:
            return self._decision(
                MatchAction.CREATE,
                None,
                ranked,
                ("NO_CANDIDATES",),
                model_name,
                model_version,
            )

        top = ranked[0]
        safety_reasons = tuple(
            reason for reason in top.score.reason_codes if reason in _IDENTITY_SAFETY_REASONS
        )
        if safety_reasons:
            return self._decision(
                MatchAction.REVIEW,
                top,
                ranked,
                safety_reasons,
                model_name,
                model_version,
            )
        if top.score.total < self._config.review_threshold:
            return self._decision(
                MatchAction.CREATE,
                None,
                ranked,
                ("TOP_SCORE_BELOW_REVIEW_THRESHOLD",),
                model_name,
                model_version,
            )
        if (
            len(ranked) > 1
            and top.score.total - ranked[1].score.total <= self._config.near_tie_margin
        ):
            return self._decision(
                MatchAction.REVIEW,
                top,
                ranked,
                ("CANDIDATE_NEAR_TIE",),
                model_name,
                model_version,
            )
        if top.score.total >= self._config.attach_threshold:
            return self._decision(
                MatchAction.ATTACH,
                top,
                ranked,
                ("TOP_SCORE_ATTACHABLE",),
                model_name,
                model_version,
            )
        return self._decision(
            MatchAction.REVIEW,
            top,
            ranked,
            ("TOP_SCORE_IN_REVIEW_BAND",),
            model_name,
            model_version,
        )

    def _decision(
        self,
        action: MatchAction,
        selected: CandidateDecisionInput | None,
        ranked: tuple[CandidateDecisionInput, ...],
        reasons: tuple[str, ...],
        model_name: str,
        model_version: str,
    ) -> StoryMatchDecision:
        return StoryMatchDecision(
            action,
            None if selected is None else selected.story_id,
            None if selected is None else selected.story_version,
            ranked,
            reasons,
            self._config.matcher_version,
            self._config.review_threshold,
            self._config.attach_threshold,
            self._config.near_tie_margin,
            model_name,
            model_version,
        )

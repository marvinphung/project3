from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_MILLION_PATTERN = re.compile(r"€?\s*(\d+)\s*(?:million|m)\b", re.IGNORECASE)
_STOP_WORDS = frozenset(
    (
        "a",
        "an",
        "the",
        "to",
        "for",
        "with",
        "from",
        "have",
        "has",
        "had",
        "not",
        "no",
        "yet",
        "after",
        "in",
        "is",
        "are",
        "was",
        "were",
        "of",
        "at",
        "on",
        "and",
        "also",
        "known",
        "as",
        "worth",
        "valued",
        "formal",
        "major",
        "star",
        "club",
        "spanish",
        "winger",
        "said",
        "will",
        "adds",
        "new",
        "report",
        "remains",
        "still",
        "terms",
        "opener",
        "pre",
        "season",
    )
)
_SYNONYMS = {
    "bid": "offer",
    "gunners": "arsenal",
    "jr": "vinicius",
    "junior": "vinicius",
    "lodge": "submit",
    "lodged": "submit",
    "proposal": "offer",
    "responded": "respond",
    "response": "respond",
    "send": "submit",
    "sending": "submit",
    "submitted": "submit",
    "vini": "vinicius",
    "wait": "respond",
    "waiting": "respond",
}


class DuplicateType(StrEnum):
    NONE = "NONE"
    EXACT = "EXACT"
    NEAR = "NEAR"


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    article_id: UUID
    article_version_id: UUID
    title: str
    cleaned_content: str
    content_hash: str
    collected_at: datetime


@dataclass(frozen=True, slots=True)
class SimilarityComponents:
    title_similarity: float
    content_similarity: float
    time_similarity: float


@dataclass(frozen=True, slots=True)
class DuplicateDecision:
    duplicate_type: DuplicateType
    primary_article_id: UUID | None
    primary_article_version_id: UUID | None
    score: float
    components: SimilarityComponents
    threshold: float
    reason: str

    @property
    def continue_to_ai(self) -> bool:
        return self.duplicate_type is not DuplicateType.EXACT


def _signature(value: str) -> frozenset[str]:
    folded = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    folded = _MILLION_PATTERN.sub(lambda match: f" {match.group(1)}m ", folded)
    tokens = (
        _SYNONYMS.get(token, token)
        for token in _TOKEN_PATTERN.findall(folded)
        if token not in _STOP_WORDS
    )
    return frozenset(tokens)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


class DuplicatePolicy:
    def __init__(
        self,
        *,
        near_threshold: float = 0.65,
        window: timedelta = timedelta(hours=72),
        max_candidates: int = 50,
    ) -> None:
        if not 0 < near_threshold <= 1:
            raise ValueError("near duplicate threshold must be between 0 and 1")
        if window <= timedelta(0):
            raise ValueError("duplicate time window must be positive")
        if not 1 <= max_candidates <= 100:
            raise ValueError("duplicate candidate limit must be between 1 and 100")
        self._threshold = near_threshold
        self._window = window
        self._max_candidates = max_candidates

    def classify(
        self,
        *,
        title: str,
        cleaned_content: str,
        collected_at: datetime,
        candidates: list[DuplicateCandidate],
    ) -> DuplicateDecision:
        if len(candidates) > self._max_candidates:
            raise ValueError("duplicate candidate input exceeds configured limit")
        if not title or not cleaned_content or collected_at.tzinfo is None:
            raise ValueError("duplicate input requires title, content and aware timestamp")
        content_hash = hashlib.sha256(cleaned_content.encode("utf-8")).hexdigest()
        exact = sorted(
            (candidate for candidate in candidates if candidate.content_hash == content_hash),
            key=lambda candidate: (candidate.collected_at, str(candidate.article_version_id)),
        )
        if exact:
            primary = exact[0]
            return DuplicateDecision(
                DuplicateType.EXACT,
                primary.article_id,
                primary.article_version_id,
                1.0,
                SimilarityComponents(1.0, 1.0, 1.0),
                self._threshold,
                "same_cleaned_content_hash",
            )

        title_signature = _signature(title)
        content_signature = _signature(cleaned_content)
        best_candidate: DuplicateCandidate | None = None
        best_components = SimilarityComponents(0.0, 0.0, 0.0)
        best_score = 0.0
        ordered_candidates = sorted(
            candidates,
            key=lambda candidate: (candidate.collected_at, str(candidate.article_version_id)),
        )
        for candidate in ordered_candidates:
            age = collected_at - candidate.collected_at
            if age < timedelta(0) or age > self._window:
                continue
            components = SimilarityComponents(
                title_similarity=_jaccard(title_signature, _signature(candidate.title)),
                content_similarity=_jaccard(
                    content_signature,
                    _signature(candidate.cleaned_content),
                ),
                time_similarity=max(0.0, 1.0 - age / self._window),
            )
            score = (
                0.25 * components.title_similarity
                + 0.65 * components.content_similarity
                + 0.10 * components.time_similarity
            )
            if score > best_score:
                best_candidate = candidate
                best_components = components
                best_score = score

        rounded_score = round(best_score, 6)
        rounded_components = SimilarityComponents(
            round(best_components.title_similarity, 6),
            round(best_components.content_similarity, 6),
            round(best_components.time_similarity, 6),
        )
        if best_candidate is not None and rounded_score >= self._threshold:
            return DuplicateDecision(
                DuplicateType.NEAR,
                best_candidate.article_id,
                best_candidate.article_version_id,
                rounded_score,
                rounded_components,
                self._threshold,
                "weighted_lexical_similarity_above_threshold",
            )
        return DuplicateDecision(
            DuplicateType.NONE,
            None,
            None,
            rounded_score,
            rounded_components,
            self._threshold,
            "no_candidate_above_threshold",
        )

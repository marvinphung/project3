from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from footballpulse_intelligence_service.domain.embedding import (
    EMBEDDING_DIMENSIONS,
    EmbeddingVector,
)
from footballpulse_intelligence_service.domain.story import ClaimPredicate, StoryEventType

MAX_STORY_EMBEDDING_TEXT_CHARS = 500_000
_STORY_EMBEDDING_NAMESPACE = UUID("018f8b45-b634-7c81-a47d-9a7c2f3ca002")


def _text(value: str, field: str, *, max_length: int = 200) -> str:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > max_length:
        raise ValueError(f"{field} is invalid")
    return normalized


@dataclass(frozen=True, slots=True)
class StoryEmbeddingClaim:
    subject_entity_id: UUID
    subject_name: str
    predicate: ClaimPredicate
    object_entity_id: UUID | None
    object_name: str | None
    object_value: dict[str, object] | None

    def render(self) -> str:
        subject = _text(self.subject_name, "claim subject name")
        object_name = (
            None if self.object_name is None else _text(self.object_name, "claim object name")
        )
        if self.object_entity_id is not None and object_name is None:
            raise ValueError("claim object entity requires a canonical name")
        if self.object_entity_id is None and object_name is not None:
            raise ValueError("claim object name requires a canonical entity")
        if object_name is None and self.object_value is None:
            raise ValueError("claim requires an object representation")
        value = ""
        if self.object_value is not None:
            try:
                value = json.dumps(
                    self.object_value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            except (TypeError, ValueError) as error:
                raise ValueError("claim object value must be JSON serializable") from error
        return " ".join(
            part
            for part in (subject, ClaimPredicate(self.predicate).value, object_name, value)
            if part
        )


@dataclass(frozen=True, slots=True)
class StoryEmbeddingInput:
    story_id: UUID
    story_version: int
    event_type: StoryEventType
    canonical_entities: tuple[str, ...]
    claims: tuple[StoryEmbeddingClaim, ...]


@dataclass(frozen=True, slots=True)
class BuiltStoryEmbeddingInput:
    story_id: UUID
    story_version: int
    text: str
    input_hash: str


def build_story_embedding_text(source: StoryEmbeddingInput) -> BuiltStoryEmbeddingInput:
    if source.story_version < 1:
        raise ValueError("story version must be positive")
    unique_entities: dict[str, str] = {}
    for value in source.canonical_entities:
        entity = _text(value, "canonical entity name")
        key = entity.casefold()
        current = unique_entities.get(key)
        if current is None or entity < current:
            unique_entities[key] = entity
    if not unique_entities:
        raise ValueError("story embedding requires canonical entities")
    rendered_claims = sorted({claim.render() for claim in source.claims}, key=str.casefold)
    if not rendered_claims:
        raise ValueError("story embedding requires canonical claims")
    entities = sorted(unique_entities.values(), key=lambda value: (value.casefold(), value))
    text = "\n".join(
        (
            f"event_type: {StoryEventType(source.event_type).value}",
            f"entities: {' | '.join(entities)}",
            "claims:",
            *rendered_claims,
        )
    )
    if len(text) > MAX_STORY_EMBEDDING_TEXT_CHARS:
        raise ValueError("story embedding text exceeds configured length")
    hash_input = f"{source.story_id}:{source.story_version}\n{text}"
    return BuiltStoryEmbeddingInput(
        source.story_id,
        source.story_version,
        text,
        hashlib.sha256(hash_input.encode("utf-8")).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class StoryEmbeddingRecord:
    id: UUID
    story_id: UUID
    story_version: int
    input_hash: str
    input_builder_version: str
    model_name: str
    model_version: str
    vector: EmbeddingVector
    dimensions: int
    token_count: int
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        story_id: UUID,
        story_version: int,
        input_hash: str,
        input_builder_version: str,
        model_name: str,
        model_version: str,
        vector: EmbeddingVector,
        token_count: int,
        now: datetime,
    ) -> StoryEmbeddingRecord:
        if story_version < 1:
            raise ValueError("story version must be positive")
        if len(input_hash) != 64 or any(char not in "0123456789abcdef" for char in input_hash):
            raise ValueError("story embedding input hash must be lowercase SHA-256")
        identities = {
            "input_builder_version": _text(
                input_builder_version,
                "input builder version",
                max_length=100,
            ),
            "model_name": _text(model_name, "model name", max_length=200),
            "model_version": _text(model_version, "model version", max_length=200),
        }
        if token_count < 1:
            raise ValueError("story embedding token count must be positive")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("story embedding timestamp must be timezone-aware")
        stable_key = ":".join(
            (
                str(story_id),
                str(story_version),
                input_hash,
                identities["model_name"],
                identities["model_version"],
            )
        )
        return cls(
            uuid5(_STORY_EMBEDDING_NAMESPACE, stable_key),
            story_id,
            story_version,
            input_hash,
            identities["input_builder_version"],
            identities["model_name"],
            identities["model_version"],
            vector,
            EMBEDDING_DIMENSIONS,
            token_count,
            now,
        )

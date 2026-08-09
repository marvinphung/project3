from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

EMBEDDING_DIMENSIONS = 384
MAX_EMBEDDING_CONTENT_CHARS = 500_000
_NORMALIZATION_TOLERANCE = 1e-4
_EMBEDDING_NAMESPACE = UUID("018f8b45-b634-7c81-a47d-9a7c2f3ca001")


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


@dataclass(frozen=True, slots=True)
class EmbeddingInput:
    article_version_id: UUID
    title: str
    canonical_entities: tuple[str, ...]
    cleaned_content: str


@dataclass(frozen=True, slots=True)
class BuiltEmbeddingInput:
    article_version_id: UUID
    text: str
    input_hash: str


def build_embedding_text(source: EmbeddingInput) -> BuiltEmbeddingInput:
    title = _collapse_whitespace(source.title)
    if not title:
        raise ValueError("embedding title must not be empty")
    if len(title) > 1_000:
        raise ValueError("embedding title exceeds configured length")
    if len(source.cleaned_content) > MAX_EMBEDDING_CONTENT_CHARS:
        raise ValueError("embedding content exceeds configured length")
    content = _collapse_whitespace(source.cleaned_content)
    if not content:
        raise ValueError("embedding content must not be empty")

    unique_entities: dict[str, str] = {}
    for raw_entity in source.canonical_entities:
        entity = _collapse_whitespace(raw_entity)
        if not entity:
            raise ValueError("canonical entity name must not be empty")
        if len(entity) > 200:
            raise ValueError("canonical entity name exceeds configured length")
        key = entity.casefold()
        current = unique_entities.get(key)
        if current is None or entity < current:
            unique_entities[key] = entity
    entities = sorted(unique_entities.values(), key=lambda value: (value.casefold(), value))

    sections = [f"title: {title}"]
    if entities:
        sections.append(f"entities: {' | '.join(entities)}")
    sections.append(f"content: {content}")
    text = "\n".join(sections)
    return BuiltEmbeddingInput(
        source.article_version_id,
        text,
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    values: tuple[float, ...]

    @classmethod
    def create(cls, values: list[float] | tuple[float, ...]) -> EmbeddingVector:
        numeric_values = tuple(float(value) for value in values)
        if len(numeric_values) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"embedding must contain {EMBEDDING_DIMENSIONS} dimensions")
        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("embedding must contain only finite values")
        norm = math.sqrt(math.fsum(value * value for value in numeric_values))
        if not math.isclose(norm, 1.0, rel_tol=_NORMALIZATION_TOLERANCE, abs_tol=0.0):
            raise ValueError("embedding must be L2-normalized")
        return cls(numeric_values)


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    id: UUID
    article_version_id: UUID
    input_hash: str
    input_builder_version: str
    model_name: str
    model_version: str
    vector: EmbeddingVector
    dimensions: int
    token_count: int
    embedded_token_count: int
    truncated: bool
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        article_version_id: UUID,
        input_hash: str,
        input_builder_version: str,
        model_name: str,
        model_version: str,
        vector: EmbeddingVector,
        token_count: int,
        embedded_token_count: int,
        truncated: bool,
        now: datetime,
    ) -> EmbeddingRecord:
        if len(input_hash) != 64 or any(char not in "0123456789abcdef" for char in input_hash):
            raise ValueError("embedding input hash must be lowercase SHA-256")
        identities = {
            "input_builder_version": (input_builder_version.strip(), 100),
            "model_name": (model_name.strip(), 200),
            "model_version": (model_version.strip(), 200),
        }
        for field, (value, limit) in identities.items():
            if not value or len(value) > limit:
                raise ValueError(f"embedding {field} is invalid")
        if token_count < 1 or embedded_token_count < 1:
            raise ValueError("embedding token counts must be positive")
        if embedded_token_count > token_count:
            raise ValueError("embedded token count cannot exceed input token count")
        if truncated is not (embedded_token_count < token_count):
            raise ValueError("embedding truncation metadata is inconsistent")
        if now.tzinfo is None:
            raise ValueError("embedding timestamp must be timezone-aware")
        stable_key = ":".join(
            (
                str(article_version_id),
                input_hash,
                identities["model_name"][0],
                identities["model_version"][0],
            )
        )
        return cls(
            uuid5(_EMBEDDING_NAMESPACE, stable_key),
            article_version_id,
            input_hash,
            identities["input_builder_version"][0],
            identities["model_name"][0],
            identities["model_version"][0],
            vector,
            EMBEDDING_DIMENSIONS,
            token_count,
            embedded_token_count,
            truncated,
            now,
        )

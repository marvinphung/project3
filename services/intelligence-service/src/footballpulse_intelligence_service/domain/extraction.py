from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_WORD_PATTERN = re.compile(r"\S+")


class EntityLabel(StrEnum):
    PLAYER = "player"
    CLUB = "club"
    COACH = "coach"
    COMPETITION = "competition"

    @classmethod
    def from_string(cls, value: str) -> EntityLabel:
        mapping = {
            "player": cls.PLAYER,
            "football player": cls.PLAYER,
            "club": cls.CLUB,
            "football club": cls.CLUB,
            "coach": cls.COACH,
            "football coach": cls.COACH,
            "competition": cls.COMPETITION,
            "football competition": cls.COMPETITION,
        }
        normalized = value.strip().casefold()
        if normalized in mapping:
            return mapping[normalized]
        return cls(value)


class SourceField(StrEnum):
    TITLE = "TITLE"
    CONTENT = "CONTENT"


@dataclass(frozen=True, slots=True)
class TextChunk:
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SpanPrediction:
    source_field: SourceField
    text: str
    label: EntityLabel
    start: int
    end: int
    score: float

    @classmethod
    def create(
        cls,
        *,
        source_field: SourceField,
        source_text: str,
        label: EntityLabel | str,
        start: int,
        end: int,
        score: float,
    ) -> SpanPrediction:
        if start < 0 or end <= start or end > len(source_text):
            raise ValueError("prediction offset is outside source text")
        if not 0 <= score <= 1:
            raise ValueError("prediction score must be between 0 and 1")
        mention = source_text[start:end]
        if not mention.strip():
            raise ValueError("prediction offsets must select non-empty text")
        entity_label = (
            label if isinstance(label, EntityLabel) else EntityLabel.from_string(str(label))
        )
        return cls(
            SourceField(source_field),
            mention,
            entity_label,
            start,
            end,
            score,
        )


def split_text(
    text: str,
    *,
    max_words: int,
    overlap_words: int,
    max_chunks: int,
    max_chars: int = 500_000,
) -> list[TextChunk]:
    if max_words < 1 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("chunk word limits are invalid")
    if max_chunks < 1 or max_chars < 1:
        raise ValueError("chunk count and text length limits must be positive")
    if len(text) > max_chars:
        raise ValueError("text length exceeds configured limit")
    words = list(_WORD_PATTERN.finditer(text))
    if not words:
        return []

    chunks: list[TextChunk] = []
    first_word = 0
    while first_word < len(words):
        last_word = min(first_word + max_words, len(words))
        start = words[first_word].start()
        end = words[last_word - 1].end()
        chunks.append(TextChunk(text[start:end], start, end))
        if len(chunks) > max_chunks:
            raise ValueError("text requires more chunks than configured limit")
        if last_word == len(words):
            break
        first_word = last_word - overlap_words
    return chunks


def deduplicate_predictions(predictions: list[SpanPrediction]) -> list[SpanPrediction]:
    best: dict[tuple[SourceField, EntityLabel, int, int], SpanPrediction] = {}
    for prediction in predictions:
        key = (
            prediction.source_field,
            prediction.label,
            prediction.start,
            prediction.end,
        )
        current = best.get(key)
        if current is None or prediction.score > current.score:
            best[key] = prediction
    return sorted(
        best.values(),
        key=lambda prediction: (
            prediction.source_field.value,
            prediction.start,
            prediction.end,
            prediction.label.value,
        ),
    )

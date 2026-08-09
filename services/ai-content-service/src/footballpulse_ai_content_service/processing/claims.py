from __future__ import annotations

import json
import re
from dataclasses import dataclass
from uuid import UUID, uuid5

from footballpulse_ai_content_service.contracts.enrichment import (
    ClaimCertainty,
    ClaimOutput,
    ClaimQualifiers,
    Predicate,
)

_WORD_PATTERN = re.compile(r"\S+")
_CLAIM_NAMESPACE = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb001")
_CERTAINTY_STRENGTH = {
    ClaimCertainty.RUMOR: 0,
    ClaimCertainty.REPORTED: 1,
    ClaimCertainty.CONFIRMED: 2,
    ClaimCertainty.DENIED: 2,
}


@dataclass(frozen=True, slots=True)
class ContentChunk:
    index: int
    text: str
    start: int
    end: int


def split_content(
    content: str,
    *,
    max_words: int = 1_200,
    overlap_words: int = 150,
    max_chunks: int = 64,
    max_chars: int = 500_000,
) -> tuple[ContentChunk, ...]:
    if max_words < 1 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("AI chunk word limits are invalid")
    if max_chunks < 1 or max_chars < 1:
        raise ValueError("AI chunk count and content length limits must be positive")
    if len(content) > max_chars:
        raise ValueError("AI content exceeds configured length")
    words = list(_WORD_PATTERN.finditer(content))
    if not words:
        return ()

    chunks: list[ContentChunk] = []
    first_word = 0
    while first_word < len(words):
        last_word = min(first_word + max_words, len(words))
        start = words[first_word].start()
        end = words[last_word - 1].end()
        chunks.append(ContentChunk(len(chunks), content[start:end], start, end))
        if len(chunks) > max_chunks:
            raise ValueError("AI content requires more chunks than configured limit")
        if last_word == len(words):
            break
        first_word = last_word - overlap_words
    return tuple(chunks)


def globalize_claim(chunk: ContentChunk, claim: ClaimOutput) -> ClaimOutput:
    if claim.evidence_end > len(chunk.text):
        raise ValueError("claim evidence offset is outside chunk")
    if chunk.text[claim.evidence_start : claim.evidence_end] != claim.evidence_quote:
        raise ValueError("claim evidence quote does not match chunk offsets")
    return claim.model_copy(
        update={
            "evidence_start": chunk.start + claim.evidence_start,
            "evidence_end": chunk.start + claim.evidence_end,
        }
    )


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    quote: str
    start: int
    end: int
    certainty: ClaimCertainty


@dataclass(frozen=True, slots=True)
class MergedClaim:
    claim_id: UUID
    subject_entity_id: UUID
    predicate: Predicate
    object_entity_id: UUID | None
    object_text: str | None
    qualifiers: ClaimQualifiers
    certainty: ClaimCertainty
    evidence: tuple[ClaimEvidence, ...]


def _claim_key(claim: ClaimOutput) -> tuple[str, ...]:
    object_key = (
        f"entity:{claim.object_entity_id}"
        if claim.object_entity_id is not None
        else f"text:{' '.join((claim.object_text or '').split()).casefold()}"
    )
    qualifier_key = json.dumps(
        claim.qualifiers.model_dump(mode="json", exclude_none=True),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return str(claim.subject_entity_id), claim.predicate.value, object_key, qualifier_key


def merge_claims(claims: list[ClaimOutput], *, max_claims: int = 500) -> tuple[MergedClaim, ...]:
    if len(claims) > max_claims:
        raise ValueError("claim count exceeds configured limit")
    grouped: dict[tuple[str, ...], list[ClaimOutput]] = {}
    for claim in claims:
        grouped.setdefault(_claim_key(claim), []).append(claim)

    merged: list[MergedClaim] = []
    for key, variants in sorted(grouped.items()):
        first = variants[0]
        certainty = max(
            (variant.certainty for variant in variants),
            key=lambda value: (_CERTAINTY_STRENGTH[value], value.value),
        )
        unique_evidence = {
            (
                variant.evidence_start,
                variant.evidence_end,
                variant.evidence_quote,
                variant.certainty,
            ): ClaimEvidence(
                variant.evidence_quote,
                variant.evidence_start,
                variant.evidence_end,
                variant.certainty,
            )
            for variant in variants
        }
        evidence = tuple(
            unique_evidence[evidence_key]
            for evidence_key in sorted(
                unique_evidence,
                key=lambda item: (item[0], item[1], item[2], item[3].value),
            )
        )
        stable_key = json.dumps(key, ensure_ascii=True, separators=(",", ":"))
        merged.append(
            MergedClaim(
                uuid5(_CLAIM_NAMESPACE, stable_key),
                first.subject_entity_id,
                first.predicate,
                first.object_entity_id,
                first.object_text,
                first.qualifiers,
                certainty,
                evidence,
            )
        )
    return tuple(merged)

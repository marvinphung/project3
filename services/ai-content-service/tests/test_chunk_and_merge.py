from __future__ import annotations

from uuid import UUID

from footballpulse_ai_content_service.contracts.enrichment import (
    ClaimCertainty,
    ClaimOutput,
    ClaimQualifiers,
    Predicate,
)
from footballpulse_ai_content_service.processing.claims import (
    globalize_claim,
    merge_claims,
    split_content,
)

ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")


def _claim(
    *,
    predicate: Predicate = Predicate.SUBMITTED_BID,
    certainty: ClaimCertainty = ClaimCertainty.REPORTED,
    start: int = 0,
    quote: str = "Arsenal submitted an offer",
) -> ClaimOutput:
    return ClaimOutput(
        subject_entity_id=ARSENAL_ID,
        predicate=predicate,
        object_entity_id=PLAYER_ID,
        object_text=None,
        qualifiers=ClaimQualifiers(amount=180_000_000, currency="EUR"),
        certainty=certainty,
        evidence_quote=quote,
        evidence_start=start,
        evidence_end=start + len(quote),
    )


def test_chunking_preserves_global_offsets_and_overlap() -> None:
    content = "one two three four five six seven"

    chunks = split_content(content, max_words=4, overlap_words=1, max_chunks=10)

    assert [chunk.text for chunk in chunks] == ["one two three four", "four five six seven"]
    assert [chunk.start for chunk in chunks] == [0, 14]
    assert all(content[chunk.start : chunk.end] == chunk.text for chunk in chunks)


def test_local_evidence_offsets_are_globalized_and_verified() -> None:
    content = "Earlier report. Arsenal submitted an offer yesterday."
    chunk = split_content(content, max_words=4, overlap_words=2, max_chunks=10)[1]
    local_start = chunk.text.index("Arsenal")
    claim = _claim(start=local_start)

    global_claim = globalize_claim(chunk, claim)

    assert global_claim.evidence_start == content.index("Arsenal")
    assert content[global_claim.evidence_start : global_claim.evidence_end] == claim.evidence_quote


def test_merge_deduplicates_overlap_keeps_all_evidence_and_strongest_certainty() -> None:
    first = _claim(start=10, certainty=ClaimCertainty.REPORTED)
    second = _claim(start=80, certainty=ClaimCertainty.CONFIRMED)

    merged = merge_claims([first, second])

    assert len(merged) == 1
    assert merged[0].certainty is ClaimCertainty.CONFIRMED
    assert [evidence.start for evidence in merged[0].evidence] == [10, 80]
    assert len(str(merged[0].claim_id)) == 36


def test_merge_preserves_conflicting_predicates() -> None:
    positive = _claim(predicate=Predicate.SUBMITTED_BID)
    denial = _claim(predicate=Predicate.DENIED_REPORT, certainty=ClaimCertainty.DENIED)

    merged = merge_claims([positive, denial])

    assert {claim.predicate for claim in merged} == {
        Predicate.SUBMITTED_BID,
        Predicate.DENIED_REPORT,
    }

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from footballpulse_article_service.domain.duplicate import (
    DuplicateCandidate,
    DuplicatePolicy,
    DuplicateType,
)

NOW = datetime(2026, 8, 1, 5, 5, tzinfo=UTC)
OFFER_TITLE = "Arsenal submit €180m Vinicius offer"
OFFER_TEXT = (
    "Arsenal send €180m offer to Real Madrid for Vinícius Júnior Arsenal have submitted "
    "a formal offer worth €180 million to Real Madrid for Vinícius Júnior. Real Madrid "
    "have not yet responded to the proposal."
)
NEAR_TITLE = "Gunners lodge major Vinicius proposal"
NEAR_TEXT = (
    "Gunners lodge major proposal for Real star Arsenal, also known as the Gunners, "
    "lodged an offer valued at €180m for Real Madrid winger Vinícius Júnior. The Spanish "
    "club is considering the bid."
)
INJURY_TITLE = "Vinicius ruled out with hamstring injury"
INJURY_TEXT = (
    "Vinícius Júnior suffers hamstring injury Real Madrid coach Xabi Alonso said Vini Jr "
    "will miss the La Liga opener with a hamstring injury."
)
MATCH_TITLE = "Real Madrid beat Arsenal 2-1"
MATCH_TEXT = (
    "Real Madrid beat Arsenal in friendly Real Madrid defeated Arsenal 2-1 after a late "
    "winner in a pre-season match."
)


def _candidate(
    *,
    suffix: int,
    title: str = OFFER_TITLE,
    text: str = OFFER_TEXT,
    collected_at: datetime = NOW - timedelta(hours=1),
) -> DuplicateCandidate:
    return DuplicateCandidate(
        article_id=UUID(f"018f8b45-b634-7c81-a47d-9a7c2f3c41{suffix:02d}"),
        article_version_id=UUID(f"018f8b45-b634-7c81-a47d-9a7c2f3c42{suffix:02d}"),
        title=title,
        cleaned_content=text,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        collected_at=collected_at,
    )


def test_exact_hash_links_to_primary_and_stops_ai() -> None:
    decision = DuplicatePolicy().classify(
        title="Syndicated headline",
        cleaned_content=OFFER_TEXT,
        collected_at=NOW,
        candidates=[_candidate(suffix=1)],
    )

    assert decision.duplicate_type is DuplicateType.EXACT
    assert decision.primary_article_version_id == _candidate(suffix=1).article_version_id
    assert decision.score == 1.0
    assert decision.continue_to_ai is False
    assert decision.reason == "same_cleaned_content_hash"


def test_fixture_paraphrase_is_near_duplicate_with_inspectable_components() -> None:
    decision = DuplicatePolicy(near_threshold=0.65).classify(
        title=NEAR_TITLE,
        cleaned_content=NEAR_TEXT,
        collected_at=NOW,
        candidates=[_candidate(suffix=1)],
    )

    assert decision.duplicate_type is DuplicateType.NEAR
    assert decision.primary_article_version_id == _candidate(suffix=1).article_version_id
    assert decision.score >= 0.65
    assert decision.components.title_similarity >= 0.7
    assert decision.components.content_similarity >= 0.5
    assert decision.components.time_similarity > 0.9
    assert decision.threshold == 0.65
    assert decision.continue_to_ai is True


def test_injury_and_match_fixtures_are_not_false_positive_near_duplicates() -> None:
    policy = DuplicatePolicy(near_threshold=0.65)

    injury = policy.classify(
        title=INJURY_TITLE,
        cleaned_content=INJURY_TEXT,
        collected_at=NOW,
        candidates=[_candidate(suffix=1)],
    )
    match = policy.classify(
        title=MATCH_TITLE,
        cleaned_content=MATCH_TEXT,
        collected_at=NOW,
        candidates=[_candidate(suffix=1)],
    )

    assert injury.duplicate_type is DuplicateType.NONE
    assert match.duplicate_type is DuplicateType.NONE
    assert injury.score < 0.65
    assert match.score < 0.65


def test_ignores_candidate_outside_time_window() -> None:
    old = _candidate(suffix=1, collected_at=NOW - timedelta(hours=73))

    decision = DuplicatePolicy(window=timedelta(hours=72)).classify(
        title=NEAR_TITLE,
        cleaned_content=NEAR_TEXT,
        collected_at=NOW,
        candidates=[old],
    )

    assert decision.duplicate_type is DuplicateType.NONE
    assert decision.primary_article_version_id is None


def test_rejects_unbounded_candidate_set() -> None:
    candidates = [_candidate(suffix=index) for index in range(1, 52)]

    try:
        DuplicatePolicy(max_candidates=50).classify(
            title=NEAR_TITLE,
            cleaned_content=NEAR_TEXT,
            collected_at=NOW,
            candidates=candidates,
        )
    except ValueError as error:
        assert "candidate" in str(error)
    else:
        raise AssertionError("unbounded candidate input must be rejected")


def test_near_duplicate_tie_break_is_independent_of_candidate_order() -> None:
    candidates = [_candidate(suffix=2), _candidate(suffix=1)]
    policy = DuplicatePolicy()

    first = policy.classify(
        title=NEAR_TITLE,
        cleaned_content=NEAR_TEXT,
        collected_at=NOW,
        candidates=candidates,
    )
    reversed_result = policy.classify(
        title=NEAR_TITLE,
        cleaned_content=NEAR_TEXT,
        collected_at=NOW,
        candidates=list(reversed(candidates)),
    )

    assert first.primary_article_version_id == _candidate(suffix=1).article_version_id
    assert reversed_result.primary_article_version_id == first.primary_article_version_id

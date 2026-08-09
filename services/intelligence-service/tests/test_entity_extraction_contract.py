from __future__ import annotations

from footballpulse_intelligence_service.domain.extraction import (
    EntityLabel,
    SourceField,
    SpanPrediction,
    deduplicate_predictions,
    split_text,
)


def test_chunking_preserves_global_offsets_with_word_overlap() -> None:
    text = "one two three four five six seven"

    chunks = split_text(text, max_words=4, overlap_words=1, max_chunks=10)

    assert [chunk.text for chunk in chunks] == ["one two three four", "four five six seven"]
    assert [chunk.start for chunk in chunks] == [0, 14]
    assert all(text[chunk.start : chunk.end] == chunk.text for chunk in chunks)


def test_chunking_rejects_unbounded_article_or_chunk_count() -> None:
    try:
        split_text("x" * 101, max_words=10, overlap_words=1, max_chunks=2, max_chars=100)
    except ValueError as error:
        assert "length" in str(error)
    else:
        raise AssertionError("oversized text must be rejected")

    try:
        split_text("one two three four five", max_words=2, overlap_words=1, max_chunks=2)
    except ValueError as error:
        assert "chunk" in str(error)
    else:
        raise AssertionError("unbounded chunk count must be rejected")


def test_overlap_predictions_use_global_offsets_and_keep_highest_score() -> None:
    text = "Arsenal contacted Vinicius Junior before Real Madrid replied."
    low = SpanPrediction.create(
        source_field=SourceField.CONTENT,
        source_text=text,
        label=EntityLabel.PLAYER,
        start=18,
        end=33,
        score=0.76,
    )
    high = SpanPrediction.create(
        source_field=SourceField.CONTENT,
        source_text=text,
        label=EntityLabel.PLAYER,
        start=18,
        end=33,
        score=0.91,
    )

    assert deduplicate_predictions([low, high]) == [high]
    assert high.text == "Vinicius Junior"


def test_prediction_rejects_offsets_that_do_not_match_source_text() -> None:
    try:
        SpanPrediction.create(
            source_field=SourceField.TITLE,
            source_text="Arsenal update",
            label=EntityLabel.CLUB,
            start=8,
            end=99,
            score=0.8,
        )
    except ValueError as error:
        assert "offset" in str(error)
    else:
        raise AssertionError("invalid model offsets must be rejected")

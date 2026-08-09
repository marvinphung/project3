from __future__ import annotations

from footballpulse_crawler_service.extraction.normalization import normalize_article_text


def test_normalizes_whitespace_entities_unicode_and_invisible_characters() -> None:
    decomposed_name = "Vini\u0301cius"
    raw = f"  {decomposed_name}\n\t sent&nbsp;an offer.\u200b\x00  "

    normalized = normalize_article_text(raw)

    assert normalized == "Vinícius sent an offer."


def test_removes_exact_duplicate_paragraphs_but_preserves_punctuation_and_currency() -> None:
    raw = (
        "Arsenal submitted a €180m offer.\n\n"
        "Real Madrid have not responded.\n"
        "Arsenal submitted a €180m offer."
    )

    normalized = normalize_article_text(raw)

    assert normalized == "Arsenal submitted a €180m offer. Real Madrid have not responded."


def test_does_not_remove_repeated_words_inside_a_paragraph() -> None:
    assert normalize_article_text("very very important") == "very very important"

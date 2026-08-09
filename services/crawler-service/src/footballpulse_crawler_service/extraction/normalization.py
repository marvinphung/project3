from __future__ import annotations

import html
import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def _remove_invisible_characters(value: str) -> str:
    characters: list[str] = []
    for character in value:
        category = unicodedata.category(character)
        if category == "Cf":
            continue
        if category == "Cc":
            if character.isspace():
                characters.append(" ")
            continue
        characters.append(character)
    return "".join(characters)


def normalize_article_text(value: str) -> str:
    """Normalize representation without rewriting editorial meaning."""
    decoded = unicodedata.normalize("NFC", html.unescape(value))
    paragraphs: list[str] = []
    seen: set[str] = set()
    for raw_paragraph in decoded.splitlines() or [decoded]:
        visible = _remove_invisible_characters(raw_paragraph)
        paragraph = _WHITESPACE.sub(" ", visible).strip()
        if not paragraph or paragraph in seen:
            continue
        seen.add(paragraph)
        paragraphs.append(paragraph)
    return " ".join(paragraphs)

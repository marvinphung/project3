from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid5

ENTITY_NAMESPACE = UUID("a5577179-7f6d-4f2e-8e6d-9671bfc68231")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^\w\s']", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")
    return slug


def canonical_key(entity_type: str, canonical_name: str) -> str:
    return f"{entity_type.upper()}:{slugify(canonical_name)}"


def deterministic_entity_id(entity_type: str, canonical_name: str) -> UUID:
    key = canonical_key(entity_type, canonical_name)
    return uuid5(ENTITY_NAMESPACE, key)


@dataclass(frozen=True, slots=True)
class AliasReplacementRule:
    pattern: re.Pattern[str]
    canonical_name: str
    original_alias: str


@dataclass(frozen=True, slots=True)
class CanonicalEntityInfo:
    id: UUID
    canonical_name: str
    entity_type: str


class CanonicalRegistry:
    """Manages alias replacement rules and canonical entity lookup."""

    def __init__(self, entities: Iterable[dict[str, Any]]) -> None:
        self._lookup: dict[tuple[str, str], CanonicalEntityInfo] = {}
        self._alias_map: dict[str, str] = {}
        self._replacement_pattern: re.Pattern[str] | None = None

        raw_aliases: list[str] = []

        for doc in entities:
            entity_id = doc["_id"] if isinstance(doc["_id"], UUID) else UUID(str(doc["_id"]))
            canonical_name = str(doc["canonical_name"]).strip()
            entity_type = str(doc.get("entity_type", "CLUB")).upper()
            info = CanonicalEntityInfo(id=entity_id, canonical_name=canonical_name, entity_type=entity_type)

            # Map canonical name itself
            norm_canonical = normalize_text(canonical_name)
            self._lookup[(entity_type, norm_canonical)] = info
            self._lookup[("ALL", norm_canonical)] = info

            # Collect aliases
            aliases = doc.get("aliases", [])
            for alias_entry in aliases:
                if isinstance(alias_entry, dict):
                    alias_val = str(alias_entry.get("value", "")).strip()
                else:
                    alias_val = str(alias_entry).strip()
                if not alias_val:
                    continue
                norm_alias = normalize_text(alias_val)
                self._lookup[(entity_type, norm_alias)] = info
                self._lookup[("ALL", norm_alias)] = info

                if alias_val.casefold() != canonical_name.casefold():
                    self._alias_map[alias_val.casefold()] = canonical_name
                    raw_aliases.append(alias_val)

        if raw_aliases:
            # Sort longest alias first so alternation prefers longer matches
            raw_aliases.sort(key=len, reverse=True)
            pattern_str = r"(?<!\w)(" + "|".join(re.escape(a) for a in raw_aliases) + r")(?!\w)"
            self._replacement_pattern = re.compile(pattern_str, re.IGNORECASE)

    def replace_aliases(self, text: str) -> str:
        """Replaces known aliases in text with canonical names using a single pass."""
        if not text or not self._replacement_pattern:
            return text or ""

        return self._replacement_pattern.sub(
            lambda match: self._alias_map.get(match.group(0).casefold(), match.group(0)),
            text,
        )

    def resolve_entity(
        self,
        mention_text: str,
        label: str,
    ) -> tuple[UUID, str]:
        """Resolves mention text and label to (canonical_entity_id, canonical_name)."""
        clean_label = label.upper()
        norm = normalize_text(mention_text)

        # 1. Direct match in registry for label
        info = self._lookup.get((clean_label, norm))
        if info is None:
            # 2. Match in registry across all types
            info = self._lookup.get(("ALL", norm))

        if info is not None:
            return info.id, info.canonical_name

        # 3. Fallback for unseeded entities (e.g. players/coaches/competitions)
        clean_name = mention_text.strip()
        entity_id = deterministic_entity_id(clean_label, clean_name)
        return entity_id, clean_name

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from pymongo import ASCENDING, MongoClient

ENTITY_NAMESPACE = UUID("a5577179-7f6d-4f2e-8e6d-9671bfc68231")
DEFAULT_SOURCE = "docs/europe_top6_clubs_2026_27_aliases.json"


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
    return f"{entity_type.casefold()}:{slugify(canonical_name)}"


def load_documents(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    season = str(payload["season"])
    seen_aliases: dict[str, str] = {}
    documents: list[dict[str, Any]] = []
    now = datetime.now(UTC)

    for league, clubs in payload["leagues"].items():
        for club in clubs:
            canonical_name = str(club["club"]).strip()
            key = canonical_key("CLUB", canonical_name)
            alias_values = [canonical_name, *club.get("alias", [])]
            aliases = []
            alias_values_normalized: list[str] = []
            for raw_alias in alias_values:
                value = str(raw_alias).strip()
                if not value:
                    continue
                normalized = normalize_text(value)
                if not normalized:
                    continue
                owner = seen_aliases.get(normalized)
                if owner is not None and owner != key:
                    raise ValueError(f"Alias conflict for {value!r}: {owner} vs {key}")
                seen_aliases[normalized] = key
                if normalized not in alias_values_normalized:
                    alias_values_normalized.append(normalized)
                    aliases.append(
                        {
                            "value": value,
                            "normalized_value": normalized,
                            "case_sensitive": False,
                        }
                    )

            documents.append(
                {
                    "_id": uuid5(ENTITY_NAMESPACE, key),
                    "entity_type": "CLUB",
                    "canonical_key": key,
                    "canonical_name": canonical_name,
                    "canonical_name_normalized": normalize_text(canonical_name),
                    "leagues": [str(league)],
                    "seasons": [season],
                    "aliases": aliases,
                    "alias_values_normalized": alias_values_normalized,
                    "status": "ACTIVE",
                    "source": str(path),
                    "created_at": now,
                    "updated_at": now,
                }
            )

    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description="Import canonical football entities into MongoDB.")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--mongo-url", default=os.getenv("FOOTBALLPULSE_MONGODB_URL", "mongodb://127.0.0.1:27117/?replicaSet=rs0&directConnection=true"))
    parser.add_argument("--db", default=os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2"))
    args = parser.parse_args()

    documents = load_documents(Path(args.source))
    client: MongoClient[dict[str, Any]] = MongoClient(args.mongo_url, uuidRepresentation="standard")
    database = client[args.db]
    collection = database.canonical_entities

    collection.create_index([("canonical_key", ASCENDING)], unique=True)
    collection.create_index([("entity_type", ASCENDING), ("canonical_name_normalized", ASCENDING)])
    collection.create_index([("alias_values_normalized", ASCENDING)])
    collection.create_index([("status", ASCENDING), ("updated_at", ASCENDING)])

    for document in documents:
        collection.update_one(
            {"canonical_key": document["canonical_key"]},
            {
                "$set": {
                    "entity_type": document["entity_type"],
                    "canonical_name": document["canonical_name"],
                    "canonical_name_normalized": document["canonical_name_normalized"],
                    "leagues": document["leagues"],
                    "seasons": document["seasons"],
                    "aliases": document["aliases"],
                    "alias_values_normalized": document["alias_values_normalized"],
                    "status": document["status"],
                    "source": document["source"],
                    "updated_at": document["updated_at"],
                },
                "$setOnInsert": {
                    "_id": document["_id"],
                    "created_at": document["created_at"],
                },
            },
            upsert=True,
        )

    print(f"Imported {len(documents)} canonical entities into {args.db}.canonical_entities")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

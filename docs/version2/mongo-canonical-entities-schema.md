# Mongo Schema: Canonical Entities

## Purpose

`canonical_entities` is the MongoDB source of truth for entity aliases used by
the pipeline.

The aliases are not part of the PostgreSQL serving read model. They are used by
pipeline services before extraction/grouping so text variants such as `MU`,
`Man United`, and `Man Utd` can be rewritten to `Manchester United` in
`clean_content`.

## Collection

```text
canonical_entities
```

## Document Shape

```json
{
  "_id": "uuid",
  "entity_type": "CLUB",
  "canonical_key": "club:manchester-united",
  "canonical_name": "Manchester United",
  "canonical_name_normalized": "manchester united",
  "leagues": ["Premier League"],
  "seasons": ["2026-27"],
  "aliases": [
    {
      "value": "MU",
      "normalized_value": "mu",
      "case_sensitive": false
    },
    {
      "value": "Man United",
      "normalized_value": "man united",
      "case_sensitive": false
    }
  ],
  "alias_values_normalized": [
    "manchester united",
    "mu",
    "man united"
  ],
  "status": "ACTIVE",
  "source": "docs/europe_top6_clubs_2026_27_aliases.json",
  "created_at": "2026-08-20T00:00:00Z",
  "updated_at": "2026-08-20T00:00:00Z"
}
```

## Rules

- `canonical_key` is unique and deterministic: `{entity_type}:{normalized_slug}`.
- `canonical_name` is the text that should replace aliases in cleaned article content.
- `alias_values_normalized` must include the normalized canonical name and every normalized alias.
- Alias matching is case-insensitive by default.
- Import must detect duplicate normalized aliases across different canonical entities and fail fast.
- Pipeline services may load this collection into memory and build a longest-match-first alias map.

## Indexes

```text
unique: canonical_key
index:  entity_type + canonical_name_normalized
index:  alias_values_normalized
index:  status + updated_at
```

## Current Seed Source

The current seed data is:

```text
docs/europe_top6_clubs_2026_27_aliases.json
```

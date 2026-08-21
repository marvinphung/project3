# MongoDB Pipeline Store

## Purpose

MongoDB la working store cho pipeline. No luu du lieu trung gian co shape linh
hoat: crawl output, canonical entity catalog, extraction results va timeline
summaries truoc khi publish sang Supabase PostgreSQL.

MongoDB khong phai serving database production cho frontend.

## Collections

```text
canonical_entities
news_metadata
news_content
news_entities
entity_timeline_summaries
```

Legacy/old collections nhu `news_enrichments` hoac `news_embeddings` khong nam
trong target entity timeline flow hien tai.

## `canonical_entities`

Owner:

- canonical entity import/catalog process
- consumed by `entities-extraction-service`

Purpose:

- luu canonical names va aliases
- support alias replacement trong `filtered_content`
- support publish aliases sang PostgreSQL `entities.aliases`

Important fields:

| Field | Meaning |
| --- | --- |
| `_id` | deterministic UUID cua canonical entity |
| `entity_type` | `PLAYER`, `CLUB`, `COACH`, `COMPETITION` |
| `canonical_key` | unique key, thuong la `<type>:<slug>` |
| `canonical_name` | ten canonical de hien thi va group |
| `canonical_name_normalized` | normalized name de lookup |
| `aliases` | list alias values |
| `alias_values_normalized` | normalized aliases de search/lookup |
| `status` | `ACTIVE` neu entity con dung |
| `source` | source file/import source |
| `created_at`, `updated_at` | audit timestamps |

Indexes/lookup:

- unique `canonical_key`
- lookup by `(entity_type, canonical_name_normalized)`
- lookup aliases via `alias_values_normalized`
- filter active docs by `status`

Key invariant:

- Alias chung chung hoac conflict giua 2 canonical entities phai bi chan o import.
- Alias replacement uu tien alias dai hon truoc.

## `news_metadata`

Owner:

- `crawler`

Purpose:

- article metadata
- canonical URL dedupe
- timestamp source cho summary buckets va popularity window

Important fields:

| Field | Meaning |
| --- | --- |
| `_id` | UUID article id, shared across article collections |
| `url` | original URL |
| `canonical_url` | unique canonical URL |
| `domain_name` | source domain |
| `source_name` | human source name |
| `title` | article title |
| `description` | source description/excerpt neu co |
| `published_time` | source published time neu co |
| `crawl_date` | pipeline timestamp, clock chinh cho v2 summary |
| `image_url` | article image |
| `tags` | source tags |
| `article_keywords` | keywords neu source co |
| `content_hash` | content duplicate helper |
| `language` | article language |

Indexes/lookup:

- unique `canonical_url`
- `domain_name`
- `published_time`
- text index title/description

Key invariant:

- `crawl_date` phai ton tai.
- Summary window va popularity 24h dung `crawl_date`, khong dung
  `published_time`.

## `news_content`

Owner:

- `crawler` owns `content`, `cleaned_at`, `extractor`, `extraction_status`
- `entities-extraction-service` owns `filtered_content`, `filtered_at`

Purpose:

- luu clean article body
- luu filtered canonicalized body cho extraction/ranking

Important fields:

| Field | Meaning |
| --- | --- |
| `_id` | same UUID as `news_metadata._id` |
| `content` | clean content used in LLM prompt |
| `filtered_content` | content after alias replacement |
| `cleaned_at` | crawler extraction timestamp |
| `filtered_at` | entity extraction filtering timestamp |
| `extractor` | extractor used by crawler |
| `extraction_status` | `SUCCESS`, `PARTIAL`, `FAILED` |

Indexes/lookup:

- `cleaned_at`
- `filtered_at`

Key invariant:

- LLM prompt dung `content`.
- Mention count ranking dung `filtered_content`.
- Neu `filtered_content` missing, summary co the fallback sang `content`, nhung
  target pipeline phai tao `filtered_content` truoc summary.

## `news_entities`

Owner:

- `entities-extraction-service`

Purpose:

- one document per article
- luu extracted/canonical entity mentions
- source cho summary grouping va popularity counts

Important fields:

| Field | Meaning |
| --- | --- |
| `_id` | same UUID as article id |
| `entities` | list of extracted mentions |
| `model_name` | extraction model name |
| `model_version` | extraction model version |
| `processed_at` | extraction timestamp |

Entity mention fields:

| Field | Meaning |
| --- | --- |
| `label` | entity type: `PLAYER`, `CLUB`, `COACH`, `COMPETITION` |
| `text` | mention text from filtered content |
| `score` | model confidence |
| `start`, `end` | character offsets in filtered content |
| `canonical_entity_id` | UUID after canonical resolution |
| `canonical_name` | display/grouping name |

Indexes/lookup:

- `entities.label`
- `entities.canonical_entity_id`
- `entities.canonical_name`
- `processed_at`

Key invariant:

- Only mentions with score `>= ENTITY_EXTRACTION_MIN_CONFIDENCE` should be saved.
- Current target confidence is `0.95`.
- Distinct article count must deduplicate mentions within one article.

## `entity_timeline_summaries`

Owner:

- `content-summary-service`

Purpose:

- Mongo-side generated summary before publish
- one entity + one 3h UTC window

Important fields:

| Field | Meaning |
| --- | --- |
| `_id` | deterministic summary UUID |
| `entity_id` | canonical entity UUID |
| `canonical_name` | display/group name |
| `entity_type` | `PLAYER`, `CLUB`, `COACH`, `COMPETITION` |
| `window_start`, `window_end` | fixed 3h UTC window |
| `article_ids` | selected articles sent to LLM |
| `article_count` | number of selected articles |
| `aggregated_news` | LLM `content` |
| `short_description` | LLM `title` |
| `status` | `COMPLETED` or failed status |
| `error_message` | error detail if failed |
| `published_at` | set by publish after PostgreSQL materialization |
| `created_at`, `updated_at` | audit timestamps |

Legacy fields:

- `entities_50`
- `entities_80`

These fields remain for compatibility if schema/code still contains them. Target
summary flow no longer uses `>=50%` or `>=80%` entity thresholds.

Indexes/lookup:

- `(entity_id, window_start, window_end)`
- `(status, window_start)`
- `(canonical_name, window_start)`
- `(window_start, window_end)`

Key invariant:

- `_id` deterministic from `entity_id + window_start + window_end`.
- Re-running summary should skip existing `COMPLETED` docs unless force recompute.
- `window_start/window_end` must align to UTC 3h buckets.

## Debug Queries

Backlog for entities extraction:

```text
news_metadata exists but news_entities missing
```

Summary candidates:

```text
news_metadata.crawl_date in [window_start, window_end)
news_entities exists for same article id
```

Publish candidates:

```text
entity_timeline_summaries.status = COMPLETED
published_at is missing/null
```

## Retention

Mongo currently acts as pipeline history. If retention is introduced later, it
must not delete data needed to republish latest Supabase read model unless
archive/replay strategy exists.

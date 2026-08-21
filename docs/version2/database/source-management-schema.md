# Source Management Schema

## Purpose

`source_schema` la PostgreSQL schema phuc vu crawler source management va crawl
batch diagnostics. No khac voi Supabase public read model.

Target serving layer khong doc schema nay.

## Tables

```text
source_schema.sources
source_schema.crawl_batches
```

## `source_schema.sources`

Owner:

- crawler source management/admin logic

Consumers:

- crawler

Purpose:

- luu danh sach source crawl duoc enable
- luu RSS/source URL, allowed domains, crawl interval va concurrency settings

Important columns:

| Column | Meaning |
| --- | --- |
| `id` | source UUID |
| `name` | source display name |
| `rss_url` | RSS/source feed URL |
| `allowed_domains` | allowed crawl domains |
| `source_type` | RSS/real source type |
| `reliability_tier` | source quality tier |
| `enabled` | crawler can use source or not |
| `crawl_interval_minutes` | schedule hint |
| `max_concurrency` | per-source crawl concurrency |
| `last_discovered_at` | last discovery timestamp |
| `created_at`, `updated_at` | audit timestamps |
| `version` | optimistic/version field |

## `source_schema.crawl_batches`

Owner:

- crawler

Consumers:

- crawler diagnostics/admin tooling

Purpose:

- track one crawl batch per source/window/idempotency key
- support diagnosing failed or partial crawl runs

Important columns:

| Column | Meaning |
| --- | --- |
| `id` | batch UUID |
| `source_id` | source id |
| `idempotency_key` | dedupe key for batch |
| `window_started_at` | crawl window start |
| `status` | batch status |
| `discovered_count` | number discovered |
| `fetched_count` | number fetched |
| `failed_count` | number failed |
| `started_at` | run start timestamp |
| `completed_at` | run completion timestamp |

## Relationship To Main v2 Flow

Crawler may use source management data to decide what to crawl. After an article
is crawled, main pipeline data starts in Mongo:

```text
source_schema.sources
  -> crawler
  -> Mongo news_metadata/news_content
  -> entities-extraction
  -> content-summary
  -> publish
  -> Supabase public read model
```

Serving path:

```text
frontend -> backend-api -> Supabase public read model
```

Serving path does not include `source_schema`.

## Debug Checklist

Crawler not discovering articles:

1. Check source exists and `enabled=true`.
2. Check `allowed_domains`.
3. Check `rss_url`/source URL.
4. Check `crawl_interval_minutes` and `last_discovered_at`.

Crawler batch failing:

1. Check `crawl_batches.status`.
2. Compare `discovered_count`, `fetched_count`, `failed_count`.
3. Inspect crawler logs for source-specific failures.

## Schema Change Rule

Changes here should not require frontend/backend public API changes unless those
changes affect what crawler writes into Mongo and what publish later materializes.

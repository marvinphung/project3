# Database Overview

## Purpose

Tai lieu nay mo ta database architecture cua FootballPulse v2. Doc file nay de
hieu vi sao du an dung ca MongoDB va Supabase PostgreSQL, data di qua tung DB
nhu the nao, va service nao duoc phep doc/ghi DB nao.

Chi tiet:

- `docs/version2/database/mongo-pipeline-store.md`
- `docs/version2/database/supabase-postgres-read-model.md`
- `docs/version2/database/source-management-schema.md`

## Database Roles

FootballPulse v2 tach DB thanh hai vai tro:

```text
MongoDB:
  pipeline working store
  luu raw-ish crawl data, extracted entities, summary intermediate

Supabase PostgreSQL:
  serving read model
  luu data da materialize cho backend API/frontend
```

Rule quan trong:

```text
frontend -> backend-api -> Supabase PostgreSQL
```

Backend API khong doc MongoDB. Neu frontend thieu data, can fix pipeline/publish
de PostgreSQL co du read model.

## End-To-End Data Movement

```text
crawler
  writes Mongo news_metadata
  writes Mongo news_content

entities-extraction-service
  reads Mongo news_metadata/news_content/canonical_entities
  updates Mongo news_content.filtered_content
  writes Mongo news_entities

content-summary-service
  reads Mongo news_metadata/news_content/news_entities
  writes Mongo entity_timeline_summaries

publish
  reads Mongo canonical_entities/news_metadata/news_content/news_entities/entity_timeline_summaries
  writes Supabase entities/source_articles/entity_timeline_items/timeline_item_articles

backend-api
  reads Supabase only

frontend
  reads backend-api only
```

## Ownership Matrix

| Data object | Database | Owner | Consumers |
| --- | --- | --- | --- |
| `canonical_entities` | MongoDB | entities catalog import / entities-extraction | entities-extraction, publish |
| `news_metadata` | MongoDB | crawler | entities-extraction, content-summary, publish |
| `news_content.content` | MongoDB | crawler | entities-extraction, content-summary, publish |
| `news_content.filtered_content` | MongoDB | entities-extraction | content-summary, publish |
| `news_entities` | MongoDB | entities-extraction | content-summary, publish |
| `entity_timeline_summaries` | MongoDB | content-summary | publish |
| `entities` | Supabase PostgreSQL | publish | backend-api |
| `source_articles` | Supabase PostgreSQL | publish | backend-api |
| `entity_timeline_items` | Supabase PostgreSQL | publish | backend-api |
| `timeline_item_articles` | Supabase PostgreSQL | publish | backend-api |
| `source_schema.sources` | PostgreSQL/source management | crawler admin/source management | crawler |
| `source_schema.crawl_batches` | PostgreSQL/source management | crawler | crawler/admin diagnostics |

## Timestamp Rules

`crawl_date` la timestamp pipeline chinh:

- content summary chia 3h UTC windows theo `news_metadata.crawl_date`
- popularity 24h tinh theo `news_metadata.crawl_date`
- publish dung `crawl_date` de set `source_articles.crawled_at`

`published_time` la timestamp cua publisher/source neu co. No huu ich cho display
hoac sorting phu, nhung khong la clock chinh cua summary pipeline.

## Idempotency Rules

Idempotency theo tung layer:

- Mongo `news_metadata`: unique `canonical_url`
- Mongo `news_entities`: one document per article `_id`
- Mongo `entity_timeline_summaries`: deterministic `_id` theo entity/window
- PostgreSQL `entities`: upsert theo canonical entity id va `(entity_type, slug)`
- PostgreSQL `source_articles`: upsert theo `canonical_url`
- PostgreSQL `entity_timeline_items`: upsert theo `(entity_id, window_start, window_end)`
- PostgreSQL `timeline_item_articles`: upsert theo `(timeline_item_id, article_id)`

Re-running pipeline phai an toan va khong tao duplicate read model.

## Freshness Rules

Home/top entity UI:

- doc `entities.mention_count_24h`
- value nay duoc publish tu distinct article mentions trong Mongo 24h gan nhat
- khong phu thuoc entity co timeline summary hay chua

Entity timeline UI:

- doc `entity_timeline_items`
- chi co data sau khi content-summary tao Mongo summary va publish materialize sang
  PostgreSQL

Latest articles UI:

- doc `source_articles`
- co the co article ke ca article chua co summary, mien publish da backfill source
  articles

## Environment

Production/local serving nen dung Supabase PostgreSQL URL:

```text
SUPABASE_DATABASE_URL=postgresql://...
```

Neu dung Supabase IPv4, session pooler URL la acceptable. Password co ky tu dac
biet phai percent-encode neu can.

Mongo pipeline store:

```text
FOOTBALLPULSE_MONGODB_URL=mongodb://...
FOOTBALLPULSE_MONGODB_DB=footballpulse_v2
```

## Debug Direction

Neu UI khong hien data:

1. Kiem tra backend API response.
2. Kiem tra Supabase read model table tuong ung.
3. Kiem tra publish da chay va co loi khong.
4. Kiem tra Mongo source collection tuong ung.
5. Kiem tra upstream service owner cua collection do.

Khong them Mongo fallback vao backend API.

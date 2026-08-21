# Supabase PostgreSQL Read Model

## Purpose

Supabase PostgreSQL la serving database cua FootballPulse v2. Backend API doc
du lieu tu day de phuc vu frontend. Data trong PostgreSQL duoc materialize boi
`publish` tu MongoDB pipeline store.

Backend API local va production deu doc Supabase PostgreSQL. Khong co local
PostgreSQL fallback cho serving.

## Tables

```text
entities
source_articles
entity_timeline_items
timeline_item_articles
```

## `entities`

Owner:

- `publish`

Consumers:

- `backend-api`
- indirectly `frontend`

Purpose:

- canonical entity directory
- top entities 24h
- slug routing
- alias search

Important columns:

| Column | Meaning |
| --- | --- |
| `id` | canonical entity UUID |
| `entity_type` | `PLAYER`, `CLUB`, `COACH`, `COMPETITION` |
| `canonical_name` | display name |
| `slug` | user-facing route slug |
| `aliases` | canonical aliases for search |
| `mention_count_24h` | distinct article count in last 24h |
| `last_seen_at` | latest crawl_date where entity appeared |
| `metadata` | extra JSONB |
| `created_at`, `updated_at` | audit timestamps |

Upsert keys:

- entity `id`
- `(entity_type, slug)` conflict handling

Popularity rule:

```text
mention_count_24h = number of distinct articles mentioning entity in last 24h
```

If one article mentions an entity 10 times, it still counts as 1.

Important:

- `mention_count_24h` must not be computed from `entity_timeline_items`.
- Top UI must show entities even if they do not have generated timeline summaries.

## `source_articles`

Owner:

- `publish`

Consumers:

- `backend-api`
- frontend latest news and article detail pages
- entity timeline source list

Purpose:

- serving read model for crawled source articles
- source list for timeline summaries

Important columns:

| Column | Meaning |
| --- | --- |
| `id` | article UUID from Mongo |
| `title` | article title |
| `url` | original URL |
| `canonical_url` | unique URL/upsert key |
| `source_name` | source display name |
| `domain_name` | source domain |
| `description` | source description |
| `image_url` | article image |
| `published_at` | source published time if available |
| `crawled_at` | Mongo `news_metadata.crawl_date` |
| `content_hash` | content hash from crawler |
| `slug` | article route slug |
| `body` | article body for detail page |
| `excerpt` | short excerpt |
| `language` | language code |
| `created_at`, `updated_at` | audit timestamps |

Upsert key:

- `canonical_url`

Body rule:

- publish should prefer useful body from Mongo `news_content`
- current publish may use `filtered_content` or `content` depending mapping
- UI should not call Mongo for article body

## `entity_timeline_items`

Owner:

- `publish`

Consumers:

- `backend-api`
- frontend entity detail timeline

Purpose:

- serving row for one generated timeline summary
- one entity + one 3h UTC window

Important columns:

| Column | Meaning |
| --- | --- |
| `id` | summary UUID from Mongo |
| `entity_id` | FK to `entities.id` |
| `window_start` | UTC 3h bucket start |
| `window_end` | UTC 3h bucket end |
| `title` | LLM generated timeline title |
| `summary` | LLM generated content |
| `article_count` | number of selected source articles |
| `key_entities_50` | legacy compatibility field |
| `key_entities_80` | legacy compatibility field |
| `created_at`, `updated_at` | audit timestamps |

Upsert key:

- `(entity_id, window_start, window_end)`

Important:

- Windows must be aligned to `00,03,06,09,12,15,18,21 UTC`.
- These rows only exist after content-summary and publish both succeed.

## `timeline_item_articles`

Owner:

- `publish`

Consumers:

- `backend-api`
- frontend timeline source list

Purpose:

- join table between generated timeline item and source articles used for that
  summary

Important columns:

| Column | Meaning |
| --- | --- |
| `timeline_item_id` | FK to `entity_timeline_items.id` |
| `article_id` | FK to `source_articles.id` |
| `position` | ordering from summary selected articles |
| `created_at` | audit timestamp |

Primary/upsert key:

- `(timeline_item_id, article_id)`

## Backend API Mapping

Top entities:

```text
GET /api/v2/entities/top
  reads entities
```

Entity search:

```text
GET /api/v2/entities/search
  reads entities.canonical_name and entities.aliases
```

Entity slug resolve:

```text
GET /api/v2/entities/by-slug/{entity_type}/{slug}
  reads entities
```

Entity timeline:

```text
GET /api/v2/entities/{entity_id}/timeline
  reads entities
  reads entity_timeline_items
  reads timeline_item_articles
  reads source_articles
```

Latest articles:

```text
GET /api/v2/articles
  reads source_articles
```

Article detail:

```text
GET /api/v2/articles/{id_or_slug}
  reads source_articles
```

## Deployment/Connection Rule

Render backend:

```text
SUPABASE_DATABASE_URL=postgresql://...
```

Local backend:

```text
SUPABASE_DATABASE_URL=postgresql://...
```

Vercel frontend:

```text
VITE_API_BASE_URL=https://<render-backend>.onrender.com
```

Local frontend:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Do not point frontend to Supabase directly.

## Debug Checklist

Home top entities empty:

1. Check `entities` table has rows.
2. Check `mention_count_24h > 0`.
3. Run publish to refresh popularity.
4. Check Mongo `news_entities` and `news_metadata.crawl_date`.

Entity slug page empty:

1. Check `entities.slug`.
2. Check backend slug endpoint.
3. Check `entity_timeline_items` for entity id.
4. If no timeline rows, run content-summary then publish.

Latest news empty:

1. Check `source_articles`.
2. Run publish/backfill source articles.
3. Check Mongo `news_metadata` and `news_content`.

Article source list empty:

1. Check `timeline_item_articles`.
2. Check timeline item id exists.
3. Check `source_articles` rows exist for mapped article ids.

## Schema Change Rule

Moi thay doi table/column/index can:

1. Update migration/schema SQL.
2. Update SQLAlchemy table definitions.
3. Update publisher mapping.
4. Update backend API query/contract if exposed.
5. Update frontend model if response shape changes.
6. Update docs nay.

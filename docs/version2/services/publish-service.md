# Publish Service

## Purpose

`publish` materialize du lieu pipeline tu MongoDB sang Supabase PostgreSQL read
model. Day la stage cuoi cua Airflow pipeline va la cau noi giua pipeline store
voi serving layer.

Publish khong tao summary moi va khong goi LLM.

## Position In Flow

```text
crawler -> entities-extraction-service -> content-summary-service -> publish
```

Airflow task tuong ung:

```text
footballpulse_pipeline.publish
```

CLI command:

```bash
python -m footballpulse_pipeline publish --limit 100
```

Docker command:

```bash
docker compose -f docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish --limit 100
```

Local `uv` command:

```bash
uv run python -m footballpulse_pipeline publish --limit 100
```

## Inputs

MongoDB:

- `canonical_entities`
- `news_metadata`
- `news_content`
- `news_entities`
- `entity_timeline_summaries`

PostgreSQL:

- Supabase connection string
- v2 public schema/tables

## Outputs

Supabase PostgreSQL:

- `entities`
- `source_articles`
- `entity_timeline_items`
- `timeline_item_articles`

MongoDB:

- update `entity_timeline_summaries.published_at`

## Read Model Tables

### `entities`

Purpose:

- canonical entity directory
- top entities ranking
- slug routing
- alias-backed search

Important fields:

- `id`
- `entity_type`
- `canonical_name`
- `slug`
- `aliases`
- `mention_count_24h`
- `last_seen_at`

`mention_count_24h` phai duoc tinh tu `news_entities` + `news_metadata` theo
distinct article count trong 24 gio gan nhat. Khong duoc tinh tu
`entity_timeline_items`, vi UI can hien entity hot ke ca khi entity chua co
summary moi.

### `source_articles`

Purpose:

- danh sach tin moi
- chi tiet bai viet
- source articles cua timeline item

Important fields:

- `id`
- `title`
- `slug`
- `url`
- `canonical_url`
- `source_name`
- `domain_name`
- `description`
- `body`
- `excerpt`
- `published_at`
- `crawled_at`
- `language`

### `entity_timeline_items`

Purpose:

- timeline item da duoc LLM tong hop cho mot entity trong mot window 3h UTC

Important fields:

- `id`
- `entity_id`
- `window_start`
- `window_end`
- `title`
- `summary`
- `article_count`

### `timeline_item_articles`

Purpose:

- mapping N-N giua timeline item va source articles da dung trong prompt
- giu `position` de UI hien source theo thu tu input/relevance

## Internal Pipeline

1. Refresh popularity scores:
   - doc `news_metadata` trong 24h gan nhat theo `crawl_date`
   - join `news_entities`
   - count distinct articles per canonical entity
   - upsert vao PostgreSQL `entities.mention_count_24h`
2. Backfill/update source articles tu `news_metadata` + `news_content`.
3. Lay summaries `status=COMPLETED` chua publish hoac trong limit.
4. Upsert entity.
5. Upsert source articles cho `article_ids` cua summary.
6. Upsert timeline item.
7. Upsert timeline-item/article mapping.
8. Mark Mongo summary `published_at`.

## Idempotency

- `entities`: upsert theo id va/hoac `(entity_type, slug)`.
- `source_articles`: upsert theo `canonical_url`.
- `entity_timeline_items`: upsert theo `(entity_id, window_start, window_end)`.
- `timeline_item_articles`: upsert theo `(timeline_item_id, article_id)`.

Re-running publish phai an toan va khong tao duplicate.

## Serving Contract

Sau publish, backend API phai co du data trong Supabase de tra:

- top entities trong 24h
- entity search theo canonical name hoac alias
- entity timeline theo id/slug
- latest articles
- article detail/source

Backend API khong duoc fallback sang Mongo neu PostgreSQL thieu data. Neu UI thieu
data, sua publisher/read model truoc.

## Non-Goals

- Khong crawl.
- Khong extract entity.
- Khong call LLM.
- Khong chua business logic UI.

## Debug Checklist

Neu frontend khong co top entities:

1. Kiem tra PostgreSQL `entities.mention_count_24h` co > 0 khong.
2. Kiem tra publish da chay `refresh_popularity_scores` khong.
3. Kiem tra Mongo `news_entities` trong 24h co canonical mentions khong.
4. Kiem tra `news_metadata.crawl_date` co nam trong 24h gan nhat khong.

Neu entity detail co entity nhung khong co timeline:

1. Kiem tra Mongo `entity_timeline_summaries` co summary cho entity/window khong.
2. Kiem tra summary `status=COMPLETED`.
3. Kiem tra `entity_timeline_items` trong Supabase co row cho entity id khong.
4. Kiem tra `timeline_item_articles` co mapping khong.

Neu article detail thieu body/excerpt:

1. Kiem tra `source_articles.body` trong PostgreSQL.
2. Kiem tra Mongo `news_content.content` va `filtered_content`.
3. Chay publish/backfill source articles lai.

## Safe Changes

Co the sua trong boundary publish:

- Mongo to PostgreSQL mapping
- PostgreSQL upsert logic
- popularity refresh
- source article backfill
- slug materialization

Khong nen sua o day:

- LLM prompt/output
- extraction threshold
- frontend layout
- Airflow schedule semantics

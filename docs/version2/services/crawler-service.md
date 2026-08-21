# Crawler Service

## Purpose

`crawler` la service dau tien trong pipeline FootballPulse v2. Service nay lay
tin bong da tu cac source da cau hinh, chuan hoa URL, tach metadata va clean
article content, roi luu vao MongoDB pipeline store.

Crawler chi tao du lieu bai viet dau vao. No khong extract entity, khong goi LLM,
khong tao timeline va khong ghi Supabase PostgreSQL.

## Position In Flow

```text
crawler -> entities-extraction-service -> content-summary-service -> publish
```

Airflow task tuong ung:

```text
footballpulse_pipeline.crawl
```

CLI command:

```bash
python -m footballpulse_pipeline crawl --max-articles 100
```

Docker command:

```bash
docker compose -f docker-compose.v2.yml run --rm crawler python -m footballpulse_pipeline crawl --max-articles 100
```

Local `uv` command:

```bash
uv run python -m footballpulse_pipeline crawl --max-articles 100
```

## Inputs

- source configuration trong repo/env
- HTTP/RSS/source pages tu cac football news domains
- MongoDB connection
- Kafka connection neu event publish duoc bat

## Outputs

MongoDB:

- `news_metadata`
- `news_content`

Kafka:

- topic `news.crawled.v1` neu event publishing duoc dung

## Mongo Documents

### `news_metadata`

Owner: `crawler`.

Noi dung chinh:

- article `_id`
- `url`
- `canonical_url`
- `domain_name`
- `source_name`
- `title`
- `description`
- `published_time`
- `crawl_date`
- `image_url`
- `content_hash`
- `language`

`crawl_date` la timestamp quan trong cho cac stage sau. `content-summary-service`
dung `crawl_date` de chia bucket 3 gio UTC.

### `news_content`

Owner ban dau: `crawler`.

Noi dung chinh:

- article `_id`
- `content`
- `cleaned_at`
- `extractor`
- `extraction_status`

`filtered_content` va `filtered_at` khong do crawler tao. Hai field nay thuoc
boundary cua `entities-extraction-service`.

## Internal Pipeline

1. Discover article URLs tu source.
2. Normalize/canonicalize URL de tranh duplicate.
3. Fetch HTML.
4. Extract readable content bang primary extractor.
5. Fallback sang extractor khac neu primary khong du noi dung.
6. Build `news_metadata`.
7. Build `news_content`.
8. Upsert vao Mongo theo canonical URL/content hash.
9. Optionally publish `news.crawled.v1`.

## Idempotency

- `canonical_url` la key de tranh duplicate article.
- `content_hash` giup phat hien noi dung lap.
- Re-running crawler khong duoc tao duplicate cho cung canonical URL.

## Downstream Contract

`entities-extraction-service` mong doi:

- article co document trong `news_metadata`
- article co document trong `news_content`
- `news_content.content` co clean text du de extract

`content-summary-service` ve sau mong doi:

- `news_metadata.crawl_date` hop le
- article da co `news_entities`
- article da co `filtered_content` neu canonical alias replacement can thiet

## Non-Goals

- Khong extract entities.
- Khong replace aliases.
- Khong tinh popularity.
- Khong goi LLM.
- Khong publish Supabase.
- Khong phuc vu frontend.

## Operational Notes

- Source failures nen duoc log theo source/domain de debug nhanh.
- Crawler co the chay scheduled trong Airflow hoac manual bang CLI.
- Neu source thay doi HTML, chi sua extraction/source adapter o service nay;
  khong sua downstream service de compensate raw crawl bug.

## Debug Checklist

Neu khong thay bai moi sau khi crawl:

1. Kiem tra `news_metadata` co document moi theo `crawl_date` khong.
2. Kiem tra `news_content` co document cung `_id` khong.
3. Kiem tra `canonical_url` co bi duplicate nen upsert vao bai cu khong.
4. Kiem tra extractor co tra `extraction_status=FAILED` khong.
5. Kiem tra source adapter co fetch duoc HTML khong.

Neu entities-extraction khong xu ly bai:

1. Kiem tra bai co trong `news_metadata`.
2. Kiem tra bai co trong `news_content`.
3. Kiem tra bai da co `news_entities` nen bi skip khong.

## Safe Changes

Co the sua trong boundary crawler:

- source adapter
- URL normalization
- content extraction fallback
- metadata mapping
- crawl logging/retry

Khong nen sua trong crawler:

- entity extraction threshold/model
- canonical entity scoring
- summary prompt
- PostgreSQL read model

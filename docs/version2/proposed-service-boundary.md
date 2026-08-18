# Proposed Service Boundary

## Muc tieu

Version 2 tach du an theo noi chay thuc te:

- Frontend deploy len Vercel.
- Backend API deploy len Render.
- Crawl/processing/enrichment/publisher chay local de tao du lieu moi.
- MongoDB local luu du lieu crawl va xu ly.
- Supabase PostgreSQL luu du lieu product de Backend API phuc vu giao dien.

Backend production khong connect MongoDB, khong crawl, khong enrich AI, khong
chay Airflow/Kaggle.

Kafka va Airflow van thuoc local pipeline:

- Airflow dieu phoi crawl/process/publish.
- Kafka handoff article moi giua cac buoc pipeline, theo pattern producer/consumer
  cua `news-aggregator`.
- `news-aggregator` dung Prefect thay vi Airflow, nen V2 chi hoc cach chia flow,
  khong copy implementation scheduler 1:1.

## 1. Cau truc thu muc de xuat

```text
project3/
├── apps/
│   ├── backend-api/
│   └── frontend/
├── pipeline/
│   ├── crawler/
│   ├── processor/
│   └── publisher/
├── packages/
│   ├── mongo-models/
│   ├── supabase-models/
│   └── shared/
├── docs/
│   ├── version1/
│   └── version2/
└── scripts/
```

## 2. `apps/frontend`

Vai tro:

- React/Vite app deploy Vercel.
- Chi goi HTTP API cua `apps/backend-api`.
- Khong connect Supabase truc tiep.
- Khong biet MongoDB, crawler, processor, Kaggle.

Env production:

```text
VITE_BACKEND_API_URL=https://footballpulse-api.onrender.com
```

Du lieu duoc phep dung:

- article list/detail tu Backend API
- story detail
- entity detail
- timeline
- publications

Khong co logic:

- crawl trigger
- AI enrichment
- Mongo query
- Supabase direct query

## 3. `apps/backend-api`

Vai tro:

- FastAPI service deploy Render.
- Doc Supabase PostgreSQL.
- Expose API cho frontend.
- Co the co admin/editor endpoint nhe neu can sua publication, nhung khong xu ly
  pipeline crawl.

Dependencies:

```text
FastAPI
Pydantic
SQLAlchemy or supabase-py
PostgreSQL/Supabase
```

Env production:

```text
SUPABASE_DATABASE_URL=postgresql://...
BACKEND_CORS_ORIGINS=https://your-vercel-app.vercel.app
```

API surface dau tien:

```text
GET /health
GET /api/v1/articles
GET /api/v1/articles/{id}
GET /api/v1/publications
GET /api/v1/publications/{slug}
GET /api/v1/stories
GET /api/v1/stories/{id}
GET /api/v1/stories/{id}/timeline
GET /api/v1/entities
GET /api/v1/entities/{type}/{slug}
GET /api/v1/entities/{type}/{slug}/timeline
```

Nguyen tac:

- API chi tra data da materialize trong Supabase.
- API khong doc Mongo.
- API khong goi AI.
- API khong trigger crawl.
- List endpoint co pagination.
- Error response thong nhat.

## 4. `pipeline/crawler`

Vai tro:

- Chay local.
- Doc RSS/source config local.
- Fetch HTML.
- Extract metadata/content.
- Ghi Mongo:
  - `news_metadata`
  - `news_content`

Input:

```text
RSS_URLS
MONGODB_URL
MONGODB_DB
```

Output:

```text
news_metadata._id = uuid5(canonical_news_url)
news_content._id = same article_id
```

Khong lam:

- khong ghi Supabase truc tiep
- khong tao Story
- khong goi backend API

## 5. `pipeline/processor`

Vai tro:

- Chay local sau crawler.
- Doc Mongo `news_metadata` + `news_content`.
- Chay entity extraction, embedding optional, AI enrichment/Kaggle.
- Ghi Mongo:
  - `news_entities`
  - `news_enrichments`
  - `news_embeddings` neu can

Input:

```text
MONGODB_URL
MONGODB_DB
KAGGLE_USERNAME
KAGGLE_KEY
AI_MODEL_CONFIG
```

Output:

```text
news_entities._id = article_id
news_enrichments._id = article_id
news_embeddings._id = article_id
```

Khong lam:

- khong expose public API
- khong deploy Render
- khong ghi frontend-facing table neu enrichment chua validate

## 6. `pipeline/publisher`

Vai tro:

- Chay local sau processor.
- Doc Mongo da xu ly.
- Transform sang Supabase product schema.
- Upsert vao Supabase PostgreSQL.

Input:

```text
MONGODB_URL
MONGODB_DB
SUPABASE_DATABASE_URL
```

Mapping:

```text
news_metadata    -> sources, articles
news_entities    -> entities, entity_aliases, story_entities
news_enrichments -> stories, story_sources, claims, timeline_entries, publications
```

Nguyen tac upsert:

- `article_id` la khoa noi giua Mongo va Supabase.
- `articles.id = news_metadata._id`.
- Publisher co the chay lai nhieu lan ma khong tao duplicate.
- Chi sync document co du `news_metadata`, `news_content`, va `news_enrichments`
  hop le.

Khong lam:

- khong luu log vao DB
- khong luu batch/job state
- khong expose public API

## 7. `packages/mongo-models`

Vai tro:

- Chua Beanie/Pydantic Document models cho Mongo local.
- Dung boi `pipeline/crawler` va `pipeline/processor`.

Models:

```text
NewsMetadata
NewsContent
NewsEntities
NewsEnrichments
NewsEmbeddings
```

Khong import:

- FastAPI backend API
- Supabase repository
- frontend types

## 8. `packages/supabase-models`

Vai tro:

- Chua SQLAlchemy tables/Pydantic DTO hoac migration helpers cho Supabase.
- Dung boi `apps/backend-api` va `pipeline/publisher`.

Tables:

```text
sources
articles
entities
entity_aliases
stories
story_entities
story_sources
claims
timeline_entries
publications
```

Khong import:

- Mongo models
- crawler internals
- AI/Kaggle logic

## 9. `packages/shared`

Vai tro:

- Logic thuc su dung chung, nho va on dinh.

Nen de:

```text
canonicalize_news_url()
article_id_from_url()
slugify()
datetime helpers
common enums
```

Khong nen de:

```text
database repositories
service container
business pipeline orchestration
framework-specific app code
```

## 10. Flow runtime version 2

```text
Local:
Airflow -> pipeline/crawler -> Mongo -> Kafka news.crawled.v1
Kafka news.crawled.v1 -> pipeline/processor -> Mongo -> Kafka news.enriched.v1
Kafka news.enriched.v1 -> pipeline/publisher -> Supabase PostgreSQL

Production:
Vercel frontend -> Render backend-api -> Supabase PostgreSQL
```

## 11. Pham vi refactor sau khi chap nhan

Thu tu nen lam:

1. Tao `packages/shared` voi URL canonicalization va UUIDv5 article ID.
2. Tao `packages/mongo-models` theo schema da chot.
3. Tao `packages/supabase-models` va migrations Supabase.
4. Dinh nghia Kafka DTO/topic toi thieu cho local pipeline.
5. Tach local pipeline thanh `pipeline/crawler`, `pipeline/processor`,
   `pipeline/publisher`.
6. Tao Airflow DAG dieu phoi crawl/process/publish.
7. Tach backend API sang `apps/backend-api`, chi doc Supabase.
8. Di chuyen frontend sang `apps/frontend`, chi goi backend URL.
9. Xoa dan service/outbox/batch DB-state code cu neu khong con duoc dung.

## 12. Dieu can tranh

- Khong de backend production phu thuoc Mongo local.
- Khong de frontend query Supabase truc tiep.
- Khong giu Kafka/Airflow/job state trong DB product schema.
- Khong de Airflow DAG chua business logic tung article.
- Khong tao shared package qua lon lam moi module import lan nhau.
- Khong refactor het mot lan; can cat theo boundary tren.

# Proposed Technology Stack

## Muc tieu

Version 2 uu tien it thanh phan, de deploy va de theo doi:

- Frontend tren Vercel.
- Backend API tren Render.
- Supabase PostgreSQL la database production cho API/UI.
- MongoDB local la database crawl/processing.
- Pipeline crawl/process/publish chay local.

Kafka va Airflow van nam trong local pipeline. Chung khong nam trong backend
production, frontend production, hoac Supabase product schema.

`news-aggregator` dung Kafka cho handoff ingestion va dung Prefect cho scheduling.
Version 2 hoc pattern flow split do, nhung implement scheduler bang Airflow vi du
an hien tai can Airflow.

## 1. Frontend

Thu muc:

```text
apps/frontend
```

Cong nghe:

```text
React
TypeScript
Vite
React Router
TanStack Query optional
CSS hien co hoac Tailwind neu can refactor UI sau
```

Deploy:

```text
Vercel
```

Env:

```text
VITE_BACKEND_API_URL=https://<render-backend-domain>
```

Ly do:

- Repo hien tai da dung React/Vite, khong can doi framework.
- Vercel phu hop static SPA.
- Frontend chi can HTTP client goi backend, khong can SDK Supabase.

Khong dung:

```text
Supabase client in browser
MongoDB client
AI/Kaggle client
Crawler trigger
```

## 2. Backend API

Thu muc:

```text
apps/backend-api
```

Cong nghe:

```text
Python 3.12
FastAPI
Pydantic
SQLAlchemy Core/ORM
psycopg
Uvicorn
```

Deploy:

```text
Render Web Service
```

Database:

```text
Supabase PostgreSQL
```

Env:

```text
SUPABASE_DATABASE_URL=postgresql://...
BACKEND_CORS_ORIGINS=https://<vercel-domain>,http://localhost:5173
```

Ly do:

- Codebase hien tai da co FastAPI/Pydantic/SQLAlchemy.
- Backend chi query Postgres nen khong can Supabase SDK.
- SQLAlchemy giup query join `stories`, `entities`, `timeline_entries`,
  `publications` ro rang va test duoc.
- Render chay Python web service don gian.

Khong dung trong backend API:

```text
MongoDB
Beanie
Motor
Kafka
Airflow
Kaggle
GLiNER
BGE
Qwen
```

## 3. Supabase PostgreSQL

Vai tro:

- Production read database cho Backend API.
- Luu schema product da chot trong `docs/version2/proposed-db-schema.md`.

Cong nghe:

```text
Supabase PostgreSQL
SQL migrations
PostgreSQL full-text search optional
pgvector optional, chi them khi can semantic search production
```

Ly do:

- De deploy backend/frontend ma khong can host Mongo production.
- Supabase co managed PostgreSQL, dashboard va connection string nhanh cho do an.
- Product data co quan he ro: `stories`, `entities`, `claims`, `timeline`.

Khong dua vao Supabase:

```text
raw_html
raw_model_output
pipeline logs
batch/job state
local crawl attempts
```

## 4. Local MongoDB

Vai tro:

- Luu du lieu crawl va xu ly trung gian.
- Chi pipeline local connect.

Cong nghe:

```text
MongoDB
Motor
Beanie
Pydantic
```

Ly do:

- Giong pattern `news-aggregator`.
- Phu hop document output tu crawler, entity extraction va AI enrichment.
- `_id = uuid5(canonical_news_url)` giup dedupe theo URL don gian.

Collections:

```text
news_metadata
news_content
news_entities
news_enrichments
news_embeddings optional
```

## 5. Local Pipeline

Thu muc:

```text
pipeline/crawler
pipeline/processor
pipeline/publisher
airflow/dags
```

Cong nghe chung:

```text
Python 3.12
Pydantic
httpx/aiohttp
BeautifulSoup
Trafilatura
Motor
Beanie
Kafka client
```

### `pipeline/crawler`

Them:

```text
feedparser optional
curl_cffi optional neu can bypass mot so site
cloudscraper optional neu source bi anti-bot nhe
confluent-kafka or aiokafka
```

Chuc nang:

- Doc RSS/source config.
- Moi source check toi da 500 URL candidate moi run.
- Dedupe bang `article_id = uuid5(canonical_url)` truoc khi fetch.
- Fetch article bang async fallback stack.
- Extract metadata/content bang Trafilatura, JSON-LD, OpenGraph, BeautifulSoup.
- Ghi Mongo `news_metadata`, `news_content`.
- Publish Kafka event/topic cho article moi da crawl.

Concurrency de xuat:

```text
global_fetch_concurrency: 10
per_domain_concurrency: 2
scheduled step2_fetch_budget_per_crawl_command: 100
bootstrap step2_fetch_budget_per_crawl_command: 500
```

Browser automation nhu Playwright/Patchright chi bat theo source khi HTTP fallback
khong du, khong dung mac dinh.

Crawler runtime duoc tach 2 pha:

```text
Step 1: discovery / metadata seeding
Step 2: content extraction / Kafka handoff
```

Kafka topic de xuat:

```text
news.crawled.v1
```

### `pipeline/processor`

Them:

```text
GLiNER
sentence-transformers optional
Kaggle CLI
OpenAI compatible client optional neu dung LLM API
confluent-kafka or aiokafka
```

Chuc nang:

- Consume Kafka topic `news.crawled.v1` hoac fallback scan Mongo khi replay.
- Extract entities song song theo article.
- Chay AI enrichment/Kaggle.
- Validate output toi thieu.
- Ghi Mongo `news_entities`, `news_enrichments`, optional `news_embeddings`.
- Publish Kafka event/topic khi enrichment validated.

Concurrency va Kaggle:

```text
entity_workers: 4-8
kaggle_input: all articles with content exists and validated enrichment missing
kaggle_artifact_dir: .tmp/kaggle-runs/<timestamp>/
```

Kaggle dataset nen gom toan bo backlog chua enrichment trong mot lan upload de
tan dung GPU. Khong luu `batch_id`/kernel run state vao DB.

Kafka topic de xuat:

```text
news.enriched.v1
```

### `pipeline/publisher`

Them:

```text
SQLAlchemy
psycopg
confluent-kafka or aiokafka
```

Chuc nang:

- Consume Kafka topic `news.enriched.v1` hoac fallback scan Mongo khi replay.
- Upsert Supabase PostgreSQL.
- Build `articles`, `entities`, `stories`, `claims`, `timeline_entries`,
  `publications`.

Concurrency de xuat:

```text
publisher_workers: 4-8
```

Moi write vao Supabase phai idempotent bang primary key/unique key.

### `airflow/dags`

Cong nghe:

```text
Apache Airflow
PythonOperator or TaskFlow API
```

Chuc nang:

- Schedule crawl flow.
- Trigger processor flow sau crawl.
- Trigger publisher flow sau processor.
- Khong xu ly tung article trong Airflow task.
- Khong luu batch/job state vao product DB.
- Khong deploy cung backend Render.

Schedule de xuat:

```text
footballpulse_crawl      */30 * * * *
footballpulse_process    trigger-after-crawl, fallback */30 * * * *
footballpulse_publish    trigger-after-process, fallback */15 * * * *
footballpulse_reconcile  0 3 * * *
```

Tat ca DAG crawl/process/publish nen dung `catchup=False` va `max_active_runs=1`.

## 6. Shared Packages

### `packages/shared`

Cong nghe:

```text
Python package thuan
Pydantic neu can DTO chung
```

Chua:

```text
canonicalize_news_url()
article_id_from_url()
slugify()
common enums
datetime helpers
```

### `packages/mongo-models`

Cong nghe:

```text
Beanie
Motor
Pydantic
```

Chua Mongo documents:

```text
NewsMetadata
NewsContent
NewsEntities
NewsEnrichments
NewsEmbeddings
```

### `packages/supabase-models`

Cong nghe:

```text
SQLAlchemy
Pydantic response DTOs optional
Alembic optional
```

Chua:

```text
Postgres table definitions
read query helpers
migration SQL
```

## 7. Tooling

Python package/dependency:

```text
uv
pyproject.toml per app/package hoac workspace pyproject
pytest
ruff
mypy optional
```

Frontend:

```text
npm or pnpm
vite
typescript
eslint optional
```

Local dev:

```text
docker compose for MongoDB, Kafka, Airflow, optionally local Postgres test
.env for local pipeline
.env.production examples for Vercel/Render
```

## 8. Technologies to Keep Local Only

Nhung thanh phan nay van co trong V2, nhung chi thuoc local pipeline:

```text
Kafka
Airflow
Kaggle CLI
GLiNER/BGE local models
MongoDB local
```

Khong dua cac thanh phan nay vao Render backend, Vercel frontend, hoac Supabase
product schema.

## 9. Technologies to Remove From V2 MVP

Nhung thanh phan nay khong can cho target architecture version 2:

```text
outbox pattern
processed_events table/collection
ai_batch_jobs
ai_batch_locks
ai_enrichment_work
multi-service internal HTTP mesh
local API gateway as composition service
MongoDB transactions for outbox/event flow
```

Khong dua lai tai lieu/history V1 vao target architecture V2.

## 10. Ly do khong chon stack khac

### Node/Express backend

Khong chon cho MVP vi backend hien tai da co nhieu Python domain/query code, pipeline
cung Python. Dung Python giup giam context switch.

### Supabase direct from frontend

Khong chon vi frontend se phu thuoc DB schema, kho them business response shape,
kho che giau table/internal fields, va phai dua anon policy/RLS vao som.

### MongoDB production

Khong chon vi yeu cau hien tai la BE production doc Supabase. Mongo local chi lam
pipeline store.

### Prefect

Khong chon Prefect du `news-aggregator` dang dung Prefect. Project nay da co
Airflow va user yeu cau giu Airflow, nen chi hoc cach repo cu chia flow:

```text
crawl flow -> enrichment flow -> publish/read flow
```

roi implement bang Airflow DAG.

## 11. Ket luan

Stack version 2 nen la:

```text
Frontend: React + TypeScript + Vite -> Vercel
Backend API: FastAPI + Pydantic + SQLAlchemy + psycopg -> Render
Production DB: Supabase PostgreSQL
Local DB: MongoDB + Beanie + Motor
Local orchestration: Airflow
Local messaging: Kafka
Local pipeline: Python services crawl -> process -> publish
```

Day la stack nho hon version 1, phu hop hon voi yeu cau: local tao du lieu, Supabase
luu data product, Render/Vercel chi phuc vu giao dien.

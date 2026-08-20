# FootballPulse v2

FootballPulse v2 hien tai duoc dinh huong theo flow:

```text
crawler
-> entities-extraction-service
-> content-summary-service
-> publish
-> backend-api
-> frontend
```

Trong repo hien tai, code duoc giu lai cho:

- `crawler-service`
- `entities-extraction-service`
- `publisher-service`
- `api-gateway`
- `frontend`
- `airflow`
- `kafka`

Phan `content-summary-service` se duoc viet lai sau, nen code enrichment/intelligence
cu da bi loai bo khoi repo.

## Source Of Truth

Tai lieu nguon cho architecture hien tai:

- [docs/version2/source-of-truth-entity-timeline-architecture.md](/home/pmv259/Documents/personal-projects/project3/docs/version2/source-of-truth-entity-timeline-architecture.md)

Neu co mau thuan giua cac docs, uu tien tai lieu tren.

## High-Level Architecture

### 1. `crawler`

- crawl metadata va cleaned content
- luu vao Mongo:
  - `news_metadata`
  - `news_content`
- publish `news.crawled.v1`

### 2. `entities-extraction-service`

- lay cac bai co `news_metadata` nhung chua co `news_entities`
- extract named entities
- ghi vao `news_entities`

### 3. `content-summary-service`

- se duoc lam moi theo mo hinh timeline theo tung entity
- moi entity co timeline rieng
- moi timeline item duoc tong hop tren cua so 3 gio

### 4. `publish`

- doc du lieu can publish tu Mongo
- materialize sang Supabase PostgreSQL

### 5. Serving

- `backend-api` doc Supabase
- `frontend` goi `backend-api`
- frontend deploy tren Vercel
- backend deploy tren Render

## Local Stack

Ha tang local chinh:

- MongoDB
- Kafka
- PostgreSQL
- Airflow

Service/runtime local chinh:

- `api`
- `crawler`
- `entities-extraction`
- `publisher`

## Quick Start

```bash
cp .env.example .env
docker compose -f docker-compose.v2.yml up -d --build
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Them chi tiet van hanh xem:

- [docs/HUONG_DAN_CHAY.md](/home/pmv259/Documents/personal-projects/project3/docs/HUONG_DAN_CHAY.md)
- [docs/version2/local-development.md](/home/pmv259/Documents/personal-projects/project3/docs/version2/local-development.md)

# FootballPulse

FootballPulse là pipeline local-first để crawl tin bóng đá, xử lý dữ liệu trong
MongoDB, rồi materialize read model public lên PostgreSQL/Supabase cho backend
API và frontend.

Kiến trúc `version2` hiện tại:

```text
Local:
Airflow -> crawler -> Mongo -> Kafka news.crawled.v1
Kafka news.crawled.v1 -> processor -> Mongo -> Kaggle enrichment -> Mongo news_enrichments
Mongo news_enrichments -> publisher -> PostgreSQL/Supabase

Serving:
Frontend -> API /api/v2 -> PostgreSQL/Supabase
```

## Trạng thái hiện tại

Đã verify local tính đến Tuesday, August 18, 2026:

- `docker-compose.v2.yml` chạy được cho MongoDB, Kafka, PostgreSQL local.
- `footballpulse_pipeline crawl` chạy được với nguồn live và ghi vào
  `news_metadata`, `news_content`, đồng thời publish `news.crawled.v1`.
- `footballpulse_pipeline process` xử lý được `news_entities`.
- `footballpulse_pipeline publish` publish được dữ liệu validated từ Mongo sang
  PostgreSQL/Supabase.
- `scripts/smoke-v2-api.py` pass trên `/api/v2`.
- Focused API tests pass.

Phần đang có phụ thuộc external queue:

- Kaggle enrichment đã đi được tới bước upload dataset và push kernel.
- Runtime local hiện phải chờ GPU queue phía Kaggle; vì vậy đây là phần dễ bị
  chậm hoặc pending ngoài hệ thống local.

## Quick Start

1. Tạo file môi trường:

```bash
cp .env.example .env
```

2. Điền các biến tối thiểu trong `.env`:

- `FOOTBALLPULSE_MONGODB_URL`
- `FOOTBALLPULSE_MONGODB_DB`
- `FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS`
- `SUPABASE_DB_HOST`
- `SUPABASE_DB_PORT`
- `SUPABASE_DB_NAME`
- `SUPABASE_DB_USER`
- `SUPABASE_DB_PASSWORD`
- `FOOTBALLPULSE_KAGGLE_DATASET_SLUG`
- `FOOTBALLPULSE_KAGGLE_KERNEL_SLUG`
- `FOOTBALLPULSE_KAGGLE_MODEL_SOURCE`
- `KAGGLE_USERNAME`
- `KAGGLE_API_TOKEN`

3. Sync workspace:

```bash
UV_CACHE_DIR=/tmp/footballpulse-uv-cache /home/pmv259/.local/bin/uv sync --all-packages --all-extras --group dev
```

4. Khởi động hạ tầng local:

```bash
docker compose -f docker-compose.v2.yml up -d --build
```

5. Xem runbook local:

- [Local Development V2](docs/version2/local-development.md)

## Lệnh chính

| Command | Mục đích |
| --- | --- |
| `python -m footballpulse_pipeline crawl --source 'The Guardian Football' --max-articles 1` | Crawl live một nguồn |
| `python -m footballpulse_pipeline process --limit 1` | Consume/process backlog local |
| `python -m footballpulse_pipeline publish --limit 10` | Publish từ Mongo sang Postgres |
| `python scripts/smoke-v2-api.py` | Smoke API v2 trên DB thật |
| `docker compose -f docker-compose.v2.yml ps` | Kiểm tra hạ tầng local |

Khi chạy trực tiếp, nên dùng `PYTHONPATH` hoặc cài workspace đầy đủ qua `uv sync`
để `footballpulse_pipeline` và các packages nội bộ được import đúng.

## Cấu trúc repository

```text
footballpulse/
├── airflow/            # DAG điều phối batch
├── docs/               # Thiết kế, quyết định và hướng dẫn vận hành
├── frontend/           # React web app
├── infrastructure/     # MongoDB, Kafka và database bootstrap
├── kaggle/             # AI enrichment notebook/runner
├── packages/           # Python package dùng chung
├── scripts/            # Crawl, smoke check và công cụ vận hành
├── services/           # Các Python service
├── tests/              # Cross-service và infrastructure tests
└── docker-compose.v2.yml
```

## Tài liệu

- [ADR version 2](docs/version2/adr-0001-version2-local-pipeline-supabase-serving.md)
- [DB schema version 2](docs/version2/proposed-db-schema.md)
- [Technology stack version 2](docs/version2/proposed-technology-stack.md)
- [Pipeline flow version 2](docs/version2/proposed-pipeline-flow.md)
- [API contract version 2](docs/version2/proposed-api-contract.md)
- [Service boundary version 2](docs/version2/proposed-service-boundary.md)
- [Implementation plan version 2](docs/version2/refactor-implementation-plan.md)
- [Local Development V2](docs/version2/local-development.md)

## Deploy FE / BE

Deployment target da chot cho `version2`:

- Frontend deploy len Vercel
- Backend API deploy len Render
- MongoDB, Kafka, Airflow, crawler va Kaggle van chay local
- PostgreSQL public read model dung Supabase

### Frontend -> Vercel

Project root:

- `frontend/`

Build settings:

- Install command: `npm install`
- Build command: `npm run build`
- Output directory: `dist`

Env toi thieu:

- `VITE_API_BASE_URL=https://<render-backend-domain>`

Frontend chi goi `/api/v2` tu backend, khong noi truc tiep Mongo, Kafka, Airflow
hay Kaggle.

### Backend API -> Render

Project root:

- `services/api-gateway/`

Recommended start command:

```bash
uv run footballpulse-api-v2
```

Neu Render khong dung workspace root lam runtime context, co the dung:

```bash
PYTHONPATH=services/api-gateway/src:services/content-service/src:packages/runtime-config/src uv run footballpulse-api-v2
```

Env toi thieu:

- `SUPABASE_DB_HOST`
- `SUPABASE_DB_PORT`
- `SUPABASE_DB_NAME`
- `SUPABASE_DB_USER`
- `SUPABASE_DB_PASSWORD`
- `FOOTBALLPULSE_API_ADMIN_TOKEN`
- `FOOTBALLPULSE_API_EDITOR_TOKEN`
- `FOOTBALLPULSE_API_JWT_SECRET`
- `FOOTBALLPULSE_API_ADMIN_USERNAME`
- `FOOTBALLPULSE_API_ADMIN_PASSWORD`
- `FOOTBALLPULSE_API_EDITOR_USERNAME`
- `FOOTBALLPULSE_API_EDITOR_PASSWORD`

Backend Render chi doc PostgreSQL/Supabase. Khong deploy MongoDB, Kafka,
Airflow, crawler hay Kaggle len Render.

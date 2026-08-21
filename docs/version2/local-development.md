# Local Development V2

Local development hien tai phai duoc hieu theo source-of-truth moi:

```text
Airflow-managed pipeline:
crawler -> entities-extraction-service -> content-summary-service -> publish

Serving layer:
backend-api -> frontend
```

Tai lieu nguon:

- [source-of-truth-entity-timeline-architecture.md](/home/pmv259/Documents/personal-projects/project3/docs/version2/source-of-truth-entity-timeline-architecture.md)

## What Still Exists In Code

- `crawler`
- `entities-extraction-service`
- `publish`
- `backend-api`
- `frontend`
- `airflow`
- `kafka`
- `content-summary-service`

`content-summary-service` tao timeline theo top 30 entities trong 24h gan nhat.
Moi entity/window chi gui toi da 5 `news_content.content` vao LLM, duoc chon
bang so lan target entity xuat hien trong `news_content.filtered_content`.
Mac dinh command `summary` backfill cac bucket 3h trong 7 ngay gan nhat va skip
entity/window da co summary `COMPLETED`.

## Sync Workspace

```bash
uv sync --all-packages --all-extras --group dev
```

## Start Infra

```bash
docker compose -f docker-compose.v2.yml up -d mongodb mongodb-init kafka
```

## Serving Database Rule

Backend API va publisher bat buoc dung Supabase qua `SUPABASE_DATABASE_URL`
hoac `SUPABASE_DB_HOST`.

Dieu nay ap dung cho ca local va production:

- backend local doc Supabase
- backend Render doc Supabase
- publisher local/Airflow day read model len Supabase
- repo khong con local PostgreSQL fallback cho serving read model

Frontend local chi khac o API base URL:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

Frontend tren Vercel dung backend Render:

```bash
VITE_API_BASE_URL=<Render backend public URL>
```

## Run Stages

Crawler:

```bash
python3 -m footballpulse_pipeline crawl --max-articles 10
```

Entities extraction:

```bash
python3 -m footballpulse_pipeline process --limit 10
```

Content summary:

```bash
python3 -m footballpulse_pipeline summary
```

Single summary window neu can replay/debug mot bucket cu the:

```bash
python3 -m footballpulse_pipeline summary \
  --window-start 2026-08-20T15:00:00Z \
  --window-end 2026-08-20T18:00:00Z
```

Publisher:

```bash
python3 -m footballpulse_pipeline publish --limit 20
```

Lenh nay publish len Supabase. Neu thieu Supabase env, command se fail fast.

API:

```bash
PYTHONPATH=packages/pipeline/src:packages/runtime-config/src:packages/event-contracts/src:services/api-gateway/src:services/crawler-service/src:services/entities-extraction-service/src:services/publisher-service/src python3 -m footballpulse_api_gateway.runtime_v2
```

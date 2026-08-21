# FootballPulse

FootballPulse is a football news intelligence pipeline. It crawls football news,
extracts canonical entities, generates per-entity timeline summaries, publishes a
PostgreSQL read model, and serves the UI through a backend API.

## Current Architecture

```text
Airflow-managed pipeline:
crawler -> entities-extraction -> content-summary -> publish

Serving layer:
frontend -> backend-api -> Supabase PostgreSQL
```

The pipeline uses MongoDB as the working store. The serving layer reads only from
Supabase PostgreSQL. Frontend and backend are intentionally outside the Airflow
pipeline.

## Services

| Service | Role | Main Storage |
| --- | --- | --- |
| `crawler` | Crawl metadata and clean article content. | MongoDB `news_metadata`, `news_content` |
| `entities-extraction` | Build `filtered_content`, extract entities, persist canonical mentions. | MongoDB `news_entities` |
| `content-summary` | Generate 3h UTC per-entity timeline summaries. | MongoDB `entity_timeline_summaries` |
| `publish` | Materialize Mongo pipeline data into PostgreSQL read model. | Supabase PostgreSQL |
| `backend-api` | Public API for frontend. | Supabase PostgreSQL only |
| `frontend` | React/Vite UI. | Backend API |
| `airflow` | Orchestrates the 4-step pipeline. | Docker Compose services |
| `kafka` | Crawl event transport for entity processing. | Local Kafka volume |

## Summary Selection Rule

`content-summary-service` processes fixed 3-hour UTC windows based on
`news_metadata.crawl_date`. For each window run, it selects entities by distinct
article count in the previous 24 hours:

- top 50 `PLAYER`
- top 30 `COACH`
- top 30 `CLUB`

For each selected entity/window, the LLM receives up to 5 articles with the
highest mention count of that entity in `news_content.filtered_content`, while
the prompt content itself uses `news_content.content`.

## Quick Start With Docker

```bash
cp .env.example .env
docker compose -f docker-compose.v2.yml up -d --build
```

Main local URLs:

- Backend API: `http://localhost:8000`
- Airflow: `http://localhost:8080`
- Frontend dev server: run separately from `frontend/`

```bash
cd frontend
npm install
npm run dev
```

## Run The Pipeline Manually

Docker:

```bash
docker compose -f docker-compose.v2.yml run --rm crawler python -m footballpulse_pipeline crawl --max-articles 100
docker compose -f docker-compose.v2.yml run --rm entities-extraction python -m footballpulse_pipeline process --limit 100
docker compose -f docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary --backfill-days 7
docker compose -f docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish --limit 100
```

Local Python with `uv`:

```bash
uv run python -m footballpulse_pipeline crawl --max-articles 100
uv run python -m footballpulse_pipeline process --limit 100
uv run python -m footballpulse_pipeline summary --backfill-days 7
uv run python -m footballpulse_pipeline publish --limit 100
```

## Run Serving Layer Locally

Backend API:

```bash
docker compose -f docker-compose.v2.yml up -d api
```

or:

```bash
uv run python -m footballpulse_api_gateway.runtime_v2
```

Frontend:

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Configuration

Copy `.env.example` to `.env` and fill required secrets:

- `SUPABASE_DATABASE_URL` or `SUPABASE_DB_*`
- `FOOTBALLPULSE_LLM_PROVIDER`
- `FOOTBALLPULSE_LLM_MODEL`
- `FOOTBALLPULSE_LLM_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`
- `FOOTBALLPULSE_API_JWT_SECRET`
- `FOOTBALLPULSE_API_CORS_ORIGINS`
- `VITE_API_BASE_URL`

For local entity extraction on CPU:

```env
NER_DEVICE=cpu
ENTITY_EXTRACTION_MIN_CONFIDENCE=0.95
```

## Deployment

Use [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment and full
command references for Docker, `uv`, Render, Vercel, Airflow, and Supabase.

## Source Of Truth Docs

- [Entity timeline architecture](docs/version2/source-of-truth-entity-timeline-architecture.md)
- [Local development notes](docs/version2/local-development.md)
- [Vietnamese run guide](docs/HUONG_DAN_CHAY.md)

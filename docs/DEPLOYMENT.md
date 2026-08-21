# Deployment

## Flow

```text
Airflow pipeline:
crawler -> entities-extraction -> content-summary -> publish

Serving:
frontend -> backend-api -> Supabase PostgreSQL
```

Backend API reads Supabase only. MongoDB/Kafka are only for the pipeline.

## Required Env

Copy:

```bash
cp .env.example .env
```

Fill these first:

```env
SUPABASE_DATABASE_URL=

FOOTBALLPULSE_LLM_PROVIDER=
FOOTBALLPULSE_LLM_MODEL=
FOOTBALLPULSE_LLM_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=

FOOTBALLPULSE_API_JWT_SECRET=
FOOTBALLPULSE_API_ADMIN_USERNAME=
FOOTBALLPULSE_API_ADMIN_PASSWORD=
FOOTBALLPULSE_API_CORS_ORIGINS=

VITE_API_BASE_URL=
```

Notes:

- Supabase IPv4: use the session pooler URL in `SUPABASE_DATABASE_URL`.
- No trailing slash for CORS/API URLs.
- Backend local and Render both read Supabase.
- Publisher local/Airflow both publish to Supabase.

## Docker Runbook

Start stack:

```bash
docker compose -f docker-compose.v2.yml up -d --build
```

Rebuild:

```bash
docker compose -f docker-compose.v2.yml build
```

Status/logs:

```bash
docker compose -f docker-compose.v2.yml ps
docker compose -f docker-compose.v2.yml logs -f api
docker compose -f docker-compose.v2.yml logs -f airflow-scheduler
```

Run each pipeline stage:

```bash
docker compose -f docker-compose.v2.yml run --rm crawler python -m footballpulse_pipeline crawl --max-articles 100
docker compose -f docker-compose.v2.yml run --rm entities-extraction python -m footballpulse_pipeline process --limit 100
docker compose -f docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary --backfill-days 7
docker compose -f docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish --limit 100
```

Run one summary window:

```bash
docker compose -f docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary \
  --window-start 2026-08-21T00:00:00Z \
  --window-end 2026-08-21T03:00:00Z
```

Stop stack:

```bash
docker compose -f docker-compose.v2.yml down
```

## uv Runbook

Use `uv run python -m ...`.

```bash
uv run python -m footballpulse_pipeline crawl --max-articles 100
uv run python -m footballpulse_pipeline process --limit 100
uv run python -m footballpulse_pipeline summary --backfill-days 7
uv run python -m footballpulse_pipeline publish --limit 100
```

Backend:

```bash
uv run python -m footballpulse_api_gateway.runtime_v2
```

Frontend:

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Airflow

Airflow UI:

```text
http://localhost:8080
```

Main DAG:

```text
footballpulse_pipeline
```

Schedule:

```env
FOOTBALLPULSE_V2_PIPELINE_SCHEDULE="5,35 * * * *"
```

Airflow should run on a Docker-capable machine, not Render.

## Render Backend

Create a Render Web Service:

```text
Language: Docker
Branch: main
Root Directory: blank
Docker Build Context Directory: .
Dockerfile Path: services/runtime.Dockerfile
Docker Command: python -m footballpulse_api_gateway.runtime_v2
Health Check Path: /health
Auto-Deploy: On Commit
```

Render env:

```env
PORT=8000
FOOTBALLPULSE_ENV=production
FOOTBALLPULSE_LOG_LEVEL=INFO
FOOTBALLPULSE_TIMEZONE=UTC
SUPABASE_DATABASE_URL=postgresql://...
FOOTBALLPULSE_API_JWT_SECRET=<32+ chars>
FOOTBALLPULSE_API_ADMIN_USERNAME=<admin-user>
FOOTBALLPULSE_API_ADMIN_PASSWORD=<admin-password>
FOOTBALLPULSE_API_CORS_ORIGINS=https://<vercel-app>.vercel.app
FOOTBALLPULSE_API_RATE_LIMIT=120
FOOTBALLPULSE_API_RATE_WINDOW_SECONDS=60
```

Check:

```bash
curl https://<render-service>.onrender.com/health
curl "https://<render-service>.onrender.com/api/v2/entities/top?limit=10&window=24h"
```

## Vercel Frontend

Vercel settings:

```text
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
Install Command: npm install
```

Vercel env:

```env
VITE_API_BASE_URL=https://<render-service>.onrender.com
```

The repo already has `frontend/vercel.json` for SPA rewrites.

## After Pipeline Run

Always publish after summary:

```bash
docker compose -f docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish --limit 100
```

Quick serving check:

```bash
curl "http://localhost:8000/api/v2/entities/top?limit=10&window=24h"
curl "http://localhost:8000/api/v2/articles?limit=5"
```

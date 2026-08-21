# FootballPulse Deployment Guide

This guide covers local operations, pipeline commands, and production deployment
for the current FootballPulse architecture.

## Architecture

```text
Pipeline managed by Airflow:
crawler -> entities-extraction -> content-summary -> publish

Serving:
frontend -> backend-api -> Supabase PostgreSQL
```

MongoDB and Kafka are pipeline infrastructure. Backend API and frontend are not
pipeline workers. Backend API reads Supabase PostgreSQL only.

## Required Accounts

- Supabase project with PostgreSQL
- Render web service for backend API
- Vercel project for frontend
- A machine that can run Docker Compose for the Airflow pipeline

Do not run the Airflow Docker pipeline on Render. The Airflow DAG uses Docker
Compose and the Docker socket, so it belongs on a VPS, EC2 instance, or local
server with Docker installed.

## Environment Variables

Start from:

```bash
cp .env.example .env
```

Required runtime values:

```env
FOOTBALLPULSE_ENV=production
FOOTBALLPULSE_LOG_LEVEL=INFO
FOOTBALLPULSE_TIMEZONE=UTC

SUPABASE_DATABASE_URL=postgresql://...

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

For Supabase IPv4 pooler, use the pooler URL in `SUPABASE_DATABASE_URL`.
Wrap the URL in quotes in `.env` if the password contains special characters.

## Docker Commands

Build all images:

```bash
docker compose -f docker-compose.v2.yml build
```

Start infrastructure, Airflow, and backend API:

```bash
docker compose -f docker-compose.v2.yml up -d --build
```

Show service status:

```bash
docker compose -f docker-compose.v2.yml ps
```

View logs:

```bash
docker compose -f docker-compose.v2.yml logs -f api
docker compose -f docker-compose.v2.yml logs -f airflow-scheduler
docker compose -f docker-compose.v2.yml logs -f content-summary
```

Stop local stack without deleting volumes:

```bash
docker compose -f docker-compose.v2.yml down
```

## Pipeline Commands With Docker

Run each pipeline stage manually:

```bash
docker compose -f docker-compose.v2.yml run --rm crawler python -m footballpulse_pipeline crawl --max-articles 100
docker compose -f docker-compose.v2.yml run --rm entities-extraction python -m footballpulse_pipeline process --limit 100
docker compose -f docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary --backfill-days 7
docker compose -f docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish --limit 100
```

Run one specific summary window:

```bash
docker compose -f docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary \
  --window-start 2026-08-21T00:00:00Z \
  --window-end 2026-08-21T03:00:00Z
```

Force recompute summary for the selected windows:

```bash
docker compose -f docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary --backfill-days 7 --force
```

## Pipeline Commands With uv

Use these commands when running directly on the host. `uv run python -m` is the
correct module form.

```bash
uv run python -m footballpulse_pipeline crawl --max-articles 100
uv run python -m footballpulse_pipeline process --limit 100
uv run python -m footballpulse_pipeline summary --backfill-days 7
uv run python -m footballpulse_pipeline publish --limit 100
```

Specific summary window:

```bash
uv run python -m footballpulse_pipeline summary \
  --window-start 2026-08-21T00:00:00Z \
  --window-end 2026-08-21T03:00:00Z
```

Backend API locally:

```bash
uv run python -m footballpulse_api_gateway.runtime_v2
```

Crawler:

```bash
uv run python -m footballpulse_pipeline crawl --max-articles 100
```

Entities extraction:

```bash
uv run python -m footballpulse_pipeline process --limit 100
```

Content summary:

```bash
uv run python -m footballpulse_pipeline summary --backfill-days 7
```

Publish:

```bash
uv run python -m footballpulse_pipeline publish --limit 100
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

The main DAG runs:

```text
crawl -> entities_extraction -> content_summary -> publish
```

Schedule is controlled by:

```env
FOOTBALLPULSE_V2_PIPELINE_SCHEDULE="5,35 * * * *"
```

Stage DAGs are for manual/debug usage only:

- `footballpulse_crawl`
- `footballpulse_process`
- `footballpulse_summary`
- `footballpulse_publish`

## Backend API On Render

Create a Render Web Service from the GitHub repository.

Recommended settings:

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

Render environment variables:

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

Do not add a trailing slash to `FOOTBALLPULSE_API_CORS_ORIGINS`.

Verify Render:

```bash
curl https://<render-service>.onrender.com/health
curl "https://<render-service>.onrender.com/api/v2/entities/top?limit=10&window=24h"
```

## Frontend On Vercel

Create a Vercel project from the repository and set:

```text
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
Install Command: npm install
```

Vercel environment variable:

```env
VITE_API_BASE_URL=https://<render-service>.onrender.com
```

Do not add a trailing slash to `VITE_API_BASE_URL`.

The repo includes `frontend/vercel.json` for Vite SPA routing:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "installCommand": "npm install",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

After changing `VITE_API_BASE_URL`, redeploy the Vercel project.

## Supabase/PostgreSQL

The publisher writes the read model used by backend/frontend. Backend does not
read MongoDB.

Apply schema/migrations as needed from:

```text
supabase/migrations/
```

After running summary, publish to Supabase:

```bash
docker compose -f docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish --limit 100
```

or:

```bash
uv run python -m footballpulse_pipeline publish --limit 100
```

## Frontend Local Development

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

Build:

```bash
cd frontend
npm run build
```

## Verification Checklist

After deploying backend:

```bash
curl https://<render-service>.onrender.com/health
curl "https://<render-service>.onrender.com/api/v2/entities/top?limit=10&window=24h"
```

After deploying frontend:

- open the Vercel URL
- check Home top entities
- open `/clb/<slug>`, `/cau-thu/<slug>`, `/hlv/<slug>`
- open `/tin-moi`
- search for an entity alias

After running the full pipeline:

```bash
docker compose -f docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish --limit 100
curl "http://localhost:8000/api/v2/entities/top?limit=10&window=24h"
```

## Rollback

Backend rollback:

```bash
git revert <bad-commit>
git push
```

Render will redeploy the reverted commit if auto-deploy is enabled.

Frontend rollback:

- use Vercel deployment history to promote the previous good deployment
- or revert the bad commit and push

Pipeline rollback:

- pause `footballpulse_pipeline` in Airflow
- revert the bad code
- rebuild Docker images
- resume the DAG after verification

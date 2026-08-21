# Local Development V2

Local development follows the current source-of-truth architecture:

```text
Airflow-managed pipeline:
crawler -> entities-extraction -> content-summary -> publish

Serving layer:
frontend -> backend-api -> Supabase PostgreSQL
```

Backend API and publisher always use Supabase PostgreSQL for the serving read
model. There is no local PostgreSQL fallback for backend serving data.

## Main References

- [Architecture source of truth](source-of-truth-entity-timeline-architecture.md)
- [Deployment and command guide](../DEPLOYMENT.md)

## Sync Workspace

```bash
uv sync --all-packages --all-extras --group dev
```

## Start Local Infrastructure

```bash
docker compose -f docker-compose.v2.yml up -d mongodb mongodb-init kafka
```

## Run Pipeline With Docker

```bash
docker compose -f docker-compose.v2.yml run --rm crawler python -m footballpulse_pipeline crawl --max-articles 100
docker compose -f docker-compose.v2.yml run --rm entities-extraction python -m footballpulse_pipeline process --limit 100
docker compose -f docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary --backfill-days 7
docker compose -f docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish --limit 100
```

## Run Pipeline With uv

```bash
uv run python -m footballpulse_pipeline crawl --max-articles 100
uv run python -m footballpulse_pipeline process --limit 100
uv run python -m footballpulse_pipeline summary --backfill-days 7
uv run python -m footballpulse_pipeline publish --limit 100
```

## Run Serving Locally

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

## Content Summary Rule

`content-summary-service` backfills fixed 3-hour UTC buckets by
`news_metadata.crawl_date`. It generates summaries for entities with the highest
distinct article count in the previous 24 hours:

- top 50 `PLAYER`
- top 30 `COACH`
- top 30 `CLUB`

For each entity/window, it sends up to 5 selected `news_content.content` values
to the LLM, ranked by mention count in `news_content.filtered_content`.

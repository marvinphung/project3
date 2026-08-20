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

`content-summary-service` se duoc viet lai sau, nen local runtime hien tai chua co
stage summary moi.

## Sync Workspace

```bash
uv sync --all-packages --all-extras --group dev
```

## Start Infra

```bash
docker compose -f docker-compose.v2.yml up -d mongodb mongodb-init kafka postgres
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

Publisher:

```bash
python3 -m footballpulse_pipeline publish --limit 20
```

API:

```bash
PYTHONPATH=packages/pipeline/src:packages/runtime-config/src:packages/event-contracts/src:services/api-gateway/src:services/crawler-service/src:services/entities-extraction-service/src:services/publisher-service/src python3 -m footballpulse_api_gateway.runtime_v2
```

# Huong Dan Chay FootballPulse v2

Tai lieu nay chi mo ta phan code va flow con duoc giu lai trong repo.

Kien truc muc tieu:

```text
(1) crawler
-> (2) entities-extraction-service
-> (3) content-summary-service
-> (4) publish
-> backend-api
-> frontend
```

Tai thoi diem hien tai:

- `crawler` da co code
- `entities-extraction-service` da co code
- `publish` da co code
- `backend-api` va `frontend` giu nguyen
- `content-summary-service` chua duoc viet lai

Tai lieu nguon:

- [docs/version2/source-of-truth-entity-timeline-architecture.md](/home/pmv259/Documents/personal-projects/project3/docs/version2/source-of-truth-entity-timeline-architecture.md)

## 1. Prerequisites

- Docker + Docker Compose
- Python 3.12
- `uv`
- Node.js 18+

## 2. Env

```bash
cp .env.example .env
```

Bien can co cho local stack:

- `FOOTBALLPULSE_MONGODB_URL`
- `FOOTBALLPULSE_V2_MONGODB_URL`
- `FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS`
- `FOOTBALLPULSE_V2_POSTGRES_URL`
- `NER_MODEL_NAME` hoac `FOOTBALLPULSE_GLINER_MODEL`

## 3. Chay Full Stack

```bash
docker compose -f docker-compose.v2.yml up -d --build
docker compose -f docker-compose.v2.yml ps
```

Services chinh:

- `mongodb`
- `kafka`
- `postgres`
- `api`
- `crawler`
- `entities-extraction`
- `publisher`
- `airflow-*`

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## 4. Chay Tung Stage Bang Docker

Ha tang:

```bash
docker compose -f docker-compose.v2.yml up -d mongodb mongodb-init kafka postgres
```

Crawler:

```bash
docker compose -f docker-compose.v2.yml run --rm crawler \
  python -m footballpulse_pipeline crawl --max-articles 10
```

Entities extraction:

```bash
docker compose -f docker-compose.v2.yml run --rm entities-extraction \
  python -m footballpulse_pipeline process --limit 10
```

Publisher:

```bash
docker compose -f docker-compose.v2.yml run --rm publisher \
  python -m footballpulse_pipeline publish --limit 20
```

API:

```bash
docker compose -f docker-compose.v2.yml up -d api
```

## 5. Chay Bang Python Local

Dong bo workspace:

```bash
uv sync --all-packages --all-extras --group dev
source .venv/bin/activate
set -a
source .env
set +a
```

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

## 6. Kiem Tra Nhanh

Mongo:

```bash
docker compose -f docker-compose.v2.yml exec -T mongodb mongosh --quiet --eval '
const v2 = db.getSiblingDB("footballpulse_v2");
print("metadata=" + v2.news_metadata.countDocuments());
print("content=" + v2.news_content.countDocuments());
print("entities=" + v2.news_entities.countDocuments());
'
```

API:

```bash
curl -s http://127.0.0.1:8000/health
curl -s "http://127.0.0.1:8000/api/v2/articles?limit=5"
```

## 7. Luu Y Hien Tai

- `process` hien tai chi con scope entity extraction.
- `content-summary-service` chua duoc build lai, nen flow tong hop timeline chua co code runtime moi.
- `publish` va serving layer van la phan duoc giu lai cho phase tiep theo.

# Local Development V2

Tai lieu nay huong dan chay FootballPulse `version2` o local theo dung flow da
verify tinh den Tuesday, August 18, 2026.

## 1. Prerequisites

- Python `3.12`
- Docker + Docker Compose
- `uv`
- Kaggle credentials
- Supabase/PostgreSQL credentials

Tao `.env` tu `.env.example` va dien day du:

- `FOOTBALLPULSE_MONGODB_URL`
- `FOOTBALLPULSE_MONGODB_DB=footballpulse_v2`
- `FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:19092`
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

## 2. Sync workspace

```bash
UV_CACHE_DIR=/tmp/footballpulse-uv-cache /home/pmv259/.local/bin/uv sync --all-packages --all-extras --group dev
```

## 3. Start local infra

```bash
docker compose -f docker-compose.v2.yml up -d --build
docker compose -f docker-compose.v2.yml ps
```

Ky vong:

- `mongodb` healthy
- `kafka` healthy
- `postgres` healthy

Ports mac dinh:

- MongoDB: `127.0.0.1:27117`
- Kafka: `127.0.0.1:19092`
- PostgreSQL local: `127.0.0.1:15432`

## 4. Crawl live

Vi du crawl mot nguon RSS live:

```bash
PYTHONPATH=packages/pipeline/src:services/crawler-service/src:services/ai-content-service/src:services/publisher-service/src:packages/runtime-config/src:packages/shared/src:packages/event-contracts/src \
.venv/bin/python -m footballpulse_pipeline crawl --source 'The Guardian Football' --max-articles 1
```

Da verify:

- fetch RSS live duoc
- fetch article live duoc
- ghi Mongo `news_metadata`, `news_content`
- publish Kafka `news.crawled.v1`

Kiem tra nhanh Mongo:

```bash
.venv/bin/python -c "from pymongo import MongoClient; client=MongoClient('mongodb://127.0.0.1:27117/?directConnection=true', uuidRepresentation='standard'); db=client['footballpulse_v2']; print(db.news_metadata.count_documents({}), db.news_content.count_documents({}))"
```

## 5. Process local

```bash
.venv/bin/python -m footballpulse_pipeline process --limit 1
```

Trang thai hien tai:

- consume/process `news.crawled.v1` duoc
- ghi `news_entities` duoc
- neu Kaggle duoc cap GPU slot, pipeline se tiep tuc enrichment
- neu Kaggle dang queue, process co the cho lau ben ngoai local

Kiem tra nhanh:

```bash
.venv/bin/python -c "from pymongo import MongoClient; client=MongoClient('mongodb://127.0.0.1:27117/?directConnection=true', uuidRepresentation='standard'); db=client['footballpulse_v2']; print(db.news_entities.count_documents({}), db.news_enrichments.count_documents({}))"
```

## 6. Publish read model

Neu Mongo da co `news_enrichments.validation_status = VALIDATED`:

```bash
.venv/bin/python -m footballpulse_pipeline publish --limit 10
```

Da verify:

- publish tu Mongo sang PostgreSQL/Supabase duoc

## 7. Test API v2

Smoke test:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/smoke-v2-api.py
```

Focused backend tests:

```bash
set -a
source .env
set +a
uv run pytest -q \
  services/api-gateway/tests/test_runtime.py \
  services/api-gateway/tests/test_auth_api.py \
  services/api-gateway/tests/test_editorial_admin_api.py \
  services/api-gateway/tests/test_package_smoke.py \
  services/api-gateway/tests/test_gateway_middleware.py \
  services/api-gateway/tests/test_auth.py
```

Da verify:

- `smoke-v2-api.py` pass
- focused API tests: `19 passed`

## 8. Luu y ve Kaggle

Kaggle la external dependency. Tinh den Tuesday, August 18, 2026:

- upload dataset pass
- push kernel pass
- kernel co the bi `QUEUED` rat lau do cho GPU slot

Kiem tra trang thai:

```bash
set -a
source .env
set +a
.venv/bin/kaggle kernels status pmv259/footballpulse-ai-enrichment
```

Neu muon bo qua tam thoi, van co the test cac phan con lai:

- crawl
- process entity
- publish voi validated docs san co
- API v2

## 9. Shutdown

```bash
docker compose -f docker-compose.v2.yml down
```

## 10. Deploy split FE / BE

`version2` tach local pipeline khoi serving layer:

- local: crawl, process, Kaggle, publish
- production FE: Vercel
- production BE: Render
- production DB: Supabase PostgreSQL

### Frontend tren Vercel

Working directory:

- `frontend`

Build config:

```text
Install command: npm install
Build command: npm run build
Output directory: dist
```

Env:

```text
VITE_API_BASE_URL=https://<render-backend-domain>
```

Kiem tra local truoc khi deploy:

```bash
cd frontend
npm install
npm run build
```

### Backend API tren Render

Working directory:

- repo root, nhung runtime su dung `services/api-gateway`

Start command uu tien:

```bash
uv run footballpulse-api-v2
```

Neu can chi ro `PYTHONPATH`:

```bash
PYTHONPATH=services/api-gateway/src:services/content-service/src:packages/runtime-config/src uv run footballpulse-api-v2
```

Env can co:

```text
SUPABASE_DB_HOST
SUPABASE_DB_PORT
SUPABASE_DB_NAME
SUPABASE_DB_USER
SUPABASE_DB_PASSWORD
FOOTBALLPULSE_API_ADMIN_TOKEN
FOOTBALLPULSE_API_EDITOR_TOKEN
FOOTBALLPULSE_API_JWT_SECRET
FOOTBALLPULSE_API_ADMIN_USERNAME
FOOTBALLPULSE_API_ADMIN_PASSWORD
FOOTBALLPULSE_API_EDITOR_USERNAME
FOOTBALLPULSE_API_EDITOR_PASSWORD
```

Kiem tra local truoc khi deploy:

```bash
set -a
source .env
set +a
.venv/bin/python scripts/smoke-v2-api.py
```

### Khong deploy len Vercel/Render

Nhung thanh phan sau van o local:

- MongoDB
- Kafka
- Airflow
- `footballpulse_pipeline crawl`
- `footballpulse_pipeline process`
- Kaggle batch runtime

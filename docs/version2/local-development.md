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

## 3. Start full local stack

```bash
docker compose -f docker-compose.v2.yml up -d --build
docker compose -f docker-compose.v2.yml ps
```

Ky vong:

- `mongodb` healthy
- `kafka` healthy
- `postgres` healthy
- `api` running
- `crawler` running
- `processor` running
- `publisher` running

Ports mac dinh:

- MongoDB: `127.0.0.1:27117`
- Kafka: `127.0.0.1:19092`
- PostgreSQL local: `127.0.0.1:15432`
- API: `127.0.0.1:8000`

Y nghia:

- `crawler` tu dong crawl live theo vong lap
- `processor` tu dong xu ly entity va backlog processing
- `publisher` tu dong day validated records sang PostgreSQL local
- `api` doc tu PostgreSQL local va phuc vu `/api/v2`

Theo doi log:

```bash
docker compose -f docker-compose.v2.yml logs -f crawler
docker compose -f docker-compose.v2.yml logs -f processor
docker compose -f docker-compose.v2.yml logs -f publisher
```

Da verify local:

- crawl live ghi duoc `news_metadata`, `news_content`
- processor ghi duoc `news_entities`
- publisher publish duoc du lieu validated sang PostgreSQL
- API smoke pass tren `/api/v2`

## 4. Kiem tra crawler / Mongo

```bash
.venv/bin/python -c "from pymongo import MongoClient; client=MongoClient('mongodb://127.0.0.1:27117/?directConnection=true', uuidRepresentation='standard'); db=client['footballpulse_v2']; print(db.news_metadata.count_documents({}), db.news_content.count_documents({}))"
```

## 5. Kiem tra processor / Mongo

Trang thai hien tai trong Docker default:

- consume/process `news.crawled.v1` duoc
- ghi `news_entities` duoc
- `FOOTBALLPULSE_AI_PROVIDER` cua service `processor` dang de `local_skip`
  de local `up -d --build` khong bi block boi queue Kaggle
- khi can chay Kaggle that, chay thu cong process command ngoai compose hoac doi
  env cua `processor`

Kiem tra nhanh Mongo:

```bash
.venv/bin/python -c "from pymongo import MongoClient; client=MongoClient('mongodb://127.0.0.1:27117/?directConnection=true', uuidRepresentation='standard'); db=client['footballpulse_v2']; print(db.news_entities.count_documents({}), db.news_enrichments.count_documents({}))"
```

## 6. Kiem tra publisher / PostgreSQL local

Publisher trong compose se tu dong publish cac record hop le. Kiem tra nhanh:

```bash
docker exec -i $(docker compose -f docker-compose.v2.yml ps -q postgres) \
  psql -U footballpulse -d footballpulse_v2 -c "select count(*) from content_schema.publications;"
```

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

Vi local compose mac dinh dang uu tien full stack on dinh, service `processor`
khong auto cho Kaggle trong vong lap. Neu muon chay Kaggle that, dung lenh thu
cong:

```bash
set -a
source .env
set +a
.venv/bin/python -m footballpulse_pipeline process --limit 10
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

- repo root

Start command uu tien:

```bash
PYTHONPATH=packages/pipeline/src:packages/runtime-config/src:packages/event-contracts/src:services/api-gateway/src:services/content-service/src:services/ai-content-service/src:services/crawler-service/src:services/intelligence-service/src:services/publisher-service/src python -m footballpulse_api_gateway.runtime_v2
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

# Backend API Service

## Purpose

`backend-api` la serving API cho frontend. Service nay doc duy nhat tu Supabase
PostgreSQL read model va expose public endpoints cho UI.

Backend API khong nam trong Airflow pipeline va khong doc MongoDB trong target
architecture.

## Serving Flow

```text
frontend -> backend-api -> Supabase PostgreSQL
```

Deploy target:

- local: Docker hoac `uv`
- production: Render

## Commands

Docker:

```bash
docker compose -f docker-compose.v2.yml up -d api
```

Local `uv`:

```bash
uv run python -m footballpulse_api_gateway.runtime_v2
```

Render Docker command:

```bash
python -m footballpulse_api_gateway.runtime_v2
```

Health check:

```text
/health
```

## Inputs

Environment:

- Supabase PostgreSQL URL
- API auth/admin env neu dung admin endpoints
- CORS origins

Database:

- `entities`
- `source_articles`
- `entity_timeline_items`
- `timeline_item_articles`

## Public API Responsibilities

Backend API phuc vu:

- home top entities
- entity directory pages
- entity search
- entity timeline
- latest articles
- article detail
- article source list
- static health/readiness

## Key Endpoint Contracts

### Top entities

```text
GET /api/v2/entities/top?window=24h&limit=100
```

Behavior:

- doc PostgreSQL `entities`
- sort theo `mention_count_24h` giam dan
- optional filter theo `entity_type` cho tab cau thu/hlv/clb
- home page co the lay top 100
- `/cau-thu` lay top 50 `PLAYER`
- `/hlv` lay top 30 `COACH`
- `/clb` lay top 30 `CLUB`

### Entity search

```text
GET /api/v2/entities/search?q=<query>
```

Behavior:

- search canonical name va aliases
- khong can autocomplete
- neu khong co match thi tra empty result, UI hien khong tim thay

### Entity timeline

```text
GET /api/v2/entities/{entity_id}/timeline
```

Behavior:

- id la UUID
- tra entity summary + timeline items + source articles
- timeline sort moi nhat truoc

### Entity by slug

```text
GET /api/v2/entities/by-slug/{entity_type}/{slug}
```

Behavior:

- resolve route dang `/clb/{slug}`, `/cau-thu/{slug}`, `/hlv/{slug}`
- backend map slug ve canonical entity id
- frontend sau do goi timeline bang UUID hoac endpoint tuong duong

### Articles

```text
GET /api/v2/articles
GET /api/v2/articles/{id_or_slug}
GET /api/v2/articles/{id_or_slug}/sources
```

Behavior:

- latest/news listing doc `source_articles`
- article detail khong doc Mongo
- entity chips trong article lay tu published read model neu co

## CORS

`FOOTBALLPULSE_API_CORS_ORIGINS` nen dung origin khong co trailing slash.

Dung:

```text
https://project3-sigma-gray.vercel.app
```

Khong dung:

```text
https://project3-sigma-gray.vercel.app/
```

## Data Dependency

Neu API tra rong:

1. Kiem tra Supabase tables co data khong.
2. Kiem tra publish da chay chua.
3. Kiem tra frontend dang goi dung backend URL.

Khong sua backend de doc Mongo fallback.

## Non-Goals

- Khong crawl.
- Khong extract entity.
- Khong call LLM.
- Khong orchestration Airflow.
- Khong ghi Mongo.

## Debug Checklist

Neu local frontend khong connect duoc backend:

1. Kiem tra backend health `GET /health`.
2. Kiem tra `VITE_API_BASE_URL` cua frontend la `http://localhost:8000`.
3. Kiem tra CORS origin co dung origin khong trailing slash.

Neu backend tra rong nhung Supabase co data:

1. Kiem tra backend env dang tro dung Supabase URL.
2. Kiem tra query params `entity_type`, `limit`, `window`.
3. Kiem tra slug route co dung `entity_type` map `/clb`, `/cau-thu`, `/hlv`.

Neu Render backend loi:

1. Kiem tra Dockerfile path `services/runtime.Dockerfile`.
2. Kiem tra Docker command `python -m footballpulse_api_gateway.runtime_v2`.
3. Kiem tra health check path `/health`.
4. Kiem tra Supabase session pooler URL va password da percent-encode neu can.

## Safe Changes

Co the sua trong boundary backend-api:

- REST endpoint shape neu frontend contract cung update
- SQL read queries
- pagination/filtering/sorting
- CORS config
- health/readiness

Khong nen sua o day:

- pipeline generation logic
- Mongo fallback
- frontend-only state workaround cho missing read model

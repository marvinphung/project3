# Frontend Service

## Purpose

`frontend` la React/Vite UI cua FootballPulse. UI chi goi `backend-api`, khong
doc database truc tiep va khong goi pipeline workers.

## Serving Flow

```text
frontend -> backend-api -> Supabase PostgreSQL
```

Deploy target:

- local: Vite dev server
- production: Vercel

## Commands

Local:

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

Vercel settings:

```text
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
Install Command: npm install
```

Production env:

```text
VITE_API_BASE_URL=https://<render-backend>.onrender.com
```

## Inputs

Environment:

- `VITE_API_BASE_URL`

API:

- `GET /api/v2/entities/top`
- `GET /api/v2/entities/search`
- `GET /api/v2/entities/by-slug/{entity_type}/{slug}`
- `GET /api/v2/entities/{entity_id}/timeline`
- `GET /api/v2/articles`
- `GET /api/v2/articles/{id_or_slug}`
- `GET /api/v2/articles/{id_or_slug}/sources`

## Pages

### Home

Purpose:

- hien hero/search
- hien top 100 entities xuat hien nhieu nhat trong 24h
- entities van hien ke ca chua co timeline summary

Data:

```text
GET /api/v2/entities/top?window=24h&limit=100
```

### `/cau-thu`

Purpose:

- hien top 50 `PLAYER` trong 24h

Data:

```text
GET /api/v2/entities/top?window=24h&entity_type=PLAYER&limit=50
```

### `/hlv`

Purpose:

- hien top 30 `COACH` trong 24h

Data:

```text
GET /api/v2/entities/top?window=24h&entity_type=COACH&limit=30
```

### `/clb`

Purpose:

- hien top 30 `CLUB` trong 24h

Data:

```text
GET /api/v2/entities/top?window=24h&entity_type=CLUB&limit=30
```

### Entity Detail

Routes:

```text
/cau-thu/{slug}
/hlv/{slug}
/clb/{slug}
/entity/{uuid}
```

Behavior:

- slug routes resolve entity bang backend slug endpoint
- UUID routes goi timeline truc tiep
- timeline item hien `title`, `summary`, 3h UTC window va source articles
- neu entity chua co timeline thi UI hien empty state thay vi loi

### Search

Purpose:

- search entity bang canonical name hoac alias
- khong co autocomplete
- neu khong co ket qua thi hien "khong tim thay"

Data:

```text
GET /api/v2/entities/search?q=<query>
```

### Tin moi

Purpose:

- hien article listing tu PostgreSQL read model

Data:

```text
GET /api/v2/articles
```

## Routing Rule

UI nen dung slug cho routes user-facing:

```text
/clb/brighton-hove-albion
/cau-thu/player-slug
/hlv/coach-slug
```

UUID route van co the giu cho fallback/internal link:

```text
/entity/{uuid}
```

## Non-Goals

- Khong doc Supabase truc tiep.
- Khong doc Mongo.
- Khong chay Airflow.
- Khong goi LLM.
- Khong tinh popularity client-side.

## Debug Checklist

Neu page hien empty/error:

1. Kiem tra Network tab endpoint nao fail.
2. Kiem tra `VITE_API_BASE_URL` co tro backend dung moi truong khong.
3. Kiem tra backend endpoint tuong ung bang curl.
4. Neu backend tra empty, kiem tra Supabase/publish thay vi hardcode UI fallback.

Neu click entity slug khong co data:

1. Kiem tra route dang dung slug hay UUID.
2. Kiem tra backend slug endpoint resolve duoc entity khong.
3. Kiem tra entity id do co timeline items khong.
4. Neu chua co timeline item, UI hien empty state la dung.

Neu Vercel build fail:

1. Kiem tra Root Directory la `frontend`.
2. Kiem tra Output Directory la `dist`.
3. Kiem tra `frontend/vercel.json` co rewrite SPA.
4. Kiem tra `npm run build` local pass.

## Safe Changes

Co the sua trong boundary frontend:

- route layout
- API client contract neu backend cung update
- empty/loading/error states
- responsive UI
- search UX

Khong nen sua o day:

- database schema
- direct Supabase queries
- summary generation rule
- entity extraction behavior

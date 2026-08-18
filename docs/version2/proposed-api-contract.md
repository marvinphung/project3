# Proposed Backend API Contract

## Muc tieu

Backend API version 2 la service deploy tren Render. Service nay chi doc Supabase
PostgreSQL va tra JSON cho frontend deploy tren Vercel.

Backend API khong:

- connect MongoDB
- crawl news
- goi AI/Kaggle
- sync du lieu
- luu log/job/batch state vao database

Ghi chu:

- Surface da implement trong code hien tai gom:
  - `GET /api/v2/articles`
  - `GET /api/v2/articles/{slug}`
  - `GET /api/v2/articles/{slug}/sources`
  - `GET /api/v2/stories/{story_id}/timeline`
- Cac section story/entity/publication/search ben duoi la backlog contract cho
  cac phase tiep theo, chua duoc expose day du trong runtime hien tai.

## 1. Quy uoc chung

Base path:

```text
/api/v2
```

Response list dung shape thong nhat:

```json
{
  "items": [],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 120
  }
}
```

Error envelope:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "resource not found",
    "details": {}
  }
}
```

Pagination:

- `limit`: default `20`, min `1`, max `50`
- `offset`: default `0`, min `0`

Time:

- API tra ISO-8601 UTC.
- Frontend tu format theo locale `vi-VN`.

Language:

- Public UI uu tien field tieng Viet: `title_vi`, `summary_vi`, `body_vi`.
- English field van tra kem khi co san de debug/noi dung song ngu nhe.

## 2. Shared DTOs

### `SourceSummary`

```json
{
  "id": "uuid",
  "name": "BBC Sport",
  "domain_name": "bbc.com",
  "reliability_tier": 1
}
```

### `EntitySummary`

```json
{
  "id": "uuid",
  "entity_type": "PLAYER",
  "name": "Vinicius Junior",
  "slug": "vinicius-junior",
  "image_url": "https://..."
}
```

### `ArticleSummary`

```json
{
  "id": "uuid",
  "url": "https://...",
  "domain_name": "bbc.com",
  "source": {
    "id": "uuid",
    "name": "BBC Sport",
    "domain_name": "bbc.com",
    "reliability_tier": 1
  },
  "title": "Arsenal submit bid for striker",
  "description": "Short description",
  "image_url": "https://...",
  "published_at": "2026-08-18T08:00:00Z",
  "summary_vi": "Tom tat tieng Viet...",
  "event_type": "TRANSFER"
}
```

### `StorySummary`

```json
{
  "id": "uuid",
  "title_vi": "Arsenal gui de nghi mua Vinicius",
  "summary_vi": "Dien bien moi nhat...",
  "event_type": "TRANSFER",
  "status": "DEVELOPING",
  "confirmation": "MULTI_SOURCE",
  "first_seen_at": "2026-08-18T08:00:00Z",
  "last_seen_at": "2026-08-18T12:00:00Z",
  "entities": [],
  "source_count": 3
}
```

### `TimelineEntry`

```json
{
  "id": "uuid",
  "story_id": "uuid",
  "happened_at": "2026-08-18T12:00:00Z",
  "title_vi": "De nghi moi duoc gui",
  "summary_vi": "Arsenal da gui de nghi...",
  "confirmation": "MULTI_SOURCE",
  "source_count": 2,
  "articles": []
}
```

## 3. Health

### `GET /health`

Dung cho Render health check.

Response:

```json
{
  "service": "backend-api",
  "status": "ok"
}
```

## 4. Articles API

### `GET /api/v2/articles`

Lay danh sach bai news da materialize len Supabase.

Query params:

```text
limit=20
offset=0
source_id=uuid
event_type=TRANSFER
entity_id=uuid
q=arsenal
from=2026-08-01T00:00:00Z
to=2026-08-18T23:59:59Z
```

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "url": "https://...",
      "domain_name": "bbc.com",
      "source": {},
      "title": "Arsenal submit bid for striker",
      "description": "Short description",
      "image_url": "https://...",
      "published_at": "2026-08-18T08:00:00Z",
      "summary_vi": "Tom tat tieng Viet...",
      "event_type": "TRANSFER"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 120
  }
}
```

Sort mac dinh:

```text
published_at desc, crawled_at desc
```

### `GET /api/v2/articles/{slug}`

Lay chi tiet mot article.

Response:

```json
{
  "id": "uuid",
  "url": "https://...",
  "domain_name": "bbc.com",
  "source": {},
  "title": "Arsenal submit bid for striker",
  "description": "Short description",
  "image_url": "https://...",
  "published_at": "2026-08-18T08:00:00Z",
  "summary_en": "English summary",
  "summary_vi": "Tom tat tieng Viet",
  "event_type": "TRANSFER",
  "entities": [],
  "claims": [],
  "stories": []
}
```

Notes:

- API khong tra raw HTML.
- Neu Postgres `articles` khong luu full content thi endpoint nay chi tra summary
  va link source.

## 5. Stories API

### `GET /api/v2/stories`

Lay danh sach story dang theo doi.

Query params:

```text
limit=20
offset=0
status=DEVELOPING
event_type=TRANSFER
entity_id=uuid
confirmation=MULTI_SOURCE
q=arsenal
from=2026-08-01T00:00:00Z
to=2026-08-18T23:59:59Z
```

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "title_vi": "Arsenal gui de nghi mua Vinicius",
      "summary_vi": "Dien bien moi nhat...",
      "event_type": "TRANSFER",
      "status": "DEVELOPING",
      "confirmation": "MULTI_SOURCE",
      "first_seen_at": "2026-08-18T08:00:00Z",
      "last_seen_at": "2026-08-18T12:00:00Z",
      "entities": [],
      "source_count": 3
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 32
  }
}
```

Sort mac dinh:

```text
last_seen_at desc
```

### `GET /api/v2/stories/{id}`

Lay story detail.

Response:

```json
{
  "id": "uuid",
  "title_en": "Arsenal submit bid for Vinicius",
  "title_vi": "Arsenal gui de nghi mua Vinicius",
  "summary_en": "English summary",
  "summary_vi": "Tom tat tieng Viet",
  "event_type": "TRANSFER",
  "status": "DEVELOPING",
  "confirmation": "MULTI_SOURCE",
  "first_seen_at": "2026-08-18T08:00:00Z",
  "last_seen_at": "2026-08-18T12:00:00Z",
  "entities": [],
  "sources": [],
  "claims": [],
  "latest_timeline": []
}
```

### `GET /api/v2/stories/{id}/timeline`

Lay timeline cua mot story.

Query params:

```text
limit=50
offset=0
from=2026-08-01T00:00:00Z
to=2026-08-18T23:59:59Z
```

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "story_id": "uuid",
      "happened_at": "2026-08-18T12:00:00Z",
      "title_vi": "De nghi moi duoc gui",
      "summary_vi": "Arsenal da gui de nghi...",
      "confirmation": "MULTI_SOURCE",
      "source_count": 2,
      "articles": [
        {
          "id": "uuid",
          "title": "Arsenal submit bid...",
          "url": "https://...",
          "source": {}
        }
      ]
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 8
  }
}
```

Sort mac dinh:

```text
happened_at desc
```

## 6. Entities API

### `GET /api/v2/entities`

Lay danh sach entities.

Query params:

```text
limit=20
offset=0
type=PLAYER
q=vinicius
```

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "entity_type": "PLAYER",
      "name": "Vinicius Junior",
      "slug": "vinicius-junior",
      "image_url": "https://..."
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 100
  }
}
```

### `GET /api/v2/entities/{type}/{slug}`

Lay entity detail.

Response:

```json
{
  "id": "uuid",
  "entity_type": "PLAYER",
  "name": "Vinicius Junior",
  "slug": "vinicius-junior",
  "image_url": "https://...",
  "description": "...",
  "metadata": {},
  "story_count": 12,
  "article_count": 34,
  "latest_stories": []
}
```

### `GET /api/v2/entities/{type}/{slug}/timeline`

Lay timeline tong hop theo entity. Endpoint nay join:

```text
entities -> story_entities -> stories -> timeline_entries
```

Query params:

```text
limit=50
offset=0
event_type=TRANSFER
from=2026-08-01T00:00:00Z
to=2026-08-18T23:59:59Z
```

Response:

```json
{
  "entity": {
    "id": "uuid",
    "entity_type": "PLAYER",
    "name": "Vinicius Junior",
    "slug": "vinicius-junior",
    "image_url": "https://..."
  },
  "items": [
    {
      "id": "uuid",
      "story_id": "uuid",
      "happened_at": "2026-08-18T12:00:00Z",
      "title_vi": "De nghi moi duoc gui",
      "summary_vi": "Arsenal da gui de nghi...",
      "confirmation": "MULTI_SOURCE",
      "source_count": 2,
      "articles": []
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 20
  }
}
```

## 7. Publications API

### `GET /api/v2/publications`

Lay danh sach bai tong hop da publish.

Query params:

```text
limit=20
offset=0
q=arsenal
entity_id=uuid
from=2026-08-01T00:00:00Z
to=2026-08-18T23:59:59Z
```

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "story_id": "uuid",
      "slug": "arsenal-submit-bid-for-vinicius",
      "title_vi": "Arsenal gui de nghi mua Vinicius",
      "excerpt_vi": "Tom tat ngan...",
      "cover_image_url": "https://...",
      "published_at": "2026-08-18T13:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 15
  }
}
```

### `GET /api/v2/publications/{slug}`

Lay detail bai publish.

Response:

```json
{
  "id": "uuid",
  "story_id": "uuid",
  "slug": "arsenal-submit-bid-for-vinicius",
  "title_en": "Arsenal submit bid for Vinicius",
  "title_vi": "Arsenal gui de nghi mua Vinicius",
  "excerpt_vi": "Tom tat ngan...",
  "body_en": "...",
  "body_vi": "...",
  "cover_image_url": "https://...",
  "published_at": "2026-08-18T13:00:00Z",
  "story": {},
  "sources": []
}
```

## 8. Search API

### `GET /api/v2/search`

Search nhe cho UI.

Query params:

```text
q=arsenal
limit=10
```

Response:

```json
{
  "articles": [],
  "stories": [],
  "entities": [],
  "publications": []
}
```

Notes:

- MVP co the search bang Postgres `ILIKE`.
- Sau nay neu can chat luong hon thi dung full-text index trong Supabase.

## 9. Security va CORS

Public read endpoints co the khong can auth trong MVP.

Backend chi allow origins:

```text
http://localhost:5173
https://<vercel-domain>
```

Khong expose Supabase service role key cho frontend.

## 10. Backend query ownership

Backend API chi duoc query cac bang:

```text
sources
articles
entities
entity_aliases
stories
story_entities
story_sources
claims
timeline_entries
publications
```

Backend API khong co repository/client cho:

```text
MongoDB
Kaggle
Airflow
crawler
processor
publisher
```

## 11. Thu tu implement

1. Tao Pydantic response schemas cho shared DTOs.
2. Tao Supabase/Postgres read repositories.
3. Implement health + list articles.
4. Implement story list/detail/timeline.
5. Implement entity list/detail/timeline.
6. Implement publications.
7. Implement search.
8. Chuyen frontend API client sang contract moi.

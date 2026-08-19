# Proposed Database Schema

## Muc tieu

Thiet ke nay tach ro hai lop du lieu:

- MongoDB local: luu du lieu da crawl va da xu ly trong pipeline local.
- Supabase PostgreSQL: luu du lieu san pham da materialize de backend API doc va frontend hien thi.

Khong luu log, batch state, Airflow/Kaggle job state, outbox, processed event,
`batch_id`, `correlation_id` trong schema chinh. Neu can debug thi dung log file,
stdout container, hoac local artifact tam thoi ngoai database.

## 1. MongoDB Local Schema

MongoDB chi phuc vu pipeline local. Backend deploy Render khong connect MongoDB.

Mongo collections duoc thiet ke gan voi `news-aggregator`: moi lop xu ly la mot
collection rieng, dung chung `_id = article_id`.

Cong nghe Mongo nen dung nhu `news-aggregator`:

- `Beanie` `Document`
- `Motor`
- `Pydantic`
- `_id`/`id` dung `uuid.UUID`, khong dung Mongo `ObjectId`
- `validate_on_save = True`
- index khai bao trong model hoac bootstrap luc startup

### Article ID generation

Tat ca collection Mongo dung chung `_id = article_id`.

`article_id` la UUID deterministic tao tu URL bai viet:

```python
article_id = uuid.uuid5(NEWS_URL_NAMESPACE, canonical_news_url)
```

Quy tac:

- `canonical_news_url` la URL da normalize de dedupe: lowercase scheme/host, bo
  fragment, bo tracking params nhu `utm_*`, sap xep query params con lai.
- Van luu `url` goc trong `news_metadata` neu can trace.
- Cung mot URL canonical luon ra cung UUID, nen check trung lap chi can lookup
  `_id`.
- Khong tao article ID tu title vi title co the doi.

### 1.1 `news_metadata`

Luu metadata de dedupe, filter, va chon bai cho processor.

```json
{
  "_id": "uuid5(canonical_news_url)",
  "url": "https://example.com/article",
  "canonical_url": "https://example.com/article",
  "domain_name": "example.com",
  "source_name": "Example Sport",
  "title": "Arsenal submit bid for striker",
  "description": "Short article description",
  "published_time": "2026-08-18T08:00:00Z",
  "crawl_date": "2026-08-18T08:03:00Z",
  "image_url": "https://example.com/image.jpg",
  "tags": ["transfer", "premier-league"],
  "article_keywords": ["Arsenal", "bid", "striker"],
  "content_hash": "sha256",
  "language": "en"
}
```

Indexes:

```javascript
db.news_metadata.createIndex({ canonical_url: 1 }, { unique: true })
db.news_metadata.createIndex({ published_time: -1 })
db.news_metadata.createIndex({ domain_name: 1, published_time: -1 })
db.news_metadata.createIndex({ title: "text", description: "text" })
```

Notes:

- `_id` la article ID on dinh, tao bang UUIDv5 tu `canonical_url`.
- Check trung URL chi can `find_one({"_id": article_id})`.
- `content_hash` dung de bo qua bai noi dung trung lap don gian.
- Khong luu raw HTML.
- Khong luu crawl run, batch, attempt, scheduler metadata.

### 1.2 `news_content`

Luu noi dung text da clean.

```json
{
  "_id": "uuid5(canonical_news_url)",
  "content": "Cleaned English article content...",
  "cleaned_at": "2026-08-18T08:03:05Z",
  "extractor": "TRAFILATURA",
  "extraction_status": "SUCCESS"
}
```

Indexes:

```javascript
db.news_content.createIndex({ cleaned_at: -1 })
```

Notes:

- Chi luu cleaned content. Raw HTML khong dua vao DB.
- Neu can replay extractor thi crawl lai tu URL hoac dung local artifact tam thoi,
  khong bien Mongo thanh kho forensic.

### 1.3 `news_entities`

Luu entity extraction cua tung bai.

```json
{
  "_id": "uuid5(canonical_news_url)",
  "entities": [
    {
      "label": "PLAYER",
      "text": "Vinicius Junior",
      "score": 0.94,
      "start": 120,
      "end": 136,
      "canonical_entity_id": "uuid-or-null",
      "canonical_name": "Vinicius Junior"
    }
  ],
  "model_name": "gliner2",
  "model_version": "fastino/gliner2-large-v1",
  "processed_at": "2026-08-18T08:08:00Z"
}
```

Indexes:

```javascript
db.news_entities.createIndex({ "entities.label": 1 })
db.news_entities.createIndex({ "entities.canonical_entity_id": 1 })
db.news_entities.createIndex({ processed_at: -1 })
```

Notes:

- `canonical_entity_id` tro sang entity trong Supabase PostgreSQL sau khi publisher
  map duoc.
- Mention chua map duoc van giu trong Mongo, nhung khong can tao queue review rieng
  neu MVP chua co UI admin review.

### 1.4 `news_enrichments`

Luu ket qua AI/enrichment da validate o muc article.

```json
{
  "_id": "uuid5(canonical_news_url)",
  "event_type": "TRANSFER",
  "summary_en": "Arsenal have submitted a bid...",
  "summary_vi": "Arsenal da gui de nghi...",
  "claims": [
    {
      "subject": "Arsenal",
      "subject_entity_id": "uuid-or-null",
      "predicate": "SUBMITTED_BID",
      "object": "Vinicius Junior",
      "object_entity_id": "uuid-or-null",
      "object_value": {
        "amount": 180000000,
        "currency": "EUR"
      },
      "certainty": "REPORTED",
      "evidence_quote": "Arsenal have submitted a EUR180m bid...",
      "evidence_start": 120,
      "evidence_end": 170
    }
  ],
  "validation_status": "VALIDATED",
  "model_name": "qwen3",
  "model_version": "qwen3-0.6b",
  "prompt_version": "article-enrichment-v1",
  "processed_at": "2026-08-18T08:20:00Z"
}
```

Indexes:

```javascript
db.news_enrichments.createIndex({ validation_status: 1, processed_at: -1 })
db.news_enrichments.createIndex({ event_type: 1, processed_at: -1 })
db.news_enrichments.createIndex({ "claims.subject_entity_id": 1 })
db.news_enrichments.createIndex({ "claims.object_entity_id": 1 })
```

Notes:

- `_id` van la article ID, khong phai model run ID.
- Enrichment cua cung mot article overwrite/upsert document cu neu chay lai va
  output duoc chap nhan. MVP khong luu lich su run.
- Chi giu ket qua moi nhat duoc chap nhan. MVP khong can luu lich su prompt/model
  run trong DB.
- Neu output loi thi co the khong ghi document, hoac ghi `validation_status =
  "FAILED"` voi `error_code` ngan gon. Khong luu raw model output.

### 1.5 `news_embeddings` optional

Chi giu neu can semantic search local trong pipeline.

```json
{
  "_id": "uuid5(canonical_news_url)",
  "embedding": [0.01, -0.03],
  "model_name": "bge-small-en-v1.5",
  "dimensions": 384,
  "created_at": "2026-08-18T08:10:00Z"
}
```

Indexes:

```javascript
db.news_embeddings.createIndex({ model_name: 1, created_at: -1 })
```

Notes:

- Neu Supabase/Postgres se phuc vu search vector thi embedding nen sync sang
  Postgres bang `pgvector`, khong bat buoc giu Mongo.

## 2. Supabase PostgreSQL Schema

Supabase PostgreSQL la source cho Render backend API va Vercel frontend.
Schema nay chi chua du lieu da materialize de phuc vu san pham.

### 2.1 Enum conventions

Co the dung `text` + check constraints de migration don gian tren Supabase.

```sql
create type entity_type as enum ('PLAYER', 'CLUB', 'COACH', 'COMPETITION');
create type story_status as enum ('DEVELOPING', 'CONFIRMED', 'STALE', 'CLOSED');
create type confirmation_level as enum ('SINGLE_SOURCE', 'MULTI_SOURCE', 'OFFICIAL', 'CONFLICTED');
create type publication_status as enum ('PUBLISHED', 'REJECTED');
```

### 2.2 `sources`

Nguon tin de hien thi va tinh do tin cay.

```sql
create table sources (
  id uuid primary key,
  name text not null,
  domain_name text not null,
  homepage_url text,
  reliability_tier smallint not null check (reliability_tier between 1 and 5),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (domain_name)
);
```

### 2.3 `articles`

Ban public/read model cua bai crawl da duoc chap nhan de lam evidence.

```sql
create table articles (
  id uuid primary key,
  source_id uuid not null references sources(id),
  url text not null,
  canonical_url text not null,
  domain_name text not null,
  title text not null,
  description text,
  image_url text,
  published_at timestamptz,
  crawled_at timestamptz not null,
  language text not null default 'en',
  content_hash text not null,
  summary_en text,
  summary_vi text,
  event_type text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (canonical_url)
);

create index articles_published_at_idx on articles (published_at desc);
create index articles_source_published_idx on articles (source_id, published_at desc);
create index articles_event_type_idx on articles (event_type);
```

Notes:

- `articles.id` dung cung UUID voi Mongo `_id`, tao tu `canonical_news_url`.
- `articles` khong luu full cleaned content neu UI khong can doc noi dung goc.
- Neu can trang article detail hien full source text, them cot `content text`.
  Con neu chi can link ve source, khong them.

### 2.4 `entities`

Danh muc thuc the bong da.

```sql
create table entities (
  id uuid primary key,
  entity_type entity_type not null,
  name text not null,
  slug text not null,
  image_url text,
  description text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (entity_type, slug)
);

create index entities_name_search_idx on entities using gin (to_tsvector('simple', name));
```

### 2.5 `entity_aliases`

Phuc vu publisher map mention tu Mongo sang entity canonical.

```sql
create table entity_aliases (
  id uuid primary key,
  entity_id uuid not null references entities(id) on delete cascade,
  alias text not null,
  normalized_alias text not null,
  created_at timestamptz not null default now(),
  unique (normalized_alias)
);

create index entity_aliases_entity_idx on entity_aliases (entity_id);
```

### 2.6 `stories`

Story la su kien/chu de ma UI theo doi theo thoi gian.

```sql
create table stories (
  id uuid primary key,
  title_en text not null,
  title_vi text not null,
  summary_en text,
  summary_vi text,
  event_type text not null,
  status story_status not null default 'DEVELOPING',
  confirmation confirmation_level not null default 'SINGLE_SOURCE',
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index stories_last_seen_idx on stories (last_seen_at desc);
create index stories_event_type_idx on stories (event_type);
create index stories_status_idx on stories (status);
```

### 2.7 `story_entities`

Lien ket story voi entity de query timeline theo player/club/coach/competition.

```sql
create table story_entities (
  story_id uuid not null references stories(id) on delete cascade,
  entity_id uuid not null references entities(id) on delete cascade,
  role text,
  created_at timestamptz not null default now(),
  primary key (story_id, entity_id)
);

create index story_entities_entity_idx on story_entities (entity_id);
```

### 2.8 `story_sources`

Lien ket story voi bai bao nguon.

```sql
create table story_sources (
  story_id uuid not null references stories(id) on delete cascade,
  article_id uuid not null references articles(id) on delete cascade,
  source_id uuid not null references sources(id),
  is_primary boolean not null default false,
  added_at timestamptz not null default now(),
  primary key (story_id, article_id)
);

create index story_sources_article_idx on story_sources (article_id);
create index story_sources_source_idx on story_sources (source_id);
```

### 2.9 `claims`

Fact da validate de dung cho story/timeline.

```sql
create table claims (
  id uuid primary key,
  story_id uuid not null references stories(id) on delete cascade,
  article_id uuid not null references articles(id) on delete cascade,
  subject_entity_id uuid references entities(id),
  predicate text not null,
  object_entity_id uuid references entities(id),
  object_text text,
  object_value jsonb not null default '{}'::jsonb,
  statement_en text not null,
  statement_vi text,
  certainty text not null,
  evidence_quote text not null,
  evidence_start integer,
  evidence_end integer,
  created_at timestamptz not null default now()
);

create index claims_story_idx on claims (story_id);
create index claims_article_idx on claims (article_id);
create index claims_subject_idx on claims (subject_entity_id);
create index claims_object_idx on claims (object_entity_id);
```

Notes:

- Khong tach `claim_evidence` rieng o MVP de schema gon hon.
- Moi claim gan truc tiep voi `article_id` va evidence quote.

### 2.10 `timeline_entries`

Du lieu frontend doc cho timeline.

```sql
create table timeline_entries (
  id uuid primary key,
  story_id uuid not null references stories(id) on delete cascade,
  happened_at timestamptz not null,
  title_en text,
  title_vi text,
  summary_en text not null,
  summary_vi text not null,
  confirmation confirmation_level not null,
  source_count integer not null default 1,
  article_ids uuid[] not null default '{}',
  claim_ids uuid[] not null default '{}',
  created_at timestamptz not null default now()
);

create index timeline_entries_story_time_idx on timeline_entries (story_id, happened_at desc);
create index timeline_entries_happened_at_idx on timeline_entries (happened_at desc);
```

Notes:

- Dung `happened_at` thay vi window/batch de don gian cho UI.
- Neu sau nay can gom 6 gio thi publisher tu quyet dinh luc ghi, API khong can biet
  concept batch/window.

### 2.11 `publications`

Bai viet da publish cho trang article/detail.

```sql
create table publications (
  id uuid primary key,
  story_id uuid references stories(id) on delete set null,
  slug text not null,
  title_en text not null,
  title_vi text not null,
  excerpt_vi text,
  body_en text not null,
  body_vi text not null,
  cover_image_url text,
  status publication_status not null default 'PUBLISHED',
  published_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slug)
);

create index publications_published_at_idx on publications (published_at desc);
create index publications_story_idx on publications (story_id);
```

Notes:

- MVP khong co human review step. Publication chi duoc ghi khi pipeline da validate
  output tu dong.
- Neu generated article khong dat validation, publisher khong insert publication,
  hoac insert `REJECTED` neu can debug bang query product. Mac dinh nen khong insert
  de schema gon.
- Khong dung `DRAFT`/`REVIEW` trong V2 dau tien vi chung tao cam giac co workflow
  bien tap thu cong.

## 3. Publisher Mapping

Local publisher doc Mongo va upsert vao Supabase theo mapping:

```text
Mongo news_metadata      -> Postgres articles, sources
Mongo news_entities      -> Postgres entities, entity_aliases, story_entities
Mongo news_enrichments   -> Postgres stories, claims, timeline_entries, publications
Mongo news_content       -> chi dung noi bo pipeline, khong bat buoc sync
Mongo news_embeddings    -> optional, chi sync neu can vector search production
```

Primary key mapping:

```text
Mongo _id = article_id = uuid5(canonical_news_url)
Postgres articles.id = same article_id
Postgres story_sources.article_id = same article_id
Postgres claims.article_id = same article_id
```

## 4. Nhung thu khong nam trong DB schema chinh

Khong tao bang/collection cho cac phan sau trong thiet ke refactor nay:

```text
batch_id
correlation_id
airflow_runs
kaggle_jobs
ai_batch_jobs
ai_batch_locks
ai_enrichment_work
processed_events
outbox
publication_outbox
crawl_attempts
raw_html
raw_model_output
request logs
worker logs
```

Neu can quan sat runtime, dung log cua process/container. Neu can retry don gian,
publisher co the chay lai idempotent bang `url`, `article_id`, `slug`, va primary
keys tu schema san pham.

## 5. Duplicate And Automation Guarantees

Crawler khong crawl lai bai da co:

```text
canonical_url -> article_id = uuid5(canonical_url) -> news_metadata._id
```

Neu `news_metadata._id` da ton tai, scheduled crawler skip ngay truoc khi fetch
article page. Unique index tren `canonical_url` la lop bao ve thu hai.

Pipeline khong co human review:

- Processor tu validate JSON/enrichment/evidence.
- Publisher chi sync `validation_status = "VALIDATED"`.
- Record fail validation khong day len Supabase product table.
- Loi runtime nam trong Airflow/process logs, khong nam trong DB schema chinh.

## 6. Thu tu refactor de xay schema nay

1. Tao Mongo models moi theo 5 collection tren.
2. Tao Supabase migrations cho cac bang product.
3. Viet publisher local: Mongo -> Supabase upsert.
4. Chuyen backend API sang chi doc Supabase.
5. Chuyen frontend sang goi backend API moi.
6. Don code cu lien quan den outbox/batch/job state trong DB neu khong con dung.
   Kafka van giu cho local pipeline handoff.

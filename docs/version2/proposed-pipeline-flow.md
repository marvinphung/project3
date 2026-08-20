# Proposed Local Pipeline Flow

## Muc tieu

Pipeline version 2 chay local de tao va cap nhat du lieu moi:

```text
crawl -> process -> publish
```

Pipeline ghi MongoDB truoc, sau do publisher sync du lieu da xu ly len Supabase
PostgreSQL. Backend API deploy Render chi doc Supabase, khong tham gia pipeline.

Kafka va Airflow van duoc dung trong local pipeline:

- Airflow schedule va dieu phoi cac buoc lon.
- Kafka handoff article moi giua crawler, processor, publisher.

Khong luu outbox, processed event, batch/job state trong DB schema chinh.
`news-aggregator` dung Prefect thay vi Airflow, nhung flow pattern van ap dung
duoc: crawl flow -> enrichment flow -> publish/read flow.

## 0. Automation policy

Version 2 pipeline phai chay 100% tu dong:

- Khong co human review nam giua crawl, process, publish.
- Crawler tu skip bai da crawl bang `article_id`.
- Processor tu validate enrichment output bang rule/code.
- Publisher chi sync record dat validation sang Supabase.
- Output khong dat validation thi bo qua publish va ghi log runtime, khong tao
  queue review trong DB.
- Manual command chi de debug/replay local, khong phai buoc bat buoc trong flow
  san xuat du lieu.

## 0.1 Parallel processing policy

Pipeline duoc phep xu ly song song ben trong tung stage, nhung boundary giua cac
stage van ro rang:

```text
Airflow orchestration:
crawl stage -> process/entities stage -> Kaggle enrichment stage -> publish stage

Inside each stage:
worker pool xu ly nhieu source/article cung luc
```

Quy tac:

- Airflow khong tao task cho tung article.
- Airflow chi trigger command/stage lon.
- Crawler, processor, Kaggle adapter, va publisher tu quan ly worker pool rieng.
- Kafka chi handoff pointer event giua stage, khong chua full article payload.
- Moi stage phai idempotent de co the chay lai ma khong tao duplicate.
- Concurrency phai co cap global va cap theo domain/provider de tranh rate limit.

## 1. Identity chung

Moi bai news co `article_id` on dinh:

```python
article_id = uuid.uuid5(NEWS_URL_NAMESPACE, canonical_news_url)
```

Dung chung o tat ca lop:

```text
Mongo news_metadata._id
Mongo news_content._id
Mongo news_entities._id
Mongo news_enrichments._id
Mongo news_embeddings._id
Supabase articles.id
Supabase story_sources.article_id
Supabase claims.article_id
```

Vi vay pipeline co the chay lai ma khong tao duplicate neu URL canonical khong doi.

## 2. Airflow flow

Airflow local dieu phoi cac DAG/task cap pipeline:

```text
footballpulse_crawl
  -> run crawler
  -> publish news.crawled.v1

footballpulse_process
  -> consume news.crawled.v1 or scan Mongo fallback
  -> write news_entities/news_enrichments
  -> publish news.enriched.v1

footballpulse_publish
  -> consume news.enriched.v1 or scan Mongo fallback
  -> upsert Supabase
```

Airflow chi schedule/task orchestration. Airflow khong xu ly business logic tung
article trong DAG file.

### Airflow schedule

Lich chay de xuat cho MVP:

```text
footballpulse_crawl      */30 * * * *      every 30 minutes
footballpulse_process    trigger-after-crawl, fallback */30 * * * *
footballpulse_publish    trigger-after-process, fallback */15 * * * *
footballpulse_reconcile  0 3 * * *         daily local reconciliation
```

Quy tac:

- `catchup=False` cho cac DAG crawl/process/publish de tranh backfill tao load
  khong can thiet.
- `max_active_runs=1` cho tung DAG de tranh hai lan crawl/process cung luc.
- Crawl/process/publish nen trigger noi tiep sau khi step truoc thanh cong.
- Fallback schedule giup pipeline tu hoi phuc neu Kafka event bi missed hoac task
  trigger fail.
- `footballpulse_reconcile` scan Mongo `news_enrichments.validation_status =
  "VALIDATED"` va upsert lai Supabase de sua missing sync, van idempotent.
- Neu nguon tin/API bi rate limit, giam `footballpulse_crawl` tu 30 phut xuong
  60 phut ma khong doi kien truc.

## 3. Command flow for local manual runs

Manual run van co script theo thu tu de debug/replay. Day khong phai human review
step va khong nam giua flow tu dong:

```bash
uv run python -m footballpulse_pipeline crawl
uv run python -m footballpulse_pipeline process
uv run python -m footballpulse_pipeline publish
```

Crawler command hien tai co the chay toan bo hoac tung pha rieng:

```bash
uv run python -m footballpulse_pipeline crawl --step discovery
uv run python -m footballpulse_pipeline crawl --step content
uv run python -m footballpulse_pipeline crawl --step all
```

CLI crawl support:

- `--source` de chon source trong catalog.
- `--max-articles` de gioi han batch content fetch.
- `--concurrency` cho Step 2 extraction worker.
- `--max-age-days` de loc bai theo `published_at`.
- `--list-sources` de in source catalog hien co.

## 4. Kafka topics

Topic toi thieu:

```text
news.crawled.v1
news.enriched.v1
```

`news.crawled.v1` payload toi thieu:

```json
{
  "article_id": "uuid",
  "canonical_url": "https://example.com/article",
  "source_name": "BBC Sport",
  "published_time": "2026-08-18T08:00:00Z"
}
```

`news.enriched.v1` payload toi thieu:

```json
{
  "article_id": "uuid",
  "event_type": "TRANSFER",
  "validation_status": "VALIDATED",
  "processed_at": "2026-08-18T08:20:00Z"
}
```

Payload Kafka chi mang pointer nhe. Full content/entities/enrichment nam trong
Mongo theo `_id = article_id`.

## 5. `pipeline/crawler`

### Input

```text
Source catalog (CATALOG trong scripts/run-real-crawl.py)
FOOTBALLPULSE_V2_MONGODB_URL / FOOTBALLPULSE_MONGODB_URL
FOOTBALLPULSE_V2_MONGODB_DB / FOOTBALLPULSE_MONGODB_DB
FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS
FOOTBALLPULSE_CRAWL_MODE=scheduled|bootstrap
FOOTBALLPULSE_BROWSER_FALLBACK=true|false
```

### Crawl method

Pipeline crawl hien tai da tach 2 pha ro rang:

```text
Step 1: discovery -> filter age/domain -> canonicalize URL -> seed news_metadata
Step 2: query metadata chua co content -> fetch HTML -> extract text -> write news_content -> publish Kafka
```

Thu tu uu tien:

1. RSS la primary method cho source `RSS`.
2. Sitemap duoc ho tro nhu mot source type rieng.
3. HTML listing duoc dung cho source `HTML` khi can explicit opt-in.
4. Browser fallback chi duoc bat o Step 2 neu static extraction that bai hoac gap domain can render.

### Step 1: Discovery & Metadata Seeding

- Lay source tu catalog va co the filter bang `--source`.
- Moi source fetch toi da `500` entries (`V2_CANDIDATE_LIMIT`).
- RSS parser validate domain, title, URL va giu them `published_at`, `description`, `image_url`.
- URL duoc canonicalize truoc khi sinh `article_id`.
- Filter bai theo `published_at` trong cua so `--max-age-days` (mac dinh `30` ngay).
- `seed_metadata()` chi ghi `news_metadata` neu `_id` chua ton tai.
- Output cua Step 1 la:
  - `discovered`: so candidate tim duoc
  - `existing`: da co trong `news_metadata`
  - `seeded`: moi duoc dua vao backlog extraction

### Step 2: Content Extraction & Event Publish

- `get_unextracted_articles()` query `news_metadata` khong co ban ghi tuong ung trong `news_content`.
- So article duoc xu ly o Step 2 = `min(--max-articles, fetch_limit)` nhan voi so source duoc chon.
- `fetch_limit` = `100` cho scheduled mode, `500` neu `FOOTBALLPULSE_CRAWL_MODE=bootstrap`.
- Extraction chay song song theo `--concurrency` (mac dinh `6`).
- Primary path dung `HtmlFetcher` + `HtmlExtractionService`.
- Neu static extraction that bai, crawler co the fallback sang browser renderer cho mot so source/domain cu the.
- `write_content()` chi ghi `news_content` neu text hop le va extraction khong fail.
- Chi sau khi `write_content()` thanh cong moi publish `news.crawled.v1`.
- Kafka event van chi chua pointer nhe (`article_id`, `canonical_url`, `source_name`, `published_time`), khong day full content len topic.

### Mongo write model trong crawler

- `news_metadata`: du lieu seed tu discovery, dai dien backlog crawl.
- `news_content`: noi dung da duoc lam sach sau extraction.
- Crawler v2 hien tai khong luu crawl state vao `news_*` collections; phan crawl control/state nam ngoai write model nay.

### Fetch va extraction stack

```text
httpx client -> RSS/Sitemap/HTML fetchers -> HtmlExtractionService
-> browser fallback (khi can) -> Mongo -> Kafka
```

### Replay/debug policy

- Chay rieng `--step discovery` de seed lai metadata ma khong fetch content.
- Chay rieng `--step content` de tiep tuc xu ly backlog `news_metadata` chua co `news_content`.
- Cac buoc nay idempotent theo `_id = article_id`, nen co the replay an toan.

Neu source bi rate limit, giam `--concurrency`, tat browser fallback neu can,
hoac tang Airflow crawl interval len 60 phut.

### Steps

1. Chon source tu `CATALOG` hoac bang `--source`.
2. Step 1 fetch RSS, sitemap, hoac HTML listing tuy theo `source_type`.
3. Validate domain, title, URL; filter `published_at` theo `--max-age-days`.
4. Canonicalize URL va sinh `article_id`.
5. `seed_metadata()` chi ghi `news_metadata` neu `_id` chua ton tai.
6. Step 2 query backlog tu `get_unextracted_articles()`.
7. Fetch HTML article page va extract noi dung.
8. Neu can, fallback sang browser renderer cho mot so source/domain.
9. `write_content()` ghi `news_content` va cap nhat `content_hash` trong `news_metadata`.
10. Publish Kafka `news.crawled.v1` chi khi content da duoc save thanh cong.

### Output Mongo

`news_metadata`:

```json
{
  "_id": "article_id",
  "url": "original_url",
  "canonical_url": "canonical_url",
  "domain_name": "bbc.com",
  "source_name": "BBC Sport",
  "title": "Article title",
  "description": "Description",
  "published_time": "UTC",
  "crawl_date": "UTC",
  "image_url": "https://...",
  "tags": [],
  "article_keywords": [],
  "content_hash": "sha256 or empty string before extraction",
  "language": "en"
}
```

`news_content`:

```json
{
  "_id": "article_id",
  "content": "cleaned article text",
  "cleaned_at": "UTC",
  "extractor": "TRAFILATURA|READABILITY|UNKNOWN",
  "extraction_status": "SUCCESS"
}
```

### Skip rules

Skip hoac khong publish article neu:

- URL canonical da co trong `news_metadata` o Step 1.
- Step 2 khong lay duoc text hop le.
- Extraction status la `FAILED`.
- Browser fallback cung that bai.

Ly do bo qua nam trong runtime log; crawler khong tao collection skip-state rieng
trong Mongo write model.

## 6. `pipeline/processor`

### Input

```text
Kafka news.crawled.v1
Mongo news_metadata
Mongo news_content
KAGGLE credentials neu dung Kaggle
Model config
```

### Selection

Processor uu tien consume Kafka `news.crawled.v1`. Khi replay/manual run,
processor co the scan Mongo de lay article co:

```text
news_metadata exists
news_content exists
news_enrichments missing OR force=true
```

Neu chi chay entity extraction rieng:

```text
news_entities missing OR force=true
```

Parallel entity policy:

```text
entity_workers: 4-8
```

Neu model local nang hoac may local yeu, giam xuong `2-4`. Entity extraction
duoc xu ly theo article doc lap va upsert theo `_id = article_id`.

Kaggle enrichment selection khong gioi han batch nho theo so bai. Moi lan chay
Kaggle adapter, tao dataset tu tat ca article du dieu kien nhung chua co
`news_enrichments` validated:

```text
news_metadata exists
news_content exists
news_enrichments missing OR news_enrichments.validation_status != "VALIDATED"
```

Noi dung dataset la file JSONL local, moi dong mot article:

```json
{
  "article_id": "uuid",
  "canonical_url": "https://example.com/article",
  "title": "Article title",
  "content": "Cleaned article content",
  "published_time": "2026-08-18T08:00:00Z",
  "entities": []
}
```

Dataset upload len Kaggle co the gom toan bo backlog chua enrichment vi Kaggle
chay GPU. Khong luu `batch_id` vao DB; dataset/kernel run chi la runtime artifact
local.

### Steps

1. Load metadata + content theo `article_id`.
2. Extract entities tu title/content.
3. Map entity mention sang canonical entity neu co local alias dictionary hoac
   Supabase entity alias snapshot.
4. Ghi `news_entities`.
5. Tao prompt/input AI tu title, content, entities.
6. Chay enrichment:
   - local model, hoac
   - Kaggle kernel theo pattern input dataset gom toan bo backlog -> push kernel
     -> poll -> download output.
7. Validate output toi thieu:
   - JSON parse duoc
   - co `summary_en` hoac `summary_vi`
   - claim evidence quote nam trong content
   - event_type nam trong enum cho phep
8. Ghi `news_enrichments`.
9. Optional: tao embedding va ghi `news_embeddings`.
10. Neu enrichment validated, publish Kafka `news.enriched.v1`.

Validation la automated gate. Neu output khong dat rule thi processor khong publish
`news.enriched.v1`. Khong tao human review queue trong DB.

### Output Mongo

`news_entities`:

```json
{
  "_id": "article_id",
  "entities": [],
  "model_name": "gliner2",
  "model_version": "fastino/gliner2-large-v1",
  "processed_at": "UTC"
}
```

`news_enrichments`:

```json
{
  "_id": "article_id",
  "event_type": "TRANSFER",
  "summary_en": "...",
  "summary_vi": "...",
  "claims": [],
  "validation_status": "VALIDATED",
  "model_name": "qwen3",
  "model_version": "qwen3-0.6b",
  "prompt_version": "article-enrichment-v1",
  "processed_at": "UTC"
}
```

### Failure behavior

- Neu entity extraction fail: khong ghi `news_entities`.
- Neu AI fail: khong ghi `news_enrichments`.
- Neu validation fail: co the ghi `news_enrichments.validation_status = "FAILED"`
  voi `error_code` ngan gon, nhung khong luu raw model output.
- Processor co the chay lai bang `force=true`.

### Kaggle artifacts

Kaggle adapter tao artifact local tam thoi, khong ghi vao Mongo/Postgres:

```text
.tmp/kaggle-runs/<timestamp>/
  input/articles.jsonl
  kernel/kernel-metadata.json
  output/enrichments.jsonl
```

Sau khi download output, processor map tung dong theo `article_id`, validate,
upsert `news_enrichments`, va publish `news.enriched.v1` cho tung article
validated.

## 7. `pipeline/publisher`

### Input

```text
Kafka news.enriched.v1
Mongo news_metadata
Mongo news_content
Mongo news_entities
Mongo news_enrichments
Supabase PostgreSQL
```

### Selection

Publisher uu tien consume Kafka `news.enriched.v1`. Khi replay/manual run,
publisher co the scan Mongo va chi sync article co du:

```text
news_metadata exists
news_content exists
news_enrichments.validation_status = "VALIDATED"
```

`news_entities` nen co, nhung khong bat buoc neu article khong detect duoc entity.

Parallel publish policy:

```text
publisher_workers: 4-8
```

Publisher co the upsert song song nhung phai dung stable primary key/unique key
de chay lai khong duplicate.

### Steps

1. Load eligible articles tu Mongo.
2. Upsert `sources`.
3. Upsert `articles` voi `articles.id = article_id`.
4. Upsert/map `entities` va `entity_aliases` neu enrichment/entities co canonical data.
5. Tim hoac tao `stories`.
6. Upsert `story_sources`.
7. Upsert `story_entities`.
8. Upsert `claims`.
9. Tao/update `timeline_entries`.
10. Optional: tao/update `publications` neu muon co bai tong hop tren UI.

### Story matching MVP

De don gian, publisher co the match story theo key deterministic:

```text
event_type + primary_entity_id + normalized_main_subject
```

Neu khong co primary entity:

```text
event_type + normalized_title_keyword
```

Sau nay co the nang cap story matching bang embedding/vector, nhung khong can trong
schema version 2 ban dau.

### Timeline MVP

Moi article validated co the tao mot timeline entry neu claim moi hoac story moi.

`happened_at` uu tien:

```text
published_time -> crawl_date -> processed_at
```

Khong dung 6-hour window trong API/schema v2. Neu muon gom nhom 6 gio, publisher
lam logic noi bo va van ghi ra `happened_at`.

### Idempotency

Publisher duoc phep chay lai.

Upsert keys:

```text
sources.domain_name
articles.id
entities(entity_type, slug)
entity_aliases.normalized_alias
story_entities(story_id, entity_id)
story_sources(story_id, article_id)
publications.slug
```

Claims can stable ID hoac unique key:

```text
claim_id = uuid5(CLAIM_NAMESPACE, story_id + article_id + predicate + evidence_quote)
```

Timeline entry can stable ID:

```text
timeline_id = uuid5(TIMELINE_NAMESPACE, story_id + article_id + first_claim_id)
```

## 8. Local source of truth per stage

```text
After crawler:
Mongo news_metadata + news_content

After processor:
Mongo news_entities + news_enrichments

After publisher:
Supabase articles + stories + claims + timeline_entries + publications
```

Neu Supabase bi sai, khong sua tay dau tien. Chay lai publisher tu Mongo neu Mongo
van dung.

Neu Mongo bi sai, sua crawler/processor roi chay lai pipeline.

## 9. Minimal data quality gates

Crawler gate:

- URL hop le.
- Domain nam trong source allowlist.
- Title khong rong.
- Cleaned content du dai.

Processor gate:

- Entity labels hop le.
- Enrichment parse duoc.
- Evidence quote nam trong `news_content.content`.
- `event_type` hop le.

Publisher gate:

- Article co metadata + content + validated enrichment.
- Source map duoc.
- Story title/summary khong rong.
- Claim neu co evidence phai gan duoc article.

## 10. Thu tu implement

1. Tao shared `article_id_from_url()` va `canonicalize_news_url()`.
2. Tao Mongo Beanie models.
3. Dinh nghia Kafka event DTO toi thieu cho `news.crawled.v1` va
   `news.enriched.v1`.
4. Implement crawler ghi `news_metadata` + `news_content` va publish
   `news.crawled.v1`.
5. Implement processor consume `news.crawled.v1`, ghi `news_entities` +
   `news_enrichments`, publish `news.enriched.v1`.
6. Tao Supabase migration.
7. Implement publisher consume `news.enriched.v1` va upsert `sources` +
   `articles`.
8. Implement publisher upsert `entities` + `stories`.
9. Implement publisher upsert `claims` + `timeline_entries`.
10. Tao Airflow DAG dieu phoi crawl/process/publish.
11. Implement backend API doc Supabase.
12. Chuyen frontend sang API contract moi.

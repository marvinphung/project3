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
uv run python -m pipeline.crawler crawl
uv run python -m pipeline.processor process
uv run python -m pipeline.publisher publish
```

Hoac mot command wrapper:

```bash
uv run python -m pipeline run
```

Wrapper chi goi ba buoc tren theo thu tu. Neu mot buoc fail thi dung, khong tiep
tuc publish du lieu dang do.

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
RSS source config
MONGODB_URL
MONGODB_DB
```

Source config co the la file local:

```yaml
global:
  max_urls_per_source: 500
  max_new_articles_per_source_per_run: 100
  global_fetch_concurrency: 10
  per_domain_concurrency: 2
  request_timeout_seconds: 20
  min_content_chars: 500

sources:
  - name: BBC Sport
    rss_url: https://feeds.bbci.co.uk/sport/football/rss.xml
    allowed_domains:
      - bbc.com
      - bbc.co.uk
    reliability_tier: 1
```

### Crawl method

Method mac dinh dua tren `news-aggregator`:

```text
RSS -> URL candidates -> dedupe -> async fetch -> extract -> Mongo -> Kafka
```

Thu tu uu tien:

1. RSS crawl la primary method.
2. Source listing crawl chi la fallback cho nguon khong co RSS hoac RSS qua thieu.
3. Browser scraping chi bat theo source neu async HTTP bi chan.

Moi scheduled run:

- Moi source lay toi da `500` URL candidate gan nhat.
- Crawler canonicalize toan bo URL candidate.
- Crawler tao `article_id = uuid5(canonical_url)`.
- Crawler bulk check Mongo `news_metadata._id`.
- Chi URL chua ton tai moi vao fetch queue.
- Scheduled run fetch toi da `100` bai moi moi source de tranh burst qua lon.

Bootstrap/backfill local:

- Co the dung `--mode bootstrap`.
- Moi source van check toi da `500` URL.
- Cho phep fetch toi da `500` bai moi moi source.
- Nen giu `per_domain_concurrency` thap, mac dinh `1-2`.

Fetch stack nen giong `news-aggregator`:

```text
curl_cffi -> cloudscraper -> httpx -> aiohttp -> optional Playwright/Patchright
```

Extraction stack:

```text
trafilatura.bare_extraction()
-> JSON-LD metadata
-> OpenGraph fallback
-> BeautifulSoup fallback
-> noise removal
-> language/content quality gate
```

Parallel crawl policy:

```text
global_fetch_concurrency: 10
per_domain_concurrency: 2
request_timeout_seconds: 20
```

Neu source bi rate limit, giam `per_domain_concurrency` cua source do xuong `1`
hoac tang Airflow crawl interval len 60 phut.

### Steps

1. Doc RSS sources.
2. Lay toi da `500` URL candidate moi source tu RSS/listing.
3. Canonicalize article URL.
4. Tao `article_id = uuid5(canonical_url)`.
5. Bulk check `news_metadata` theo `_id`.
6. Neu da co `_id` thi skip va khong fetch lai article page.
7. Dua URL moi vao async fetch queue, toi da `100` bai moi/source/run trong
   scheduled mode.
8. Fetch HTML article page bang fallback stack.
9. Extract title/description/published_time/image/tags.
10. Extract cleaned content bang Trafilatura, fallback BeautifulSoup.
11. Tinh `content_hash`.
12. Upsert Mongo:
    - `news_metadata`
    - `news_content`
13. Publish Kafka `news.crawled.v1` neu article moi.

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
  "content_hash": "sha256",
  "language": "en"
}
```

`news_content`:

```json
{
  "_id": "article_id",
  "content": "cleaned article text",
  "cleaned_at": "UTC",
  "extractor": "TRAFILATURA",
  "extraction_status": "SUCCESS"
}
```

### Skip rules

Skip article neu:

- URL canonical da co trong `news_metadata`.
- Fetch fail.
- Extractor khong lay duoc content co ich.
- Content qua ngan.
- Language khong phai English neu processor chi ho tro English.

Khong ghi skip reason vao DB. Neu can xem ly do, doc console log luc chay local.

Forced recrawl chi nen la flag debug ro rang, vi du `--force-url <url>`, va mac
dinh tat. Flow scheduled cua Airflow khong dung forced recrawl.

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
  "model_name": "gliner",
  "model_version": "urchade/gliner_small-v2.1",
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

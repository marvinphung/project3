# News Aggregator Reference

## Muc dich

Tai lieu nay tong hop lai full flow va architecture cua repo `../news-aggregator` de dung lam reference cho `project3`, nhat la cac phan orchestration, crawl pipeline, API database, va cach repo cu dung Kaggle kernel.

Ngay doc: `2026-08-18`

## 1. Tong quan repo

Repo `news-aggregator` duoc tach thanh 3 khoi chinh:

1. `aggregator`
   He thong ingestion va post-processing:
   - Crawl RSS va article pages
   - Day du lieu qua Kafka
   - Luu metadata/content vao database service
   - Goi MDERank de extract keywords + embeddings
   - Goi GLiNER/NER va OpenAI de tao summary, ranking, context phuc vu san pham
   - Orchestration bang `Prefect`

2. `database`
   FastAPI service dung MongoDB qua `Beanie` / `Motor`:
   - Luu document cho news, keywords, entities, embeddings
   - Luu document tong hop nhu keyword summaries, token summaries, lending summaries, technology rankings
   - Expose API cho `aggregator` doc/ghi

3. `mderank`
   Mot microservice FastAPI rat mong:
   - Nhan batch article content
   - Ghi input vao local files
   - Push dataset + kernel len Kaggle
   - Cho kernel chay xong
   - Download output ve
   - Tra lai `mde_keywords` va `embeddings`

## 2. Kien truc he thong o muc cao

Flow tong the:

1. RSS feeds -> `aggregator/news_scraper/crawler/get_urls.py`
2. Tung URL moi -> `extract_data_from_url()` trong `aggregator/news_scraper/crawler/extract_data.py`
3. Producer day article da extract vao Kafka topic `rss_documents`
4. Consumer doc Kafka va goi `database` API de luu:
   - `NewsMetadata`
   - `NewsContent`
5. Mot flow Prefect khac lay cac bai chua co keywords -> goi `mderank` service
6. `mderank` service goi Kaggle kernel de sinh:
   - `mde_keywords`
   - `embeddings`
7. Mot flow Prefect khac lay cac bai chua co entities -> goi GLiNER service ben ngoai
8. Cac flow tong hop tiep theo tao:
   - top keywords
   - keyword overview / FAQ / summary / token-affected
   - top technology / category summary / related projects
   - top lendings / lending summary
9. Frontend hoac service khac co the doc tu `database` API de lay context, trend, metadata, ranking.

## 3. Orchestration

### 3.1 Su dung Prefect, khong phai Airflow

Repo nay **khong dung Airflow**. No dung `Prefect` cho scheduling va orchestration:

- File chinh: `aggregator/prefect/deploy_flows.py`
- Dinh nghia flows: `aggregator/prefect/monitors.py`
- Ha tang Prefect: `aggregator/docker-compose.yaml`

Thanh phan Prefect trong Docker Compose:

- `postgres`: metadata DB cho Prefect
- `redis`: messaging/cache
- `prefect-migration`
- `prefect-server`
- `prefect-services`
- `prefect-worker`
- `prefect-app`: build tu repo `aggregator`, chay `python prefect/deploy_flows.py`

### 3.2 Cac flow da deploy

Theo `aggregator/prefect/deploy_flows.py`:

- `rss-crawler`: cron `0 */3 * * *`
- `keywords-extraction`: cron `0 */6 * * *`
- `entities-extraction`: cron `0 */6 * * *`
- `top-keywords`: cron `0 */12 * * *`
- `top-technology`: cron `0 0 * * 0`
- `top-lending`: cron `0 0 * * 0`

### 3.3 Y nghia thuc te cua tung flow

Theo `aggregator/prefect/monitors.py`:

- `rss-crawler`
  Chay song song `kafka_producer` va `kafka_consumer`.

- `keywords-extraction`
  Chay `keywords_extractor()` de extract MDE keywords va embeddings.

- `entities-extraction`
  Chay `entities_extractor()` de extract named entities bang GLiNER.

- `top-keywords`
  Chay `upload_keywords.upsert()` de tao ranking, summaries, FAQ, token affected.

- `top-technology`
  Chay `TopTechnology` de tao project related, category summaries, technology ranking.

- `top-lending`
  Chay `LendingTop.upsert_lending_data(TimeInterval.SEVEN_DAYS)`.

## 4. Ingestion pipeline

### 4.1 Lay URL moi tu RSS

File: `aggregator/news_scraper/crawler/get_urls.py`

Chuc nang:

- Hardcode danh sach RSS feeds crypto
- Goi `database.get_existing_urls()`
- Chi giu URL chua ton tai trong DB
- Bo qua video/podcast mot so site

Kieu dedupe:

- Dedupe o muc URL, dua tren endpoint `/news/metadata/urls` cua database API
- Mac dinh chi lay URL trong cua so thoi gian 30 ngay, vi `database/backend/news_search.py` filter `NewsMetadata` trong 30 ngay gan nhat

### 4.2 Fetch article HTML

File: `aggregator/news_scraper/clients/scraper_services.py`

Repo dung mot `AsyncWebScraper` theo chieu fallbacks:

- `curl_cffi`
- `cloudscraper`
- `httpx`
- `aiohttp`

Co san code cho:

- `patchright` / Playwright subprocess
- `ulixee hero`

nhung dang bi comment / chua bat chinh thuc.

He thong co random delay de tranh bot detection.

### 4.3 Extract metadata + content

File: `aggregator/news_scraper/crawler/extract_data.py`

`extract_data_from_url(url)` lam cac viec:

- Fetch raw HTML
- Tao `UUIDv5` tu URL lam article id
- Parse `domain_name`
- Dung `BeautifulSoup`
- Dung `trafilatura.bare_extraction()` de lay title va text
- Doc JSON-LD de lay:
  - `datePublished`
  - `description`
  - `keywords`
  - `articleSection`
- Lay them:
  - `og:image`
  - `author`
- Chay `ContentProcessor.remove_noise()` de cat bo disclaimer, ads, boilerplate
- Co heuristics detect sponsored content, nhung trong flow hien tai chua thay goi filter manh o entrypoint

Output la `NewsData` gom:

- `id`
- `url`
- `domain_name`
- `title`
- `content`
- `published_time`
- `tags`
- `article_keywords`
- `author`
- `crawl_date`
- `image_url`
- `description`

### 4.4 Kafka producer

File: `aggregator/news_scraper/kafka/producer.py`

Flow:

1. Tao topic neu chua ton tai
2. Lay URL moi tu RSS
3. Extract tung article
4. Serialize `NewsData`
5. Push vao topic Kafka

Chi tiet:

- Topic: lay tu config, template mac dinh la `rss_documents`
- Producer dung `AIOKafkaProducer`
- Create topic dung `confluent_kafka.admin.AdminClient`
- Concurrency limit bang `Semaphore(10)`
- Timeout tong 30 phut cho mot batch

### 4.5 Kafka consumer

File: `aggregator/news_scraper/kafka/consumer.py`

Flow:

1. Subscribe topic
2. Poll message
3. Parse JSON
4. Normalize `published_time`
5. Goi database API de luu:
   - metadata
   - content

Consumer khong ghi truc tiep Mongo. No goi HTTP sang database service qua:

- `save_news_metadata()`
- `save_news_content()`

Timeout cua consumer la `2000` giay.

## 5. Database service

### 5.1 Vai tro

`database` la persistence layer trung tam. Tat ca phan ghi/doc du lieu nghiep vu deu qua FastAPI service nay.

Entry point:

- `database/api/api_main.py`

Lifecycle:

- startup: `mongo_client.initialize()`
- shutdown: `mongo_client.close()`

### 5.2 Cong nghe

- `FastAPI`
- `Uvicorn`
- `Motor`
- `Beanie`
- `MongoDB`
- `Pydantic`

### 5.3 Security / access pattern

Moi request vao API deu di qua API key dependency:

- file: `database/api/dependencies.py`
- header name lay tu config `api_key.name`
- default template dung `API_KEY`

### 5.4 Cac router

Theo `database/api/routers/*`:

- `news`
  - read/write cho metadata, content, entities, keywords, embeddings
  - helper endpoints de lay IDs chua extract
  - helper endpoints cho domain name, technology tags

- `keywords`
  - luu metadata, summary, ranking, replaced, token_summary, token_affected, questions
  - read trend, summary by id, metadata by id

- `tokens`
  - lay token metadata
  - lay top tokens lien quan toi keyword trong mot time range

- `projects`
  - tim project metadata / project id theo ten

- `lendings`
  - luu lending summary, ranking
  - lay lending metadata

- `technology`
  - luu ranking, summary, related projects
  - lay technology metadata

- `utility`
  - hasher
  - lay context theo keyword, entity, token, lending

### 5.5 Data model Mongo

File: `database/mongo/schema.py`

Collections chinh:

- `news_metadata`
- `news_content`
- `news_entities`
- `news_keywords`
- `news_embeddings`
- `tokens_metadata`
- `keywords_metadata`
- `keywords_summary`
- `keywords_ranking`
- `keywords_replaced`
- `keywords_token_summary`
- `keywords_token_affected`
- `keywords_questions`
- `projects_metadata`
- `lendings_metadata`
- `lendings_summary`
- `lendings_ranking`
- `technologies_metadata`
- `technology_summary`
- `technology_ranking`
- `technology_projects_related`

Model lien ket du lieu bang `Link` cua Beanie, vi du:

- `KeywordsSummary.keyword -> KeywordsMetadata`
- `KeywordsTokenSummary.token -> TokensMetadata`
- `LendingsSummary.lending -> LendingsMetadata`
- `TechnologySummary.category -> TechnologyMetadata`

### 5.6 Query layer

Files:

- `database/backend/news_search.py`
- `database/backend/keywords_search.py`
- `database/backend/context_search.py`

Chuc nang:

- filter bai viet theo time range
- tim bai chua extract keywords/entities
- build context cho LLM tasks
- tinh trend keyword theo bucket 6 gio
- lay token lien quan toi keyword
- lay context theo entity / token / lending

Luu y:

- Nhieu query dang la application-side joins, khong phai aggregation pipeline toi uu
- Co giao cat set/list trong Python, vi du context token giao `token_ids` va `keyword_ids`
- Cac helper nay hop ly cho quy mo vua phai, nhung se thanh bottleneck neu data lon

## 6. MDERank va cach dung Kaggle

### 6.1 Vai tro

`mderank` khong tu infer trong local process. No la mot HTTP wrapper quanh Kaggle pipeline.

Entry point:

- `mderank/api/main.py`

Endpoint:

- `POST /mderank/`

Input:

- danh sach `MdeInput { id, content }`

Output:

- danh sach `MdeOutput { id, content, mde_keywords, embeddings }`

### 6.2 Flow run thuc te

File: `mderank/engine/run.py`

Khi API duoc goi:

1. `prepare_metadata()`
2. Tao `dataset-metadata.json` cho Kaggle dataset
3. Tao `kernel-metadata.json` cho Kaggle notebook
4. Set `KAGGLE_USERNAME` va `KAGGLE_KEY`
5. Ghi input thanh `input/input.json`
6. Goi `run_pipeline()`
7. Doc `output/output.json`
8. Tra ve cho caller

### 6.3 `run_pipeline()` lam gi

File: `mderank/engine/kaggle_scripts.py`

Thu tu:

1. `kaggle datasets version -p input/ ...`
2. `kaggle kernels push -p notebook/`
3. polling `kaggle kernels status`
4. `kaggle kernels output ... -p output/`

Day la pattern quan trong cua repo cu:

- Dong goi input thanh Kaggle dataset
- Push notebook/kernel
- Cho kernel complete
- Download output file

### 6.4 Metadata Kaggle

Template config:

- `mderank/app-config-template.yaml`

Fields:

- `username`
- `key`
- `dataset`
- `notebook`

Gia tri mac dinh:

- dataset: `rss-data`
- notebook: `mderank-service`

### 6.5 Nhan xet

Kien truc nay la asynchronous theo cap process nhung khong phai event-driven that su:

- HTTP request vao `mderank` co the block rat lau khi cho Kaggle xong
- Service nay dong vai tro adapter/orchestrator hon la inference service thuan

## 7. Keywords va embeddings pipeline

File chinh:

- `aggregator/news_processor/processor/news/mde_keywords.py`

Flow:

1. Goi database API lay IDs chua co keywords
2. Lay content tung bai
3. Gom batch thanh `MdeInput`
4. Goi `mde.extract()` -> HTTP sang `mderank`
5. Nhan ve `mde_keywords` va `embeddings`
6. Ghi nguoc vao database API:
   - `/news/keywords`
   - `/news/embeddings`

Luu y:

- Co `sleep(20)` sau moi 50 item
- Comment trong code noi day la workaround tranh rate limit

## 8. Entities pipeline

File chinh:

- `aggregator/news_processor/processor/news/entities.py`
- `aggregator/news_processor/clients/ner_service.py`

Flow:

1. Lay IDs chua co entities
2. Lay article content
3. Goi external GLiNER endpoint `https://dev.loomix.ai/v1/api/model/gliner`
4. Nhan ve entities labels:
   - `Token Cryptocurrency`
   - `Lending Pool`
   - `Chain`
   - `Exchange`
   - ...
5. Luu vao `/news/entities`

Co them `NerProcessor` goi endpoint `.../model/ner` de enrich entities trong summary texts sau nay.

## 9. Top keywords pipeline

Files chinh:

- `aggregator/news_processor/processor/keywords/top_keywords.py`
- `aggregator/news_processor/processor/keywords/upload_keywords.py`
- `aggregator/news_processor/llm/llm_tasks.py`

### 9.1 Chon top keywords

`TopKeywords.get_top_keywords()`:

- Lay keyword docs trong mot time interval
- Doi chieu voi entities trong bai
- Bo stopwords
- Score theo:
  - tan suat bai nhac den keyword
  - domain ranking tu `domain_ranking.json`
- Loai bo keywords overlap / gan giong bang:
  - Jaccard similarity
  - overlap word checks
- Chi giu keyword co lien quan den crypto tokens
- Co logic `replaced_keyword` de map short keyword sang phrase dai hon neu phu hop

### 9.2 Tao output cho tung keyword

`UpsertDocuments.upsert()` se tao:

- `KeywordsMetadata`
  overview + thumbnail

- `KeywordsQuestions`
  FAQ duoc LLM generate

- `KeywordsSummary`
  main event + bullet summaries + trend

- `KeywordsTokenSummary`
  summary cho cap `keyword x token`

- `KeywordsTokenAffected`
  tap token bi anh huong boi keyword

- `KeywordsRanking`
  ranking tong hop cho time interval

### 9.3 LLM stack

Files:

- `aggregator/news_processor/llm/llm_infer.py`
- `aggregator/news_processor/llm/llm_tasks.py`
- `aggregator/news_processor/llm/prompts.py`
- `aggregator/news_processor/clients/openai_service.py`

Cong nghe:

- `AzureOpenAI`
- models:
  - `gpt-4o`
  - `gpt-4o-mini`
  - `text-embedding-3-small` duoc khai bao, nhung embeddings chinh trong pipeline nay dang di qua MDERank

LLM duoc dung cho:

- keyword overview
- keyword summary
- token-event relationship
- keyword FAQ
- lending summary
- technology category classification
- technology category summary
- alert generation

## 10. Technology pipeline

File: `aggregator/news_processor/processor/technology/upload_technology.py`

Flow:

1. Lay cac bai co `tags` hoac `article_keywords` chua `tech|technology`
2. Goi LLM classify moi bai vao category blockchain/AI/DeFi/... 
3. Nhom bai theo category
4. Goi LLM tao category summary
5. Parse `projects` duoc nhac den
6. Map sang `ProjectsMetadata`
7. Ghi 3 loai output:
   - `TechnologyProjectsRelated`
   - `TechnologySummary`
   - `TechnologyRanking`

Day la pipeline co tinh semantic-heavy rat cao, phu thuoc LLM nhieu.

## 11. Lending pipeline

File: `aggregator/news_processor/processor/lending/top_lendings.py`

Flow:

1. Lay entities label `Lending Pool` trong time range
2. Dem tan suat mention theo bai
3. Map entity text sang `LendingsMetadata`
4. Goi LLM tao lending summaries
5. Ghi:
   - `LendingsSummary`
   - `LendingsRanking`

## 12. Config va service boundaries

### 12.1 Aggregator config

`aggregator/app-config-template.yaml`:

- `database.host/port/api_key`
- `kafka.host/port/topic`
- `centic.centic_api`
- `openai.openai_api_key`
- `openai.api_version`
- `mde.host/port`

### 12.2 Database config

`database/app-config-template.yaml`:

- `api_key.name/value`
- `mongo.host/port/username/password/database`

### 12.3 MDERank config

`mderank/app-config-template.yaml`:

- `kaggle.username`
- `kaggle.key`
- `kaggle.dataset`
- `kaggle.notebook`

### 12.4 Boundary thuc te giua cac service

- `aggregator` khong truy cap Mongo truc tiep
- `aggregator` doc/ghi qua HTTP vao `database`
- `aggregator` goi `mderank` qua HTTP
- `mderank` noi chuyen voi Kaggle CLI
- `aggregator` goi external APIs cho NER/GLiNER/OpenAI/Bing

## 13. Cong nghe duoc su dung

### 13.1 Trong `aggregator`

- Python 3.10
- Prefect
- Kafka
- Zookeeper
- aiohttp / httpx / curl_cffi / cloudscraper
- BeautifulSoup
- Trafilatura
- FastAPI
- OpenAI Azure client
- Patchright / Playwright hooks (dang de san nhung chua bat chinh thuc)
- Pydantic
- OpenTelemetry logging

### 13.2 Trong `database`

- FastAPI
- Uvicorn
- MongoDB
- Motor
- Beanie
- Pydantic
- OpenTelemetry logging

### 13.3 Trong `mderank`

- FastAPI
- Kaggle CLI
- Kaggle notebook/kernel
- Uvicorn
- OpenTelemetry logging

## 14. Diem quan trong can mang sang `project3`

Neu dung repo nay lam reference, cac pattern quan trong la:

1. Tach ingestion, persistence, va enrichment thanh service boundaries ro rang.
2. Dung orchestrator rieng cho scheduled pipelines.
3. Persistence layer co API rieng thay vi de processor ghi DB truc tiep.
4. Batch enrichment co the di qua adapter service roi moi den remote compute platform.
5. Pattern Kaggle cua repo cu la:
   `prepare input -> publish dataset -> push kernel -> poll status -> pull output`.

## 15. Khac biet / han che cua repo cu

Nhung diem nay quan trong vi de "hoc lai flow" nhung khong nen copy nguyen:

1. Khong co Airflow.
   Repo nay dung Prefect. Neu `project3` dung Airflow thi chi nen hoc pattern orchestration va chia pipeline, khong hoc 1:1 implementation.

2. `mderank` la synchronous adapter cho Kaggle.
   HTTP request co the bi block lau, rat kho scale neu traffic tang.

3. Nhieu joins va filtering dang lam o app layer.
   O quy mo lon, database query hien tai se la bottleneck.

4. Pipeline phu thuoc manh vao external services:
   - GLiNER endpoint
   - custom NER endpoint
   - Azure OpenAI
   - Bing image search
   - Kaggle CLI

5. Heuristics cleanup/noise removal rat thu cong.
   Co nhieu rule hardcode trong `ContentProcessor.remove_noise()`.

6. Scheduling chia theo lo keyword/entity/technology/lending, nhung chua co contract/event model thong nhat xuyen suot he thong.

## 16. Ket luan ngan

`news-aggregator` la mot he thong pipeline-oriented gom:

- `aggregator` cho crawl + orchestration + semantic processing
- `database` cho persistence va query API
- `mderank` cho keyword extraction qua Kaggle

Flow cua no la:

`RSS -> article fetch/extract -> Kafka -> database API -> keyword/entity enrichment -> LLM summarization/ranking -> read APIs for product`.

Neu dung lam reference cho `project3`, phan nen hoc nhieu nhat la:

- cach cat boundary giua services
- cach de orchestrator dieu phoi nhieu pipeline doc lap
- cach wrap Kaggle kernel thanh mot enrichment step co input/output contract ro rang


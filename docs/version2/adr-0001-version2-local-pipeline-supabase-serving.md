# ADR-0001: Version 2 Local Pipeline And Supabase Serving

## Status

Accepted for Version 2 planning.

## Date

2026-08-18

## Context

Version 1 is hard to follow because the architecture mixes production API concerns with local pipeline concerns. The database also stores too much operational state, such as batch/job/log/outbox-style data, while the product UI only needs clean football news data.

The target Version 2 deployment model is:

- Frontend runs on Vercel.
- Backend API runs on Render.
- Supabase PostgreSQL stores the data served by the backend API.
- Crawl, processing, enrichment, Kafka, Airflow, Kaggle integration, and MongoDB run locally.

The `news-aggregator` reference remains useful for these patterns:

- Kafka producer/consumer handoff between pipeline stages.
- MongoDB document modeling with Beanie, Motor, and Pydantic.
- Kaggle dataset/kernel/poll/output workflow.

However, Version 2 should not copy the reference project directly because this project still needs Airflow for orchestration, not Prefect.

## Decision

Adopt a split architecture:

- Local pipeline owns crawling, processing, enrichment, Kafka events, Airflow orchestration, MongoDB, and publishing to Supabase.
- Production backend owns public API contracts and reads only from Supabase PostgreSQL.
- Frontend owns presentation and calls only the backend API.

MongoDB is the local pipeline store. It stores crawled and processed article data in `news_*` collections:

- `news_metadata`
- `news_content`
- `news_entities`
- `news_enrichments`
- `news_embeddings`, optional

MongoDB documents use deterministic UUID article IDs:

```text
article_id = uuid5(NEWS_URL_NAMESPACE, canonical_news_url)
```

The same article ID is reused in Supabase PostgreSQL where the backend API reads product-ready data.

Supabase PostgreSQL is the product serving database. It stores normalized API-facing data:

- `sources`
- `articles`
- `entities`
- `entity_aliases`
- `stories`
- `story_entities`
- `story_sources`
- `claims`
- `timeline_entries`
- `publications`

Airflow remains the local orchestrator. The initial DAG boundaries are:

- `footballpulse_crawl`: crawl sources, write MongoDB, publish `news.crawled.v1`.
- `footballpulse_process`: read Kafka or Mongo fallback, enrich data, write MongoDB, publish `news.enriched.v1`.
- `footballpulse_publish`: read Kafka or Mongo fallback, upsert validated data into Supabase.

Default Airflow schedule:

```text
footballpulse_crawl      */30 * * * *
footballpulse_process    trigger-after-crawl, fallback */30 * * * *
footballpulse_publish    trigger-after-process, fallback */15 * * * *
footballpulse_reconcile  0 3 * * *
```

All crawl/process/publish DAGs should use `catchup=False` and `max_active_runs=1`.
Airflow must orchestrate stages only; it must not create one task per article.

Crawler policy:

- Each source checks up to 500 URL candidates per scheduled run.
- URL canonicalization and `uuid5(canonical_url)` dedupe happen before HTML fetch.
- Scheduled runs fetch up to 100 new articles per source.
- Bootstrap runs may fetch up to 500 new articles per source.
- Fetching runs in a bounded worker pool with global and per-domain concurrency.

Processing policy:

- Entity extraction runs in parallel by article.
- The pipeline has no human review step between crawl, process, and publish.
- Validation is automated; only validated enrichments are published onward.
- Kaggle input dataset contains all articles with content but without validated enrichment.
- Kaggle run state stays in local artifacts, not in MongoDB or PostgreSQL.

Kafka remains the local pipeline handoff mechanism. Kafka messages should be small pointer events, not full article payloads:

```json
{
  "article_id": "uuid",
  "canonical_url": "https://example.com/news/article",
  "source_name": "example",
  "published_time": "2026-08-18T00:00:00Z"
}
```

Full content, entities, enrichments, and optional embeddings stay in MongoDB and are loaded by `article_id`.

Do not store operational logs or pipeline state in the main MongoDB or PostgreSQL schemas. This includes:

- `batch_id`
- batch status tables
- Airflow run state
- Kaggle job state
- generic pipeline logs
- outbox tables
- processed event tables

Runtime debugging should use Airflow logs, process/container logs, and temporary local artifacts, not product database tables.

The frontend must not show pipeline flow/status. The user-facing product should show football news, stories, entities, timelines, claims, publications, and search results from backend API data.

## Alternatives Considered

### Keep Version 1 Service-Heavy Architecture

Rejected. It keeps too much internal workflow state in the application architecture and database, making the system harder to inspect and refactor.

### Remove Kafka And Airflow

Rejected. Kafka and Airflow are still required for local orchestration and stage handoff. They should be kept local and excluded from production serving.

### Let Backend Read MongoDB Directly

Rejected. Render backend should not depend on a local MongoDB instance. Supabase PostgreSQL is the production serving boundary.

### Let Frontend Query Supabase Directly

Rejected. The backend API should own response contracts, filtering rules, pagination, and future authorization behavior. The frontend should not couple directly to database tables.

### Copy `news-aggregator` Prefect Flow

Rejected. The reference project's flow pattern is useful, but this project should implement orchestration with Airflow.

### Store Pipeline Logs And Job State In DB

Rejected. The current requirement is to avoid DB clutter. Pipeline observability belongs in logs and local runtime tools unless a concrete product requirement appears later.

## Consequences

Positive outcomes:

- Production deploy becomes simpler: Vercel frontend, Render backend, Supabase PostgreSQL.
- Backend API is independent from MongoDB, Kafka, Airflow, crawler, processor, and Kaggle runtime.
- MongoDB remains flexible for crawl and enrichment documents.
- Supabase PostgreSQL remains clean and optimized for product queries.
- Deterministic UUIDs make deduplication and Mongo/Postgres synchronization straightforward.
- Bounded crawler concurrency avoids unnecessary recrawls and reduces source rate-limit risk.
- Kaggle can use GPU efficiently by processing the whole enrichment backlog in one uploaded dataset.

Tradeoffs:

- The publisher must be idempotent because it is the only bridge from local pipeline data to Supabase.
- Local development still needs Kafka and Airflow setup.
- Pipeline debugging depends on logs and local artifacts instead of database log tables.
- Refactor work must remove or isolate Version 1 internal service boundaries carefully.
- A large Kaggle backlog can make one enrichment run slower, so the adapter needs clear timeout and output validation behavior.

## Follow-Up Documents

- `docs/version2/proposed-db-schema.md`
- `docs/version2/proposed-service-boundary.md`
- `docs/version2/proposed-api-contract.md`
- `docs/version2/proposed-technology-stack.md`
- `docs/version2/proposed-pipeline-flow.md`
- `docs/version2/refactor-implementation-plan.md`

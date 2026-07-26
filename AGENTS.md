# FootballPulse Repository Instructions

## Scope and precedence

This file applies to the entire repository. Before changing a file, also read any
closer `AGENTS.md`; the closest file takes precedence for its subtree.

FootballPulse is a three-week university Project 3 and portfolio project:

- Vietnamese title: **Thiết kế và xây dựng nền tảng tự động thu thập, tổng hợp
  và xuất bản tin tức bóng đá theo kiến trúc microservices**
- English title: **FootballPulse — Automated Football News Intelligence Platform**
- Student: **Phùng Minh Vũ**
- Student ID: **20235252**

The primary learning and portfolio goals are backend engineering,
microservices, distributed systems, concurrent network processing,
event-driven asynchronous pipelines, correctness under at-least-once delivery,
and grounded AI/NLP integration. The finished MVP must be fully reproducible on
localhost and demonstrable offline.

## Repository state at initialization

Verified on 2026-07-26:

- The repository root contains only `README.md`, `.gitignore`, and this file.
- `README.md` contains only the heading `# project3`.
- `.gitignore` contains Go binary/test-output patterns, ignores `go.work`,
  `go.work.sum`, and `.env`, and has no broader multi-language rules yet.
- The Git branch is `main`; the initial commit is the only commit.
- No application source, service directories, module/package manifests,
  dependency locks, Docker/Compose files, migrations, schemas, tests,
  generated code, CI configuration, or development scripts exist yet.
- No build, test, lint, migration, Docker, or development command has been
  verified. All commands in those categories are **TBD** until their owning
  files are added and the commands are executed successfully.
- No service-specific instructions currently exist.

Do not describe any planned component below as implemented unless the
repository has subsequently gained and verified it. Update this section when
the repository state materially changes.

## Product invariant and domain model

Always preserve:

```text
Source Article != Story != Generated News Article
```

### Source Article

An immutable evidence record collected from RSS, HTML, an official site, or a
deterministic mock source. Preserve its original and canonical URLs, source,
original title, parsed content, available author and publication time,
collection time, content hash, processing status, duplicate relationships,
entities, category, and story assignment. Never overwrite it with generated
content and never discard it merely because it is a duplicate.

### Story

A structured, evolving real-world football event. It groups supporting source
articles and owns a working headline, category, canonical entities, timeline,
claims, confirmation level, summary, version, editorial status, and
timestamps. A matching update should extend an existing story rather than
create a new one.

### Generated News Article

Editorial content derived only from supported story claims. It owns a generated
headline, description, body, source references, entities, prompt/model/provider
metadata, input story version, revisions, editorial state, and publication
metadata. It must always be identifiable as generated content, not evidence.

MVP entities are `Player`, `Coach`, `Club`, and `Competition`. Aliases such as
Manchester United, Man United, Man Utd, and MUFC must resolve to one canonical
entity, with editor correction available.

MVP event categories are deliberately limited to:

```text
TRANSFER
INJURY
MATCH
PRESS_CONFERENCE
OFFICIAL_ANNOUNCEMENT
```

Confirmation levels are:

```text
RUMOUR
REPORTED
MULTI_SOURCE
OFFICIAL
```

Never strengthen uncertainty during extraction, summarization, generation, or
publication. In particular, reported interest must not become a completed
transfer without claims and sources that support that conclusion.

## Required end-to-end outcome

Optimize for this working vertical slice:

```text
News sources
→ collection
→ parsing and normalization
→ exact and near-duplicate detection
→ entity extraction and resolution
→ event classification
→ story match or creation
→ timeline and claim update
→ source-grounded draft generation
→ editorial review
→ approval or rejection
→ publication
→ public website
```

A crawler-only, AI-only, backend-only, or frontend-only result is incomplete.
Prefer one reliable end-to-end path over broad incomplete scaffolding.

The deterministic offline demo is a first-class requirement. It must eventually
cover a developing transfer across sources, aliases, an exact duplicate, a
near-duplicate, 429/500/timeout behavior, an official update, an unrelated
injury story, a match article, draft review/publication, a later update to the
same story, duplicate delivery, and worker restart. Internet access and
external LLM credentials must never be mandatory for tests or the demo.

## Planned architecture (not yet implemented)

Use a small number of meaningful services with explicit business ownership.
Do not create network services for trivial helpers.

| Component | Planned technology | Responsibility and owned data |
| --- | --- | --- |
| API Gateway | Go | Single public/admin HTTP entry point, auth/RBAC, validation, middleware, routing; owns no article/story/publication logic |
| Source Service | Go | Source definitions, crawl policies, histories, and crawl-batch requests |
| Collector Service | Go | Safe bounded concurrent RSS/HTML fetching, retries/rate limits, and raw article events |
| Article Service | Go | Parsing, normalization, metadata, hashes, duplicate detection, and source articles |
| Intelligence Service | Python | Entities, aliases, classification, claims, story matching, timelines, and correction workflows |
| AI Content Service | Python | Deterministic mock and optional external generation from grounded claims, with structured validation |
| Content Service | Go | Drafts, revisions, editorial state, audit history, idempotent publication, and public article data |
| Web application | Next.js/TypeScript | One application containing public news pages and admin/editorial tools |
| Mock News Source | TBD implementation | Deterministic RSS/HTML fixtures and controllable failure/progression scenarios |
| Airflow | Python DAGs | Workflow scheduling, batches, backfills, reprocessing, checks, and demos—not per-article business logic |

Planned infrastructure:

- Kafka: asynchronous cross-service event backbone.
- PostgreSQL: durable source of truth, with one schema or database per service.
- Redis: rate limits, cache, and temporary coordination only.
- Docker Compose: reproducible localhost deployment.
- OpenAPI: synchronous API contracts.
- Versioned JSON Schema, Protobuf, or another explicitly selected format:
  Kafka event contracts. The format is **TBD**.
- Prometheus, Grafana, and Kafka UI: optional after the core slice works.

The preferred initial AI worker design is direct Kafka consumption. ARQ may be
introduced only for a documented, bounded internal Python job need. Never send
the same job independently through Kafka and ARQ.

### Planned repository layout

The following layout is a target, not current repository state. Create only the
parts required by the active vertical slice:

```text
services/
  api-gateway/
  source-service/
  collector-service/
  article-service/
  intelligence-service/
  ai-content-service/
  content-service/
web/
airflow/dags/
contracts/openapi/
contracts/events/
infrastructure/{docker,kafka,postgres,redis,monitoring}/
mock-news-source/
test/{fixtures,integration,end-to-end,load}/
docs/
scripts/
docker-compose.yml
Makefile
.env.example
README.md
AGENTS.md
```

## Boundaries and data ownership

- Each service owns a separate PostgreSQL database or schema and its own
  migrations. Suggested schema names are `source_schema`, `article_schema`,
  `intelligence_schema`, `ai_content_schema`, `content_schema`, and
  `identity_schema`; final names are TBD.
- Never query another service's tables. Exchange data through documented APIs
  or Kafka events. Local read models derived from events are allowed.
- PostgreSQL is authoritative for articles, stories, claims, revisions, and
  publications. Redis is never authoritative for these entities.
- Keep business logic out of HTTP handlers, middleware, Airflow DAGs, and
  infrastructure adapters.
- Do not replace an asynchronous boundary with direct synchronous coupling
  without documenting a specific reason and its trade-offs.
- The gateway handles cross-cutting HTTP concerns but does not absorb domain
  ownership.

## Contracts and event processing

Document synchronous APIs with OpenAPI. Version Kafka schemas and do not
silently alter payloads consumed by another service.

Every important event should include:

- unique event ID, event type, and schema version;
- UTC timestamp and producer;
- correlation ID and, where applicable, causation ID;
- aggregate ID and typed payload;
- trace metadata where available.

Topic names are **TBD**. Candidate groups are `crawl.*`, `article.*`,
`intelligence.*`, `story.*`, `content.*`, and `publication.*`. Select and
document one consistent naming convention before producers and consumers
depend on it.

Assume Kafka delivers at least once:

- Consumers must be idempotent using event IDs, processed-event records, unique
  constraints, conditional writes, and stable business idempotency keys.
- Atomically commit the business state change and processed-event record where
  practical.
- Do not commit an offset before durable business state is stored.
- When durable state changes must emit an event, prefer a transactional outbox:
  write state and outbox row in one transaction, then publish asynchronously.
- Outbox publication may repeat; consumers must still be idempotent.
- Choose partition keys only for required aggregate ordering. Never claim
  global Kafka ordering or system-wide exactly-once semantics.
- Classify failures as retryable, non-retryable, or requiring operator/editor
  action. Bound retries and use exponential backoff with jitter.
- Poison messages must not block a partition forever. Preserve exhausted
  failures in a DLQ or equivalent inspectable/replayable path, including the
  original event, attempts, and error context.

## Correctness-critical workflows

### Collection

- Use bounded worker pools and channels; never create unbounded goroutines.
- Propagate contexts and cancellation, reuse configured HTTP clients, enforce
  global and per-domain concurrency, support backpressure, and shut down
  gracefully without acknowledging incomplete work.
- Bound attempts, redirects, response sizes, and timeouts; respect
  `Retry-After` where applicable.
- SSRF protection is mandatory: allow only HTTP/HTTPS, use configured domains,
  resolve and validate IPs, reject private/loopback targets except explicit
  mock mode, and revalidate every redirect.
- Use an explicit user agent, do not execute scripts, and do not fetch
  unnecessary assets. Public users must not supply arbitrary crawl targets.

### Normalization and duplicates

- Normalize scheme/host case, fragments, safe trailing slashes, tracking
  parameters, known canonical URLs, titles, and article text deterministically.
- Use deterministic normalized-content hashes for exact duplicates.
- Start near-duplicate detection with explainable title similarity, SimHash,
  entity overlap, time windows, and category compatibility.
- Preserve every source article and explicit duplicate relationships.

### Intelligence and stories

- Prefer explainable rules based on category, primary player/clubs, coach,
  competition, time window, normalized title tokens, similarity, and a stable
  story fingerprint.
- Retrieve candidates, score them, attach above a documented threshold, and
  create otherwise. Provide editor merge and reassignment operations.
- Protect concurrent story processing with transactions, unique fingerprints
  and links, unique claims, optimistic versions or narrowly scoped locks, and
  retries on conflicts.
- Test against duplicate stories, lost timeline updates, duplicate links or
  claims, and stale writes.
- Embedding clustering and vector stores are not MVP requirements.

### AI generation

- Build structured claims with source IDs and confirmation levels before
  generation. Do not give arbitrary scraped pages to an unconstrained prompt.
- Accept only structured output; validate its claims and source references.
  Reject or flag malformed and unsupported output for review.
- Record provider, model, prompt version, input story version, generation time,
  validation result, source IDs, attempts, and errors.
- Bound provider concurrency, rate, timeout, retries, and optional token/cost
  budgets.
- Preserve a deterministic template/fixture-based mock implementation.

### Editorial and publication

Use explicit state transitions, initially:

```text
DRAFT → NEEDS_REVIEW → APPROVED → SCHEDULED? → PUBLISHED
                    ↘ REJECTED
```

Exact permitted transitions are **TBD** and must be documented and tested.
Use conditional updates and audit history. Publishing must require an approved,
current revision and be idempotent under retries and simultaneous workers.
Protect it with revision identity, a stable idempotency key, transactions, and
a unique successful-publication constraint.

## API, security, and observability

API-facing services should consistently support request/correlation IDs,
structured access logs, recovery, authentication, RBAC, validation, body
limits, rate limits, timeouts, CORS, appropriate security headers, consistent
error envelopes, and metrics. Middleware must not hide business logic.

Treat API, source-domain, and AI-provider rate limits as separate concerns.
Source limits include requests per second, concurrency, timeout, retry/backoff,
and crawl-policy configuration. Redis-backed limits must remain correct across
multiple workers when enabled.

Every long-running service should eventually provide liveness and readiness
endpoints, structured logs with service and correlation identity, basic
metrics, and graceful shutdown of HTTP, database, Redis, and Kafka resources.
Never log secrets or full scraped article bodies by default.

Prioritize metrics for crawl outcomes/latency/rate limits/retries, consumer lag,
article throughput and duplicate rate, story create/update outcomes, AI queue
and validation behavior, draft/publication outcomes, and DLQ size.

## Engineering rules

### General

- Inspect existing code, contracts, migrations, and tests before editing.
- Prefer correctness and clarity over clever or speculative abstractions.
- Make small vertical slices. Include migration, domain logic, API/event
  handling, tests, and documentation together when relevant.
- Validate external inputs and wrap errors with useful context. Never ignore a
  returned error.
- Use stable IDs and UTC for stored timestamps.
- Make state transitions, transaction boundaries, idempotency, retry behavior,
  and data invariants explicit.
- Keep deterministic fixtures stable.
- Never commit credentials. Provide `.env.example` with safe placeholders.
- Do not add infrastructure merely to make the design look more complex.
- Do not remove mock/offline mode or make real Internet/LLM access mandatory.
- Keep the three-week scope and complete vertical slice ahead of optional
  polish.

### Go

- Run `gofmt` on changed Go files.
- Use contexts for I/O and graceful cancellation.
- Prefer explicit constructors and small consumer-owned interfaces; do not
  create an interface for every struct.
- Avoid mutable globals. Reuse HTTP clients and configure DB pools.
- Bound goroutines and channels and avoid leaks.
- Prefer table-driven tests where appropriate.
- Once Go modules and commands exist, verify `go vet` and use the race detector
  for concurrency-sensitive packages. Exact repository commands are **TBD**.

### Python

- Use type hints and separate domain logic from framework/worker adapters.
- Keep worker operations idempotent and concurrency explicit.
- Avoid hidden global model state.
- Validate all structured AI output.
- Retain deterministic mock implementations.
- Add focused tests for alias resolution, classification, clustering, and
  generation validation.
- Formatter, linter, type-checker, package manager, and exact commands are
  **TBD** until repository configuration selects them.

### TypeScript and Next.js

- Enable strict TypeScript.
- Keep server/client responsibilities explicit and share or generate API types
  when practical.
- Model loading, failed, empty, and stale states.
- Show actionable backend errors in admin views.
- Do not duplicate backend business rules in the frontend.
- Add suitable news-page SEO metadata without prioritizing visual polish over
  pipeline correctness.
- Package manager, lint/test tools, and exact commands are **TBD**.

## Testing and validation

Required test layers:

- Unit: URL/content normalization, hashes, similarity, retry classification and
  delays, aliases, story scoring, confirmation changes, publication transitions,
  and AI output validation.
- Service integration: PostgreSQL repositories, Redis limits, Kafka
  producer/consumer behavior, outbox publishing, idempotency, uniqueness, and
  story/publication concurrency.
- Contract: OpenAPI behavior, event schemas, and producer/consumer compatibility.
- End to end: mock source through collector, Kafka, article, intelligence, mock
  AI, review, publication, and public page.
- Failure: 429, 500, timeout, duplicate event, restart, invalid AI output,
  concurrent story creation, duplicate publication, and defined Redis outage
  behavior.
- Load/concurrency: bounded collection, per-domain limiting, throughput,
  backlog, scaling, contention, AI backpressure, and API limiting.

For load results, record machine and Docker resources, worker counts, Kafka
partitions, payload sizes, duration, p50/p95/p99, errors, and final invariants.
Never invent benchmark values.

Run the narrowest relevant test first, then broader validation proportional to
the change. Never claim a command passed unless it was actually run.

### Commands

There are currently no verified project commands.

| Task | Current command |
| --- | --- |
| Local development | TBD |
| Build | TBD |
| Unit tests | TBD |
| Integration tests | TBD |
| End-to-end tests | TBD |
| Go format/vet/race | TBD until Go modules exist |
| Python format/lint/type-check | TBD |
| TypeScript lint/type-check/test | TBD |
| Database migration | TBD |
| Docker Compose startup | Planned target: `docker compose up --build`; unverified because no Compose file exists |
| Deterministic demo | TBD |

When a command becomes supported, add its owning configuration/script, execute
it, document prerequisites, and replace the matching TBD entry with the exact
verified command.

## Delivery priorities

1. **Week 1 — infrastructure and ingestion:** planned Compose baseline,
   PostgreSQL, Redis, Kafka, minimal Airflow, mock source, source configuration,
   concurrent collector, retries/rate limits, raw events, article normalization,
   exact duplicate detection, and initial integration path.
2. **Week 2 — intelligence and editorial backend:** entities/aliases,
   classification, story matching/fingerprints/timelines/confirmation,
   concurrency protection, deterministic AI generation, grounded references,
   revisions, review, approve/reject, and idempotent publication.
3. **Week 3 — web, reliability, and demonstration:** public/admin pages,
   Airflow workflows, retry/DLQ visibility, restart and end-to-end tests, load
   measurements, fixtures, architecture/testing/demo documentation.

Do not advance optional breadth at the expense of the preceding week's
end-to-end definition of done.

## Explicit MVP non-goals

Do not require arbitrary-site crawling, large commercial scraping, vector
databases, embedding-based clustering, Elasticsearch/OpenSearch, Kubernetes,
service mesh, cloud deployment, social publishing, recommendations, comments,
personalized feeds, live scores, reuse of external news images, full
multilingual support, autonomous low-confidence publication, or system-wide
exactly-once guarantees. Record them as future work only if useful.

## Documentation expectations

As implementation lands, maintain a root README plus focused documentation for
architecture, service/data ownership, APIs and events, Airflow, collection and
rate limits, duplicates, story clustering, AI grounding, failure/DLQ handling,
testing, deterministic demo, limitations, and roadmap. Use Mermaid where it
materially clarifies a flow or boundary.

## Change handoff

Every future task report must state:

- files changed;
- commands actually executed and their results;
- tests not run and why;
- unresolved issues, assumptions, or decisions;
- any effect on contracts, migrations, idempotency, retries, or state
  invariants.

Do not claim the planned architecture or MVP is complete until the full
localhost workflow, recovery behavior, tests, and documentation demonstrate
the project completion criteria.

## Decisions still TBD

Confirm through an architecture decision or implementation slice before
depending on:

- Go module path and repository/package naming;
- exact service directory and schema/database names;
- Kafka event schema format, topic names, partition keys, retry topics, and DLQ
  convention;
- API authentication and role model;
- Python package manager/framework and quality tools;
- Next.js package manager and test stack;
- migration tools for Go and Python services;
- Kafka distribution and local Airflow executor;
- whether scheduling publication is included in the MVP;
- observability components included in the default local stack;
- exact similarity thresholds and confirmation transition rules;
- verified build, lint, test, migration, startup, and demo commands.

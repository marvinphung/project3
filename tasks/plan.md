# Implementation Plan: FootballPulse

Canonical detailed plan:
[`docs/plans/2026-08-06-footballpulse-implementation.md`](../docs/plans/2026-08-06-footballpulse-implementation.md).

## Execution contract

1. Execute exactly one Work Package at a time.
2. Before coding, present a WP Kickoff and wait for explicit permission.
3. Run focused tests and proportional broader verification.
4. Present the Collaboration Gate report.
5. Wait for explicit user approval.
6. Only then mark the WP complete and propose the next WP.
7. Repeat with an additional Phase Gate after each phase.

## Phase order

1. Phase 0 — Workspace, packages, event contracts and fixtures.
2. Phase 1 — Local Kafka/MongoDB/PostgreSQL+pgvector/Redis data plane.
3. Phase 2 — RSS to immutable Mongo evidence.
4. Phase 3 — Entity, embedding and Kaggle/local/mock AI enrichment.
5. Phase 4 — Story, confirmation, change detection and timeline.
6. Phase 5 — Editorial, publication, auth and APIs.
7. Phase 6 — React/Vite public/admin integration.
8. Phase 7 — Airflow and full Compose profiles.
9. Phase 8 — Reliability, E2E, Kaggle acceptance, load and final handoff.

## Current next action

Phase Gate 4 is approved. Phase 5.1 grounded generation, 5.2 editorial revisions,
5.3 idempotent publication, and the first 5.5 public/admin API façade are implemented.
The credential model, JWT/Argon2 token endpoint, PostgreSQL user repository,
local bootstrap, and JWT role enforcement are implemented. Static admin/editor
tokens remain supported for backward-compatible local development. Phase 6.1
now has a typed public API client and loading/error state hook. Phase 6.2 has a
reusable Vietnamese Story timeline component and hook, plus a public
entity-to-Story mapping endpoint so player timelines resolve canonical slugs.
The article detail route now consumes the public article endpoint and its
persisted Story timeline. Homepage and latest-news cards now use the same
public API adapter; entity chips and richer source metadata remain future API
fields. Entity tags are now included in public article responses and mapped to
frontend chips. Admin login now obtains and stores a real JWT. Draft review actions now
have bearer-authenticated API clients; published-article listing now reads the
public API, and source listing now consumes the crawler admin API when
`VITE_CRAWLER_API_BASE_URL` is configured. Source enable/disable now uses the
crawler versioned toggle endpoint. Admin crawl triggering now opens an
idempotent batch through the crawler service. The first collection DAG now
orchestrates those batches every six hours and queries crawler `sources/due`
for source selection. Mock HTTP coverage now verifies due-source auth,
idempotency, and batch payloads.

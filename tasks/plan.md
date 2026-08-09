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

Phase Gate 2 was approved after the complete RSS-to-Mongo evidence slice and its
failure/duplicate matrix passed. The next action is the WP 3.1 Kickoff for the
canonical entity catalog; do not implement it before the user approves that kickoff.

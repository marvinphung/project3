# Implementation Plan: FootballPulse

Canonical detailed plan:
[`docs/plans/2026-08-06-footballpulse-implementation.md`](../docs/plans/2026-08-06-footballpulse-implementation.md).

Completion execution plan (current):
[`docs/plans/2026-08-17-project-completion.md`](../docs/plans/2026-08-17-project-completion.md).

Frontend real-data/API gap plan:
[`docs/plans/2026-08-17-frontend-real-data-api-plan.md`](../docs/plans/2026-08-17-frontend-real-data-api-plan.md).

## Execution contract

For the historical canonical plan, the original Collaboration Gate rules remain
recorded in that document. For the current completion plan, the user explicitly
authorized autonomous implementation and verification on 2026-08-17:

1. Execute one completion task at a time in dependency order.
2. Run focused tests, Docker smoke and proportional broader verification.
3. Report concise checkpoints, but continue without waiting for approval.
4. Stop only for missing credentials/artifacts, an irreversible action, or a
   decision that materially changes the approved MVP scope.
5. Do not mark the MVP complete until the final Docker/E2E verification passes.

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

Hoàn tất Story/timeline runtime, sau đó thực thi public real-data Phase 1 và admin
operational API Phase 2 trong frontend/API gap plan. Không thêm fixture fallback.

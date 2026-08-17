# FootballPulse Work Package Checklist

Current completion checklist:
[`docs/plans/2026-08-17-project-completion.md`](../docs/plans/2026-08-17-project-completion.md).

## MVP completion execution

- [x] A1 Baseline verification và checklist audit
- [x] A2 Runtime configuration
- [x] B1 AI provider runtime wiring
- [ ] B2 Kaggle execution lifecycle
- [ ] B3 Mongo article-to-enrichment worker
- [ ] C1 Entity/embedding intelligence worker
- [ ] C2 Enrichment-to-Story orchestration
- [ ] C3 Material-change và bilingual timeline
- [ ] D1 Operational read model/Admin API
- [ ] D2 Public API completeness
- [ ] D3 Admin operations UI
- [ ] D4 Editorial/Story correction UI
- [ ] E1 Airflow runtime orchestration
- [ ] E2 Full Docker topology/readiness
- [ ] E3 Structured operational logs
- [ ] F1 Offline deterministic E2E
- [ ] F2 Real-source smoke E2E
- [ ] F3 Restart/concurrency/recovery
- [ ] F4 Browser/load/final handoff

---

> A checkbox may be marked complete only after tests pass, the Collaboration
> Gate report is delivered, and the user explicitly approves closure.
> Every WP also requires a user-approved WP Kickoff before implementation starts.

## Phase 0 — Foundation

- [x] WP 0.1 Root uv workspace and quality gates
- [x] WP 0.2 Service package skeleton and runtime conventions
- [x] WP 0.3 Event envelope and first contracts
- [x] WP 0.4 Deterministic fixture catalog
- [x] Phase Gate 0 approved

## Phase 1 — Local data plane

- [x] WP 1.1 Minimal Compose dependencies
- [x] WP 1.2 Source/identity migrations
- [x] WP 1.3 Mongo indexes, processed events and outbox
- [x] Phase Gate 1 approved

## Phase 2 — RSS to evidence

- [x] WP 2.1 Source management domain/internal API
- [x] WP 2.2 Safe bounded RSS discovery
- [x] WP 2.3 HTML extraction and normalization
- [x] WP 2.4 Immutable article version consumer
- [x] WP 2.5 URL/exact/near duplicate pipeline
- [x] Phase Gate 2 approved

## Phase 3 — Intelligence and AI

- [x] WP 3.1 Canonical entity catalog
- [x] WP 3.2 GLiNER adapter and resolution
- [x] WP 3.3 English embedding adapter
- [x] WP 3.4 AI contracts and grounding validator
- [x] WP 3.5 Kaggle batch adapter
- [x] WP 3.6 Local Qwen/mock fallback
- [ ] Phase Gate 3 approved

## Phase 4 — Story and timeline

- [x] WP 4.1 Story/claim PostgreSQL model
- [x] WP 4.2 Hybrid candidate retrieval
- [x] WP 4.3 Confirmation/source independence
- [x] WP 4.4 Material Change Detector
- [x] WP 4.5 Bilingual timeline aggregation
- [x] Phase Gate 4 approved

## Phase 5 — Editorial and API

- [x] WP 5.1 Grounded long-form generation
- [x] WP 5.2 Revision/review state machine
- [x] WP 5.3 Idempotent publication
- [x] WP 5.4 Authentication/RBAC/gateway middleware
- [x] WP 5.5 Public/admin OpenAPI façade (read/admin routes implemented)
- [ ] Phase Gate 5 approved

## Phase 6 — Frontend

- [x] WP 6.1 Typed API client and application states
- [x] WP 6.2 Public entity timelines
- [x] WP 6.3 Public articles and Story views
- [ ] WP 6.4 Admin batch/source/failure operations (JWT login done; admin API screens remain)
- [ ] WP 6.5 Editorial and Story correction UI
- [ ] Phase Gate 6 approved

## Phase 7 — Orchestration

- [x] WP 7.1 Collection DAG
- [ ] WP 7.2 AI enrichment/reprocess DAGs (DAG + HTTP lifecycle contract done; provider worker remains)
- [x] WP 7.3 Service images and Compose profiles (AI content runtime added)
- [ ] WP 7.4 Operational read models
- [ ] Phase Gate 7 approved

## Phase 8 — Final verification

- [x] WP 8.1 Retry/DLQ/outbox recovery (contracts and recovery matrix documented)
- [x] WP 8.2 Restart and concurrency invariants (documented; integration execution remains)
- [x] WP 8.3 Offline end-to-end demo
- [x] WP 8.4 Kaggle integration acceptance (contract script; live check opt-in)
- [x] WP 8.5 Load measurement and final documentation (offline smoke-load + handoff checklist)
- [ ] Final Phase Gate approved by user

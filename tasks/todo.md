# FootballPulse Work Package Checklist

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
- [ ] WP 1.3 Mongo indexes, processed events and outbox
- [ ] Phase Gate 1 approved

## Phase 2 — RSS to evidence

- [ ] WP 2.1 Source management domain/internal API
- [ ] WP 2.2 Safe bounded RSS discovery
- [ ] WP 2.3 HTML extraction and normalization
- [ ] WP 2.4 Immutable article version consumer
- [ ] WP 2.5 URL/exact/near duplicate pipeline
- [ ] Phase Gate 2 approved

## Phase 3 — Intelligence and AI

- [ ] WP 3.1 Canonical entity catalog
- [ ] WP 3.2 GLiNER adapter and resolution
- [ ] WP 3.3 English embedding adapter
- [ ] WP 3.4 AI contracts and grounding validator
- [ ] WP 3.5 Kaggle batch adapter
- [ ] WP 3.6 Local Qwen/mock fallback
- [ ] Phase Gate 3 approved

## Phase 4 — Story and timeline

- [ ] WP 4.1 Story/claim PostgreSQL model
- [ ] WP 4.2 Hybrid candidate retrieval
- [ ] WP 4.3 Confirmation/source independence
- [ ] WP 4.4 Material Change Detector
- [ ] WP 4.5 Bilingual timeline aggregation
- [ ] Phase Gate 4 approved

## Phase 5 — Editorial and API

- [ ] WP 5.1 Grounded long-form generation
- [ ] WP 5.2 Revision/review state machine
- [ ] WP 5.3 Idempotent publication
- [ ] WP 5.4 Authentication/RBAC/gateway middleware
- [ ] WP 5.5 Public/admin OpenAPI façade
- [ ] Phase Gate 5 approved

## Phase 6 — Frontend

- [ ] WP 6.1 Typed API client and application states
- [ ] WP 6.2 Public entity timelines
- [ ] WP 6.3 Public articles and Story views
- [ ] WP 6.4 Admin batch/source/failure operations
- [ ] WP 6.5 Editorial and Story correction UI
- [ ] Phase Gate 6 approved

## Phase 7 — Orchestration

- [ ] WP 7.1 Collection DAG
- [ ] WP 7.2 AI enrichment/reprocess DAGs
- [ ] WP 7.3 Service images and Compose profiles
- [ ] WP 7.4 Operational read models
- [ ] Phase Gate 7 approved

## Phase 8 — Final verification

- [ ] WP 8.1 Retry/DLQ/outbox recovery
- [ ] WP 8.2 Restart and concurrency invariants
- [ ] WP 8.3 Offline end-to-end demo
- [ ] WP 8.4 Kaggle integration acceptance
- [ ] WP 8.5 Load measurement and final documentation
- [ ] Final Phase Gate approved by user

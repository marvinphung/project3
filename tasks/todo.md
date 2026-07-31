# FootballPulse — Phase checklist

## Phase 0 — Foundation không Docker

- [x] Re-verify root `uv` workspace và quality commands.
- [x] Re-verify `article.discovered.v1` Pydantic/JSON Schema compatibility.
- [x] Hoàn thiện deterministic fixture catalog và snapshot tests.
- [x] Chốt config models, port conventions và secret-redaction tests.
- [x] Checkpoint: không chạy Docker; ghi rõ mọi integration command unverified.

## Phase 1 — Ingestion domain

- [ ] Crawler URL/SSRF policy.
- [ ] One-source fetch/parse use case qua fake HTTP transport.
- [ ] Bounded concurrency, rate limit, retry và cancellation.
- [ ] Event producer port và delivery semantics.
- [ ] Article normalization/hash.
- [ ] Idempotent evidence/processed-event/outbox use case.
- [ ] Exact/near duplicate semantics và `article.unique.v1`.

## Phase 2 — Intelligence/story domain

- [ ] Entity/alias/keyword/category pipeline.
- [ ] Claim extraction và candidate scoring.
- [ ] Story fingerprint/create/attach/update/version.
- [ ] Concurrency conflict semantics.
- [ ] Merge/reassign/correction commands.

## Phase 3 — AI/editorial/API contracts

- [ ] Direct-Kafka job model và deterministic Mock AI Provider.
- [ ] Grounding/structured-output validation.
- [ ] Draft/revision/review/approve/reject/publish state machine.
- [ ] Gateway OpenAPI, middleware, auth/RBAC và rate-limit contracts.
- [ ] Frontend typed API boundary và demo-critical screen mapping.

## Phase 4 — Docker/integration/demo

- [ ] Compose dependency baseline và clean startup/shutdown.
- [ ] Mongo replica transaction/index và PostgreSQL migration tests.
- [ ] Kafka producer/consumer/manual-commit/retry/DLQ tests.
- [ ] Real outbox/reconciliation and worker-restart tests.
- [ ] Service images/profiles và Airflow 3 DAG/profile.
- [ ] Full offline E2E, failure and load/concurrency measurements.
- [ ] Final reproducibility, README, runbooks và demo.

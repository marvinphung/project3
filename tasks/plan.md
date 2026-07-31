# FootballPulse — Execution order

Tài liệu điều hướng ngắn này không thay thế
[`docs/implementation-plan.md`](../docs/implementation-plan.md). Thứ tự hiện
được chấp thuận là:

1. **Phase 0 — Foundation không Docker (Days 1–2):** workspace, configuration,
   contracts, fixtures và quality gates.
2. **Phase 1 — Ingestion domain (Days 3–6):** Crawler và Article use cases qua
   ports/fakes, bao gồm safety, retry, duplicate, idempotency và outbox
   semantics.
3. **Phase 2 — Intelligence/story domain (Days 7–11):** aliases, entities,
   classification, claims, clustering, timeline và concurrency semantics.
4. **Phase 3 — AI/editorial/API contracts (Days 12–16):** grounded mock AI,
   editorial state machine, Gateway/OpenAPI và frontend contract boundary.
5. **Phase 4 — Docker/integration/demo (Days 17–21):** Compose, real adapters,
   migrations, Kafka/Mongo/Postgres/Redis, Airflow, E2E, failure/load và final
   offline demo.

## Dependency rule

Mỗi use case phụ thuộc vào protocol/port. Fake/in-memory adapters chỉ chứng minh
domain behavior; không thay thế integration proof. Mọi task Docker—kể cả
Compose config, image build/pull, container startup, database/topic init,
Airflow profile và Docker-based tests—chỉ bắt đầu ở Phase 4.

## Checkpoints

- Sau Phase 0: quality/contract tests pass; Docker vẫn deferred/unverified.
- Sau Phase 1: ingestion domain invariants pass qua deterministic fakes.
- Sau Phase 2: story grouping/version/concurrency invariants pass.
- Sau Phase 3: draft/editorial/API contracts pass; chưa gọi là full-stack.
- Sau Phase 4: real integration, restart, failure và offline E2E pass.

Chi tiết từng ngày, DoD, risk và fallback nằm trong implementation plan.

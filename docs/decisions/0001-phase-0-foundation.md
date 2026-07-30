# ADR-0001: Khóa baseline kỹ thuật Phase 0

## Status

Accepted

## Date

2026-07-31

## Context

FootballPulse phải hoàn thành một vertical slice microservices chạy localhost
trong ba tuần. Repository đã có React/Vite frontend nhưng chưa có backend hoặc
hạ tầng. Các tài liệu trước đó còn mâu thuẫn về frontend, service boundaries,
data ownership, retry topology, authentication và observability.

## Decision

- Dùng Python 3.12 cho toàn bộ backend/worker, quản lý bằng một `uv` workspace
  và một `uv.lock`; mỗi service giữ manifest và business logic riêng.
- Dùng FastAPI/Pydantic, Ruff, mypy, pytest và pytest-asyncio.
- Giữ sáu backend service: API Gateway, Crawler, Article, Intelligence,
  AI Content và Content. Source configuration/crawl batch thuộc Crawler.
- Giữ nguyên React 19/Vite 8 frontend và `pnpm`; không chuyển Next.js.
- Dùng Apache Kafka KRaft single-node trên localhost. Event contract là JSON
  Schema Draft 2020-12 kết hợp Pydantic; topic có hậu tố version.
- Mỗi input topic retryable chỉ có một retry topic với `next_attempt_at` và một
  DLQ trong MVP.
- `article.discovered.v1` mang bounded parsed snapshot, không mang full raw HTML
  và không buộc Article Service gọi ngược Crawler để lấy dữ liệu.
- MongoDB single-node replica set sở hữu Source Article, processed events và
  Article outbox. PostgreSQL sở hữu source/crawl configuration, identity,
  intelligence, AI generation và content trong schema riêng.
- Airflow 3 dùng Compose profile nhẹ, không CeleryExecutor; executor chính xác
  được xác minh khi triển khai.
- Auth MVP dùng JWT access token, Argon2 và hai role `ADMIN`, `EDITOR`.
  `EDITOR` review/edit/approve/reject; chỉ `ADMIN` được publish và quản trị
  source/crawl/retry/merge. Internal API dùng configured token trong mạng
  Compose localhost.
- Không dùng ARQ, scheduled publication, Prometheus hoặc Grafana trong MVP.

## Alternatives considered

- Tách `source-service`: loại vì thêm network boundary nhưng chưa tạo đủ giá trị
  trong thời hạn ba tuần.
- Viết lại frontend bằng Next.js: loại vì UI React/Vite đã tồn tại.
- Mỗi service có lockfile riêng: loại để giữ môi trường local tái lập đơn giản.
- Redpanda hoặc Kafka/ZooKeeper: loại để thể hiện Apache Kafka trực tiếp và giảm
  thành phần.
- Protobuf/Schema Registry: để P1 vì JSON Schema dễ kiểm tra và đủ cho MVP.
- Ba retry tiers: loại khỏi MVP vì cần delayed dispatcher phức tạp hơn.
- MongoDB standalone: loại vì không thể kiểm thử atomic evidence/outbox path.
- CeleryExecutor/ARQ: loại vì tăng thêm queue ownership và tài nguyên localhost.
- Một role xuất bản riêng: loại để giữ RBAC MVP nhỏ; `ADMIN` sở hữu publish.

## Consequences

- Phase 0 phải sửa mọi contract và tài liệu theo một naming/ownership model.
- Single-node Kafka không chịu được mất broker; `acks=all` không biến nó thành
  production-grade cluster.
- Mongo replica-set initialization và Airflow executor là hai smoke test hạ
  tầng rủi ro cao cần làm sớm.
- Shared package chỉ chứa contracts/cross-cutting primitives; không trở thành
  nơi gom business logic giữa các service.
- Mọi command vẫn là planned/TBD cho đến khi file sở hữu nó được tạo và command
  được chạy thành công.

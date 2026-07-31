# ADR-0002: Chuyển toàn bộ công việc Docker xuống phase cuối

## Status

Accepted

## Date

2026-07-31

## Context

ADR-0001 ưu tiên smoke test Kafka, MongoDB replica set, PostgreSQL và Redis từ
đầu Phase 0 để giảm sớm rủi ro tích hợp. Sau khi foundation Python và contract
đầu tiên được tạo, dự án quyết định tạm thời tập trung vào contracts, domain
logic và service use cases trước; các task liên quan đến Docker phải để sau
cùng.

Repository đã có `docker-compose.yml`, init scripts và mock-source static
fixtures ở trạng thái chưa được xác minh end-to-end. Quyết định này không xóa
những file đó, nhưng cấm dựa vào chúng như một baseline đã hoạt động trước phase
hạ tầng cuối.

## Decision

- Phase 0 chỉ hoàn thiện workspace, conventions, contracts, configuration,
  deterministic fixtures và quality gates; không chạy container.
- Các phase domain triển khai theo dependency inversion: domain/use case phụ
  thuộc protocol/port, không phụ thuộc trực tiếp vào Docker hay một database
  đang chạy.
- Dùng fake/in-memory adapters và mocked HTTP/provider/Kafka boundaries cho
  unit, contract và service-level tests trước phase tích hợp.
- Chỉ tạo service package khi vertical slice đi tới service đó; không scaffold
  đồng loạt.
- Migrations, repository adapters và Kafka adapters có thể được viết trước,
  nhưng mọi tuyên bố về transaction, index, broker acknowledgement, offset,
  outbox recovery và database compatibility chỉ được xác nhận bằng integration
  test ở phase Docker cuối.
- Tất cả task tạo/chỉnh topology Compose, build image, pull image, start/stop
  container, init topic/database/replica set, Airflow Compose và Docker-based
  E2E/load test thuộc phase cuối.
- Không thay đổi kiến trúc đích: Kafka vẫn là backbone, MongoDB vẫn sở hữu
  Source Article, PostgreSQL vẫn sở hữu normalized product data và Redis không
  phải source of truth.

## Alternatives considered

### Xác minh Docker ngay sau mỗi vertical slice

- Ưu điểm: phát hiện sớm lỗi driver, transaction, broker và migration.
- Nhược điểm: ngắt nhịp phát triển domain và trái với thứ tự hiện được yêu cầu.
- Không chọn ở thời điểm này.

### Bỏ Docker khỏi MVP

- Ưu điểm: giảm thời gian hạ tầng.
- Nhược điểm: vi phạm yêu cầu full stack localhost/offline và không chứng minh
  được Kafka/Mongo/PostgreSQL/Redis/Airflow thật.
- Loại bỏ.

### Dùng SQLite/in-process broker làm implementation chính

- Ưu điểm: chạy nhanh trong phase đầu.
- Nhược điểm: che giấu semantic khác biệt của PostgreSQL, MongoDB và Kafka.
- Chỉ cho phép fake test adapters; không dùng làm production adapter hoặc bằng
  chứng integration.

## Consequences

- Domain logic và contracts có thể tiến triển mà không phụ thuộc Docker daemon.
- Rủi ro tích hợp Kafka/Mongo replica/PostgreSQL/Airflow bị dồn về cuối và có
  thể tạo rework lớn hơn.
- Phải dành đủ buffer ở phase cuối, không để Docker chỉ còn một ngày.
- Trước khi vào phase Docker, mỗi port phải có contract test và fixture rõ ràng
  để giảm phạm vi debug.
- Definition of Done toàn dự án không thay đổi: chưa có Docker smoke,
  integration, restart và offline E2E thì MVP chưa hoàn thành.

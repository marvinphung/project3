# Conventions cho application ports

## Mục đích

Các phase trước Docker triển khai domain/use case dựa trên ports và
deterministic fakes. Tài liệu này khóa hình dạng và semantics tối thiểu để fake
không trở thành một implementation thay thế Kafka, MongoDB hoặc PostgreSQL.

## Ownership và vị trí

- Mỗi port thuộc service sử dụng nó và đặt trong package application của
  service, ví dụ `crawler_service/application/ports.py`.
- Adapter nằm ở package infrastructure của cùng service.
- Không đưa repository, unit-of-work, Kafka client hoặc HTTP client ports vào
  `footballpulse-runtime-config` hay `footballpulse-event-contracts`.
- Shared packages Phase 0 chỉ gồm versioned event contracts và runtime
  configuration; không chứa business rules.
- Domain và use case không import FastAPI, PyMongo, SQLAlchemy, Redis hoặc
  Kafka client types.

## Quy tắc thiết kế

1. Dùng `typing.Protocol` cho một capability mà use case thực sự cần; không mô
   phỏng toàn bộ API của vendor.
2. Input/output dùng domain types hoặc contract types do service sở hữu, không
   trả về cursor/row/message của adapter.
3. Network-bound methods là async. Blocking client phải được adapter cô lập
   khỏi event loop.
4. Deadline/cancellation đi từ entry point tới adapter. Không tự tạo timeout vô
   hạn hoặc nuốt `CancelledError`.
5. Exception được phân loại tối thiểu thành retryable, non-retryable và
   operator/editor action; không để use case phụ thuộc exception của vendor.
6. Fake là stateful và kiểm tra outcome/invariant. Mock interaction chỉ dùng
   khi cần chứng minh một boundary side effect.
7. Mỗi real adapter phải chạy cùng contract-test suite với fake tương ứng trong
   Phase 4.

## Semantics bắt buộc

### EventPublisher

- Nhận validated/versioned event và stable partition key.
- `publish` chỉ thành công sau delivery confirmation theo cấu hình producer.
- Timeout hoặc delivery failure không được trả success.
- `DeliveryReceipt` chứa topic, partition và offset khi adapter hỗ trợ.
- Việc publish có thể lặp; consumer vẫn phải idempotent.

### EventConsumer

- Giao validated event cùng metadata cần cho commit/retry.
- Không auto-commit trước durable business processing.
- `ack` chỉ được gọi sau state và processed-event/outbox đã commit.
- Graceful shutdown không acknowledge item đang xử lý dở.

### UnitOfWork và repositories

- Boundary nguyên tử của Article:
  `Source Article + processed event + outbox`.
- Boundary nguyên tử của Intelligence/Content:
  `business state + processed event + outbox`.
- Unique conflict và optimistic-version conflict là kết quả có kiểu/phân loại,
  không bị đổi thành generic success.
- Fake unit-of-work phải hỗ trợ commit/rollback và giữ stable uniqueness rules.

### Clock, ID và rate limiter

- Use case nhận `Clock` và ID factory khi kết quả phụ thuộc thời gian/ID để test
  deterministic.
- Mọi stored/event timestamp dùng aware UTC.
- Rate limiter trả decision cùng retry delay; Redis failure policy do owning
  service quyết định rõ, không silently disable.

## Contract-test checklist

Mỗi cặp fake/real adapter phải dùng chung các case phù hợp:

- happy path trả cùng domain result;
- timeout/cancellation không trở thành success;
- duplicate event không lặp business state;
- commit failure không tạo acknowledgement;
- outbox publish lặp không làm mất event;
- unique/version conflict có cùng classification;
- resource được đóng khi shutdown.

Các test fake chạy trong Phase 1–3. Test real adapter, offset, transaction và
restart chỉ được ghi là pass sau Phase 4 Docker integration.

# Restart và concurrency invariants

Mục tiêu là restart an toàn trên local stack, không phụ thuộc process memory.

## Invariants

- Mỗi consumer dùng processed-event marker `(consumer_name, event_id)`.
- Mỗi publication dùng idempotency key và optimistic revision number.
- Story matching chỉ commit audit, aggregate và processed marker trong cùng
  transaction boundary.
- Crawler source update dùng `expected_version`; stale update trả conflict.
- AI batch chỉ cho phép transition hợp lệ và không ghi đè terminal state.
- Outbox publisher có thể chạy lại sau crash; duplicate delivery phải được
  downstream deduplicate bằng event ID.

## Restart checklist

1. Dừng process giữa state write và publish.
2. Khởi động lại cùng consumer name.
3. Chạy lại event/batch với cùng idempotency key.
4. Xác nhận chỉ có một state transition hợp lệ và một outbox record.
5. Kiểm tra retry count/failure state không bị reset.

Concurrency test phải bao phủ hai writer cùng revision, hai consumer cùng
event và hai request publish cùng idempotency key.

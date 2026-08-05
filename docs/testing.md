# Chiến lược kiểm thử

## 1. Mục tiêu

Kiểm thử phải chứng minh invariant nghiệp vụ và recovery, không chỉ chứng minh
endpoint trả 200. Test/demo mặc định deterministic, offline và không cần
external LLM credential.

## 2. Test pyramid

| Lớp | Trọng tâm |
| --- | --- |
| Unit | normalization, hashes, similarity, aliases, classification, scoring, confirmation, state machine |
| Contract | event envelope/schema, producer-consumer compatibility, API behavior |
| Service integration | repository, transaction, uniqueness, outbox, event acknowledgement |
| End-to-end | mock source → pipeline → review → publication → public page |
| Failure/recovery | retry, DLQ, duplicate delivery, restart, stale/concurrent write |
| Load/concurrency | bounded collection, backpressure, contention và final invariants |

## 3. Kịch bản deterministic chuẩn

1. Transfer rumor nguồn A dùng alias `Man Utd`.
2. Nguồn B nói cùng sự kiện bằng `Manchester United`.
3. URL duplicate có tracking parameter và exact-content copy.
4. Near duplicate bổ sung chi tiết nhưng không tạo Story mới sai.
5. Official club update nâng đúng confirmation của claims được xác nhận.
6. Injury cùng club và match article được tách thành Story khác.
7. Generator tạo draft có citation; editor sửa, approve; admin publish.
8. Official update muộn nối vào cùng Story và tạo Story version mới.
9. Event được giao lặp và worker restart; không nhân đôi Story/claim.
10. Hai publish đồng thời/cùng key chỉ tạo một publication.

## 4. Failure tests

- 429 tôn trọng `Retry-After`; 500/timeout retry đúng loại và đúng giới hạn.
- Redirect tới địa chỉ bị cấm bị chặn; response quá lớn bị dừng an toàn.
- Invalid event/output không retry vô hạn và có error context inspect được.
- Unsupported claim hoặc confirmation bị nâng làm generation validation fail.
- Concurrent Story create/update không tạo duplicate hoặc mất timeline entry.
- Offset không được xác nhận trước durable write; outbox recovery có thể phát
  lặp nhưng consumer vẫn idempotent.
- Redis outage tuân theo policy đã công bố, không âm thầm biến cache thành truth.

## 5. Test oracle và fixture

Fixture cần stable title/body/time/ID. Expected result phải kiểm tra cả outcome
và lý do: duplicate kind, matching score breakdown, supporting source IDs,
confirmation transition và audit action. Snapshot chỉ dùng cho output ổn định;
invariant quan trọng cần assertion trực tiếp.

## 6. Load và concurrency

Load test ghi rõ máy, resource limit, worker count, partition, payload, duration,
p50/p95/p99, error và final invariant. Mục tiêu đầu tiên là chứng minh bounded
concurrency/backpressure và correctness dưới tải; không bịa benchmark hoặc chọn
SLO trước khi đo.

## 7. Cổng chất lượng

Chạy test hẹp nhất trước rồi mở rộng theo rủi ro. Python dự kiến dùng Ruff, mypy,
pytest/pytest-asyncio và `uv`; frontend giữ `pnpm`. Chỉ đưa command vào README
như lệnh hỗ trợ sau khi configuration tồn tại và command đã thực sự chạy thành
công. Docker smoke, integration và E2E chưa được coi là đạt cho tới khi có log
xác minh.

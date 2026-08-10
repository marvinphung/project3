# Reliability và recovery

FootballPulse dùng retry có giới hạn và giữ failure explicit. Không retry vô
hạn, không chuyển lỗi cấu hình/integrity thành fallback thành công.

| Boundary | Cơ chế | Recovery |
| --- | --- | --- |
| Crawler fetch/discovery | Retry policy theo domain, bounded attempts | Batch tiếp tục với source failure; lần kế tiếp chạy theo lịch |
| Mongo article outbox | Unique event ID + pending publisher | Publisher đọc lại pending sau restart |
| Story matching | Retryable worker result, processed-event marker | Requeue event; marker ngăn xử lý trùng |
| Publication outbox | Transactional insert + pending worker | Poll pending, ghi failure/attempt count, publish lại |
| AI enrichment | Batch status `FAILED_RETRYABLE`/`FAILED_TERMINAL` | Reprocess DAG chỉ chạy thủ công với batch được chọn |

Các invariant cần giữ:

- Idempotency key không đổi trong cùng một cửa sổ 6 giờ.
- Không acknowledge event trước khi state và outbox được ghi bền vững.
- Retryable failure không tạo Story/Publication mới ngoài lần xử lý hợp lệ.
- Terminal failure cần operator review trước khi reprocess.

## Acceptance tối thiểu

1. Dừng worker sau khi ghi state nhưng trước publish vẫn không mất outbox.
2. Chạy lại cùng event không tạo bản ghi duplicate.
3. Crawler/AI timeout tạo trạng thái failure quan sát được.
4. Reprocess thủ công giữ nguyên input hash và audit trail.

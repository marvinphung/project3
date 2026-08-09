# Thiết kế Kaggle batch adapter — WP 3.5

## Quyết định đã chốt

- Dùng Kaggle CLI theo pipeline private dataset → private kernel → poll → output.
- Mỗi cửa sổ 6 giờ tạo batch bất biến gồm `manifest.json` và `articles.jsonl`.
- Chỉ một Kaggle job được chạy; Mongo lease có expiry bảo vệ single-flight.
- Poll mỗi 30 giây, budget 90 phút; lỗi hạ tầng là retryable, tối đa hai retry.
- Import theo article; success được giữ, ERROR/thiếu/hash sai đi retry batch.
- Qwen3-8B 4-bit nhận English và trả English summary/claim có evidence.
- MongoDB giữ job state, raw English enrichment và grounding result; PostgreSQL
  Vietnamese projection vẫn thuộc phase sau.

## Boundary

Kaggle không kết nối database local. Dataset không chứa raw HTML, embedding,
Vietnamese, database endpoint hoặc secret. Kernel dùng model attachment đã pin,
không bật Internet và không chứa credential.

## Failure semantics

Hai output khác nhau cho cùng article hoặc `job-report` không khớp manifest là lỗi
terminal. CLI/network/timeout là retryable. Output hợp lệ được import idempotent kể
cả khi batch ở trạng thái `PARTIAL`.

Real Kaggle smoke không nằm trong verification offline của WP này; lần chạy đầu
cần user cho phép network/quota và phải báo riêng runtime, quota và quality.

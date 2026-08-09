# Thiết kế local Qwen/mock fallback — WP 3.6

## Provider policy

- `kaggle` là provider chính; `local` và `mock` chỉ được chọn rõ bằng config.
- Chỉ network/service/quota/GPU/kernel timeout hoặc kernel infrastructure error
  được chuyển Kaggle → local khi `allow_local_fallback=true`.
- Credential, privacy, input/output integrity, schema, grounding và conflicting
  output không được fallback để tránh che lỗi hệ thống.
- Mock chỉ chạy trong `test|demo`, tra bằng `article_version_id + input_hash` và
  trả lỗi khi không có fixture.

## Local runtime

Qwen3-4B-Instruct GGUF `Q4_K_M` dùng optional `llama-cpp-python`, CPU,
concurrency 1. Model lazy-load theo batch, giữ tối đa 15 phút idle, batch tối đa
20 article. Mỗi article có budget 5 phút; mỗi chunk 1.200 từ/overlap 150 từ,
2.500 output token và một structural repair.

Model path phải là GGUF local, không nằm trong Git. Có thể pin SHA-256; model chỉ
được đọc khi local provider thật sự chạy. Load/native runtime failure dừng batch;
timeout/output invalid chỉ tạo ERROR cho article liên quan.

## Shared validation

Kaggle, local và mock dùng cùng `article-enrichment.v1`, identity/hash check,
grounding validator và Mongo persistence. Không provider nào được tạo Vietnamese
projection hoặc ghi thẳng PostgreSQL public model trong phase này.

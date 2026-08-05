# Open Questions

Các mục dưới đây cố ý chưa được tự quyết định. Mỗi câu hỏi cần được khóa bằng
ADR, contract hoặc kết quả implementation/test trước khi component phụ thuộc.

## 1. Story và intelligence

- Trọng số, time window và threshold cụ thể cho từng event category là bao nhiêu?
- Tiêu chí nào chứng minh hai nguồn độc lập để đạt `MULTI_SOURCE`, đặc biệt với
  syndicated content?
- Confirmation có được hạ xuống không; nếu có, timeline và publication hiện hữu
  biểu diễn correction như thế nào?
- `OFFICIAL_ANNOUNCEMENT` là category độc lập hay là loại nguồn/update cho một
  Story `TRANSFER`/`INJURY` trong từng tình huống?
- Khi alias xung đột hoặc cùng tên, mức confidence nào bắt buộc editor xử lý?

## 2. Nội dung và editorial

- Story update nào tự động yêu cầu regeneration, update nào chỉ đánh dấu stale?
- Quy trình correction, unpublish, re-review và supersede bài đã publish là gì?
- Draft đã approve có được publish khi Story có version mới nhưng claims dùng
  trong draft không đổi không?
- Citation hiển thị ở cấp câu, đoạn hay danh sách nguồn cuối bài?
- Generated Article public cần nhãn minh bạch cụ thể như thế nào?

## 3. API và event contracts

- Tên cuối cùng và payload tối thiểu của các event sau `article.discovered.v1`?
- Public Story timeline expose toàn bộ hay chỉ projection đã biên tập?
- Pagination dùng cursor hay offset cho từng collection?
- Retention/replay policy của event và DLQ sau khi có số liệu local?
- Exact contract cho internal authentication và key rotation?

## 4. Triển khai

- Partition count và retention sau load measurement là bao nhiêu?
- Airflow 3 local executor nào vượt smoke test với resource budget của đồ án?
- Resource budget mục tiêu cho full local stack và máy chuẩn dùng demo?
- Search MVP dùng projection/query đơn giản hay cần capability riêng sau khi nối
  frontend thật?

## 5. Frontend và trải nghiệm

- Public page có hiển thị Story độc lập hay chỉ Generated Article kèm timeline?
- Editor cần compare revision ở mức text diff nào trong MVP?
- UI xử lý entity correction và Story merge tới đâu trong ba tuần?
- Metadata/SEO tối thiểu nào được yêu cầu cho đồ án dù Vite không SSR?

## 6. Kiểm thử và tiêu chí đo

- Ngưỡng acceptance cho matching precision/recall trên fixture mở rộng?
- SLO local nào đáng đo cho crawl-to-draft và publish-read visibility?
- Policy chính xác khi Redis unavailable: fail closed, degraded local limit hay
  từ chối capability nào?
- Bộ command build, migration, startup, integration, E2E và demo cuối cùng sau
  khi từng phần được triển khai và xác minh?

## 7. Cách đóng câu hỏi

Mỗi quyết định cần ghi context, lựa chọn, alternatives và consequences. Thay
đổi contract hoặc invariant phải có test tương ứng; thay đổi đắt đỏ hoặc ảnh
hưởng nhiều service nên có ADR thay vì chỉ cập nhật một đoạn mô tả.

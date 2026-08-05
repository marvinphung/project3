# Yêu cầu hệ thống

## 1. Yêu cầu chức năng

### Thu thập và bằng chứng

- Quản lý danh sách nguồn tin được phép và chính sách thu thập cơ bản.
- Đọc RSS, trang HTML đơn giản và deterministic mock source.
- Lưu URL gốc, URL canonical, title, content đã parse, thời gian và nguồn.
- Ghi lại lỗi 429, 5xx, timeout và kết quả retry thay vì bỏ qua im lặng.
- Không nhận URL crawl tùy ý trực tiếp từ public user.

### Xử lý Article

- Chuẩn hóa URL, title và content theo quy tắc deterministic.
- Phát hiện URL duplicate, exact content duplicate và near duplicate cơ bản.
- Giữ mọi Source Article; duplicate là một quan hệ, không phải lý do xóa.
- Xử lý lại cùng event mà không tạo bản ghi nghiệp vụ lặp.

### Intelligence và Story

- Nhận diện `Player`, `Coach`, `Club`, `Competition` cùng alias.
- Phân loại bài vào một trong năm category MVP.
- Trích xuất claim kèm nguồn và mức xác thực.
- Khớp Source Article với Story có sẵn hoặc tạo Story mới bằng quy tắc giải thích
  được.
- Cập nhật timeline, confirmation và version khi có diễn biến mới.
- Cho phép editor sửa entity, reassign hoặc merge Story có audit trail.

### Tạo và biên tập nội dung

- Tạo draft từ structured claims, không dùng trang scrape tùy ý làm prompt.
- Mọi fact trong draft phải truy được về claim và Source Article.
- Lưu provider/model/prompt version/input Story version và validation result.
- Hỗ trợ edit, review, approve, reject và publish theo quyền.
- Publish một revision đã approve theo cách idempotent.

### Web

- Public: danh sách tin, chi tiết bài, nguồn tham khảo và Story timeline.
- Admin: xem source/article/story/draft, xử lý review và publish theo quyền.
- Hiển thị rõ loading, empty và error state; không âm thầm dùng mock khi API lỗi.

## 2. Yêu cầu phi chức năng

| Thuộc tính | Yêu cầu MVP |
| --- | --- |
| Correctness | Không làm mạnh hơn mức chắc chắn của nguồn; giữ invariant dữ liệu |
| Reliability | Chịu event lặp, retry có giới hạn, lỗi hết lượt được lưu để xử lý |
| Concurrency | Mọi queue, worker, request và provider call đều có giới hạn |
| Security | Chỉ crawl domain cho phép; chống SSRF; auth/RBAC cho admin |
| Traceability | Có correlation, causation, source reference và audit history |
| Offline | Test/demo không phụ thuộc Internet hoặc external LLM credential |
| Observability | Log có cấu trúc, health/readiness và số đếm vận hành cục bộ |
| Maintainability | Business logic tách khỏi HTTP, worker và storage adapter |

## 3. Quyền truy cập

- Public read không cần đăng nhập.
- `EDITOR`: xem bằng chứng, sửa draft, review, approve và reject.
- `ADMIN`: có toàn bộ quyền Editor; thêm publish, quản lý source/crawl/retry và
  merge/reassign Story.
- Internal command dùng danh tính nội bộ được cấu hình, không dùng public token.

## 4. Tiêu chí chấp nhận MVP

1. Một lần chạy deterministic đi xuyên suốt từ mock source tới public web.
2. Alias `Manchester United`, `Man United`, `Man Utd`, `MUFC` về cùng Club.
3. Exact duplicate không đi lại toàn pipeline nhưng vẫn xem được nguồn.
4. Near duplicate có thể bổ sung bằng chứng mà không tạo Story sai.
5. Official update nối vào Story cũ và không biến rumor thành fact trước thời điểm.
6. Duplicate delivery và worker restart không tạo dữ liệu nghiệp vụ lặp.
7. Chỉ revision hiện hành đã approve mới publish; gọi lặp chỉ có một kết quả.
8. Injury và match fixture không bị gom vào transfer Story.

## 5. Ràng buộc

- Thời gian thực hiện ba tuần; ưu tiên một vertical slice hoàn chỉnh.
- Python là ngôn ngữ backend chính; frontend React/Vite hiện có được giữ lại.
- Không đưa công nghệ mở rộng vào chỉ để tăng độ phức tạp kiến trúc.

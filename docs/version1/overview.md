# Tổng quan hệ thống

## 1. Tầm nhìn

FootballPulse giúp độc giả theo dõi **một sự kiện bóng đá đang phát triển** thay
vì tự ghép nhiều bài báo lặp lại. Hệ thống trả lời: chuyện gì thay đổi, nguồn nào
hỗ trợ, mức xác thực hiện tại là gì và timeline đã tiến triển ra sao.

## 2. Trải nghiệm mục tiêu

Khi mở trang Vinícius Júnior, người dùng thấy timeline tiếng Việt:

```text
00:00 — Real Madrid đang đàm phán gia hạn với Vinícius.
06:00 — Arsenal đã liên hệ với đại diện Vinícius.
12:00 — Arsenal được cho là đã gửi đề nghị €180m; nhiều nguồn xác nhận.
18:00 — Không có thay đổi nên không có entry.
```

Cùng entry có thể xuất hiện ở trang Player, Club, Coach hoặc Competition qua
relationship, không lưu nhiều bản sao.

## 3. Người dùng

| Nhóm | Nhu cầu |
| --- | --- |
| Độc giả | Đọc timeline và Generated Article tiếng Việt, xem nguồn |
| Editor | Kiểm tra claims/evidence, review timeline bị flag và long-form draft |
| Admin | Quản lý RSS, retry/replay, aliases, Story merge và publication |
| Nhóm phát triển | Chạy local/offline demo, drill-down batch và tái hiện failure |

## 4. Miền nghiệp vụ

Entity MVP: `Player`, `Coach`, `Club`, `Competition`. Category:

```text
TRANSFER
INJURY
MATCH
PRESS_CONFERENCE
OFFICIAL_ANNOUNCEMENT
```

Confirmation thuộc từng claim:

```text
RUMOUR → REPORTED → MULTI_SOURCE → OFFICIAL
```

Mức này tăng/giảm theo evidence và source independence, không theo độ tự tin tự
báo của model.

## 5. Ranh giới dữ liệu và ngôn ngữ

- Danh sách RSS uy tín được Admin cấu hình trước; không crawl URL public tùy ý.
- MongoDB giữ evidence/enrichment English; Source Article versions bất biến.
- PostgreSQL giữ canonical product data, English source-of-truth và Vietnamese
  timeline/content projection.
- Search, embedding, similarity và Story matching chỉ dùng English.
- Kaggle hỗ trợ compute AI nhưng không sở hữu state; mock mode là bắt buộc.

## 6. Định nghĩa thành công

Demo offline phải chứng minh transfer Story tiến triển qua các cửa sổ 6 giờ,
aliases về cùng entity, exact duplicate không chạy AI, near duplicate bổ sung
claim, cửa sổ không đổi không tạo entry, official denial/correction không nâng
sai claim cũ, injury/match tách Story, draft được review/publish và redelivery/
restart không tạo state lặp.

## 7. Ngoài phạm vi

Separate vector database, arbitrary-site crawling, Kubernetes/cloud deployment,
recommendation, social/comment, live scores, full multilingual processing,
scheduled publication và autonomous long-form publication không thuộc MVP.

# Tổng quan hệ thống

## 1. Tầm nhìn

FootballPulse giúp người đọc theo dõi **một sự kiện bóng đá đang phát triển**
thay vì phải tự ghép nhiều bài báo gần giống nhau. Hệ thống thu thập bằng chứng,
nhận biết mối liên hệ giữa các nguồn, duy trì timeline và tạo bản tin tổng hợp
có thể truy ngược về nguồn.

Giá trị chính không nằm ở việc crawl thật nhiều hay sinh thật nhiều văn bản,
mà ở khả năng trả lời bốn câu hỏi:

1. Chuyện gì đang xảy ra?
2. Những nguồn nào đang nói về chuyện đó?
3. Diễn biến và mức độ xác thực đã thay đổi ra sao?
4. Nội dung được xuất bản dựa trên những claims nào?

## 2. Người dùng

| Nhóm | Nhu cầu chính |
| --- | --- |
| Độc giả | Đọc tin tổng hợp, xem nguồn và timeline của Story |
| Editor | Kiểm tra claims, sửa draft, approve hoặc reject |
| Admin | Publish, quản lý nguồn, xử lý lỗi và thao tác quản trị Story |
| Nhóm phát triển | Chạy demo offline, quan sát pipeline và tái hiện lỗi |

MVP không có public registration, recommendation hay cá nhân hóa.

## 3. Phạm vi miền nghiệp vụ

MVP hỗ trợ entity `Player`, `Coach`, `Club`, `Competition` và năm loại sự kiện:

```text
TRANSFER
INJURY
MATCH
PRESS_CONFERENCE
OFFICIAL_ANNOUNCEMENT
```

Mức độ xác thực tăng theo bằng chứng, không theo độ tự tin của AI:

```text
RUMOUR → REPORTED → MULTI_SOURCE → OFFICIAL
```

Một Story có thể không đi qua đủ mọi mức. Việc tăng hoặc giảm mức xác thực phải
được giải thích bằng claims và nguồn hỗ trợ.

## 4. Ranh giới sản phẩm

FootballPulse không phải hệ thống sao chép và viết lại bài báo. Nội dung gốc
được giữ riêng; hệ thống chỉ tạo bài mới từ tập claims có cấu trúc. Generated
Article phải được đánh dấu là nội dung tổng hợp và qua editorial review.

Hệ thống cũng không cố crawl mọi website. MVP dùng danh sách nguồn được cấu
hình trước, RSS/HTML đơn giản và mock source. Điều này giữ phạm vi an toàn,
deterministic và phù hợp thời gian đồ án.

## 5. Định nghĩa thành công

MVP thành công khi demo offline chứng minh được một transfer Story phát triển
qua nhiều nguồn, alias khác nhau, duplicate và official update; đồng thời tách
được injury và match không liên quan. Draft có dẫn nguồn được review rồi publish,
và việc giao event lặp hoặc restart worker không tạo Story/claim/publication lặp.

## 6. Ngoài phạm vi

Vector search, embedding clustering, live score, social publishing, bình luận,
recommendation, đa ngôn ngữ hoàn chỉnh, arbitrary-site crawling, cloud/Kubernetes
và autonomous publishing là hướng tương lai, không phải điều kiện MVP.

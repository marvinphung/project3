# Thiết kế hybrid Story candidate retrieval — WP 4.2

## Phạm vi

WP 4.2 tìm và xếp hạng các Story có thể nhận một validated English enrichment.
Kết quả là `ATTACH`, `CREATE`, `REVIEW` hoặc lỗi retryable. Candidate retrieval
không tự ghi Claim, tính confirmation hay tạo timeline; các bước đó thuộc WP sau.

## Canonical Story embedding

Mỗi `story_id + story_version` có một English embedding bất biến. Input được tạo
deterministic từ event type, canonical entity names và ordered canonical claims:

```text
event_type: TRANSFER
entities: Arsenal | Real Madrid | Vinícius Júnior
claims:
Arsenal SUBMITTED_BID Vinícius Júnior amount=180000000 currency=EUR
```

Embedding lại khi Story version đổi; historical vectors được giữ để audit decision.
MVP dùng exact pgvector scan, chưa tạo HNSW/IVFFlat. Không dùng trung bình Source
Article vectors hoặc vector bài mới nhất vì wording/duplicate source có thể làm lệch
đại diện Story.

## Hard filters

SQL lọc trước vector search:

- event type phải giống hoàn toàn;
- `CLOSED` bị loại; `STALE` còn trong time window vẫn hợp lệ;
- phải có ít nhất một canonical entity trùng nhau;
- `MATCH` dùng 3 ngày, `INJURY` 21 ngày, `DISCIPLINARY` 14 ngày,
  `TRANSFER|CONTRACT|MANAGERIAL` 30 ngày và `OTHER` 7 ngày.

Các window là config khởi điểm cho benchmark. Injury/transfer conflict không thể
merge dù cosine similarity cao.

Transfer Story có granularity theo saga của primary player và current/selling-club
context trong một cửa sổ. Nhiều buying club có thể tạo các Claim khác nhau trong
cùng Story. `CONTRACT` vẫn là Story riêng và player timeline có thể xen kẽ nhiều
Story.

## Vector retrieval và explainable score

Sau hard filter, pgvector trả tối đa 20 candidate gần nhất. Rule score `0–100`:

| Thành phần | Điểm tối đa |
| --- | ---: |
| Cosine similarity | 30 |
| Primary entity match | 25 |
| Entity overlap còn lại | 15 |
| Predicate progression/compatibility | 20 |
| Time distance | 10 |

Transfer saga bắt buộc cùng primary player; current-club conflict đi `REVIEW`.
Match bắt buộc cùng hai đội và kickoff bucket. Predicate progression như
`CONTACTED → SUBMITTED_BID` được điểm cao. Qualifier đổi không bị loại vì có thể
là diễn biến mới.

Decision lưu candidate Story version, từng score component, reason codes,
matcher version và embedding model version để audit.

## Decision policy

- Không có candidate sau một retrieval thành công: `CREATE`.
- Top candidate vượt attach threshold và hơn candidate thứ hai trên margin: `ATTACH`.
- Hai candidate đầu cách nhau không quá margin khởi điểm 5 điểm: `REVIEW`.
- Identity conflict hoặc thiếu primary entity: `REVIEW`.
- Top score dưới review threshold: `CREATE`.
- Điểm nằm giữa review/attach threshold: `REVIEW`.

Attach/review thresholds và margin là config. WP 4.2 không khóa giá trị cuối trước
fixture benchmark và Collaboration Gate 4.2.

## Failure policy

Lỗi kỹ thuật không được đổi thành `CREATE`:

- thiếu article embedding: retryable error;
- thiếu embedding của current Story version: tạo embedding rồi retry;
- PostgreSQL/pgvector unavailable: retry event, chưa commit processed marker;
- optimistic conflict khi attach: đọc version mới và chạy retrieval lại;
- thiếu primary entity: `REVIEW`, không đoán.

## Acceptance và benchmark

- Unit tests khóa category/time/status/entity filters, top-K và score breakdown.
- Transfer progression, match identity, injury/transfer conflict và near-tie có
  fixtures riêng.
- Missing embedding không silently tạo Story mới.
- PostgreSQL integration khóa query scope và Story-version binding.
- Benchmark báo precision, recall, false attach, false create và review rate; user
  chọn threshold tại Collaboration Gate 4.2.

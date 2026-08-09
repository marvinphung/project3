# WP 3.4 — AI contracts và grounding validation

## Boundary

Article enrichment lưu English `summary_en` và structured claims trong MongoDB.
Vietnamese chỉ là PostgreSQL presentation projection ở Story/timeline/content phase.
WP này định nghĩa validator EN/VI để tái sử dụng, chưa tạo timeline.

## Contract

Input `article-enrichment.v1` gồm immutable article/version hash, English title và
cleaned content, source metadata, canonical entities và unresolved mentions. Không
gửi raw HTML, embedding, secret, database endpoint hoặc Vietnamese text.

Output gồm event type, English summary và claims. Claim dùng predicate vocabulary
v1, canonical entity IDs có trong input, typed qualifiers, certainty và exact
evidence quote/global offsets. Model/prompt/schema/validator version luôn được giữ
để audit.

## Processing

Content dài chia khoảng 1.200 từ, overlap 150 từ và giữ global offsets. Claim trùng
được merge theo subject/predicate/object/normalized qualifiers; conflict không bị
xóa. Strict schema cho tối đa một structural repair attempt. Validator xử lý từng
claim để cho phép partial success; không còn claim hợp lệ thì cần content review.

Vietnamese projection chỉ được tham chiếu validated claim IDs. Entity, amount,
currency, date, score và negation anchors phải nhất quán với English facts.

## Events

`article.enriched.v1` chỉ chứa identity, counts và generation metadata; full summary,
claim/evidence nằm ngoài Kafka. Output hoàn toàn invalid phát operational
`article.enrichment.failed.v1` với error metadata redacted.

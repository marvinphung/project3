# Content Summary Service

## Purpose

`content-summary-service` tao timeline item theo tung entity. Service gom cac
bai co cung entity trong fixed 3-hour UTC window, chon toi da 5 bai lien quan
nhat, goi LLM 1 lan de sinh `title` va `content`, roi luu ket qua vao MongoDB
`entity_timeline_summaries`.

Service nay khong crawl, khong extract entity va khong ghi PostgreSQL.

## Position In Flow

```text
crawler -> entities-extraction-service -> content-summary-service -> publish
```

Airflow task tuong ung:

```text
footballpulse_pipeline.content_summary
```

CLI command:

```bash
python -m footballpulse_pipeline summary --backfill-days 7
```

Docker command:

```bash
docker compose -f docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary --backfill-days 7
```

Local `uv` command:

```bash
uv run python -m footballpulse_pipeline summary --backfill-days 7
```

Run mot window cu the:

```bash
uv run python -m footballpulse_pipeline summary --window-start 2026-08-20T21:00:00Z --window-end 2026-08-21T00:00:00Z
```

## Inputs

MongoDB:

- `news_metadata`
- `news_content`
- `news_entities`

Prompt:

- prompt file trong repo
- prompt viet bang tieng Anh
- prompt yeu cau LLM tra ve JSON co `title` va `content`

LLM configuration:

- `FOOTBALLPULSE_LLM_PROVIDER`
- `FOOTBALLPULSE_LLM_MODEL`
- `FOOTBALLPULSE_LLM_API_KEY` hoac provider-specific key
- `OPENAI_BASE_URL` neu dung OpenAI-compatible provider

## Outputs

MongoDB:

- `entity_timeline_summaries`

Moi document tuong ung:

```text
one entity + one 3-hour UTC window
```

## Window Rule

Timeline windows co dinh theo UTC:

```text
00:00-03:00
03:00-06:00
06:00-09:00
09:00-12:00
12:00-15:00
15:00-18:00
18:00-21:00
21:00-24:00
```

Service dung `news_metadata.crawl_date` de chia bucket, khong dung
`published_time`.

Neu job chay luc `01:00 UTC`, latest closed window la `21:00-24:00 UTC` cua ngay
truoc. Service khong tao summary cho window dang mo.

## Backfill Rule

Mac dinh service quet cac window co article trong 7 ngay gan nhat.

Voi moi window:

- neu entity/window da co `status=COMPLETED` thi skip
- neu chua co thi tao summary
- force recompute chi dung khi can regenerate co chu dich

## Entity Selection Rule

Service khong tao summary cho moi entity trong DB.

Cho moi window, service nhin lai 24 gio ket thuc tai `window_end` va chon entities
co distinct article count cao nhat theo type:

- top 50 `PLAYER`
- top 30 `COACH`
- top 30 `CLUB`

Distinct article count nghia la:

```text
1 article mention entity 1 lan hay 10 lan deu chi tinh 1
```

`COMPETITION` khong nam trong quota auto-summary hien tai.

## Article Selection Rule

Cho mot entity trong mot 3h window:

1. Lay cac articles trong window co mention canonical entity do.
2. Dem so lan canonical entity name xuat hien trong `news_content.filtered_content`.
3. Chon toi da 5 articles co mention count cao nhat.
4. Neu bang diem, article co `crawl_date` moi hon dung truoc.
5. Dua `news_content.content` cua cac article da chon vao prompt, sap xep moi
   nhat truoc.

Neu chi co 1 article thi van tao summary binh thuong.

## LLM Contract

Service chi call LLM 1 lan cho moi entity/window can generate.

Input:

- target entity name
- target entity type
- toi da 5 clean article contents
- crawled timestamp cua moi article

Output bat buoc:

```json
{
  "title": "short timeline title",
  "content": "aggregated timeline content"
}
```

Mapping luu tru:

- `title` -> `entity_timeline_summaries.short_description`
- `content` -> `entity_timeline_summaries.aggregated_news`

Khong con dung flow 2 LLM calls. Khong con dung rule entities `>=50%` hoac
`>=80%`; cac field legacy `entities_50` va `entities_80` de rong neu schema cu
van can.

## Idempotency

`summary_id` phai deterministic theo:

```text
entity_id + window_start + window_end
```

Do do re-run job se skip hoac upsert dung timeline item, khong tao duplicate.

## Downstream Contract

`publish` mong doi:

- `status=COMPLETED`
- `entity_id`
- `canonical_name`
- `entity_type`
- `window_start`
- `window_end`
- `article_ids`
- `short_description`
- `aggregated_news`

## Non-Goals

- Khong crawl.
- Khong extract entity.
- Khong tinh frontend popularity truc tiep.
- Khong ghi Supabase PostgreSQL.
- Khong phuc vu API runtime.

## Debug Checklist

Neu summary tao it timeline:

1. Kiem tra window co `news_metadata.crawl_date` trong range khong.
2. Kiem tra cac article trong window da co `news_entities` khong.
3. Kiem tra target entity co nam trong quota 24h theo type khong.
4. Kiem tra summary entity/window da co `status=COMPLETED` nen bi skip khong.
5. Kiem tra command co `--backfill-days 7` khi can backfill lich su khong.

Neu LLM ton token qua nhieu:

1. Kiem tra moi entity/window chi gui toi da 5 articles.
2. Kiem tra ranking mention count dang dung `filtered_content`.
3. Kiem tra prompt co dua toan bo article ngoai top 5 khong.

Neu UI chua thay timeline sau khi summary thanh cong:

1. Kiem tra `entity_timeline_summaries` co summary `COMPLETED`.
2. Kiem tra summary co `published_at` chua.
3. Chay publish sang Supabase.
4. Kiem tra backend doc dung Supabase URL.

## Safe Changes

Co the sua trong boundary service nay:

- window lookback/backfill behavior
- entity quota selection
- article ranking strategy
- prompt template
- LLM provider adapter
- parsing LLM response

Khong nen sua o day:

- crawler extraction logic
- NER model threshold
- PostgreSQL API response shape neu khong cap nhat backend docs/tests
- frontend rendering

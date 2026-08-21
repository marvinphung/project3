# Entities Extraction Service

## Purpose

`entities-extraction-service` la stage thu hai trong pipeline. Service nay nhan
cac bai da crawl, tao `filtered_content` bang cach replace aliases ve canonical
club name, extract entities bang model hien tai, canonicalize mention va luu ket
qua vao MongoDB `news_entities`.

Service nay la owner cua runtime entity extraction. Model, threshold, CPU/GPU
device va canonical alias handling nam trong boundary nay.

## Position In Flow

```text
crawler -> entities-extraction-service -> content-summary-service -> publish
```

Airflow task tuong ung:

```text
footballpulse_pipeline.entities_extraction
```

CLI command:

```bash
python -m footballpulse_pipeline process --limit 100
```

Docker command:

```bash
docker compose -f docker-compose.v2.yml run --rm entities-extraction python -m footballpulse_pipeline process --limit 100
```

Local `uv` command:

```bash
uv run python -m footballpulse_pipeline process --limit 100
```

## Backlog Rule

Service xu ly cac article thoa:

```text
news_metadata exists
news_entities missing
```

Neu `news_entities` da ton tai thi mac dinh skip de tranh overwrite ket qua da
extract.

## Inputs

MongoDB:

- `news_metadata`
- `news_content`
- `canonical_entities`

Configuration:

- `NER_DEVICE`, mac dinh nen dung `cpu` trong local/light deploy
- `ENTITY_EXTRACTION_MIN_CONFIDENCE`, target hien tai la `0.95`
- model/provider env cua service neu can

## Outputs

MongoDB:

- update `news_content.filtered_content`
- update `news_content.filtered_at`
- create `news_entities`

## Internal Pipeline

1. Lay backlog article co metadata nhung chua co `news_entities`.
2. Load `news_content.content`.
3. Load canonical alias catalog tu `canonical_entities` hoac JSON/imported data.
4. Tao `filtered_content`:
   - input la `news_content.content`
   - replace aliases ve canonical club name
   - uu tien alias dai hon truoc de tranh cascade replacement
5. Luu `filtered_content` va `filtered_at` vao `news_content`.
6. Chay model entity extraction tren `filtered_content`.
7. Chi giu spans co score `>= ENTITY_EXTRACTION_MIN_CONFIDENCE`.
8. Map mention sang canonical entity neu match duoc.
9. Luu canonical mentions vao `news_entities`.

## Entity Types

Entities co the gom:

- `PLAYER`
- `CLUB`
- `COACH`
- `COMPETITION`

Content summary auto-quota hien chi tao summary cho:

- top 50 `PLAYER`
- top 30 `COACH`
- top 30 `CLUB`

`COMPETITION` van co the duoc extract va publish vao read model/popularity neu
co mention, nhung khong nam trong quota auto-summary hien tai.

## Canonicalization

`filtered_content` la ban text da replace alias ve canonical club name. Vi du:

```text
MU -> Manchester United
Man United -> Manchester United
```

Extraction dung `filtered_content`, khong dung raw `content`, de model thay
canonical terms on dinh hon.

Canonical mention luu vao `news_entities` phai co:

- `canonical_entity_id`
- `canonical_name`
- `label`
- `score`
- span offsets tren `filtered_content`

## Idempotency

- Article da co `news_entities` thi skip.
- `filtered_content` co the da ton tai thi khong can tao lai neu khong force.
- Reprocess toan bo entity chi nen chay bang script/manual task rieng khi thay
  model, threshold hoac canonical catalog.

## Downstream Contract

`content-summary-service` mong doi:

- `news_entities.entities` co canonical entity id/name/type
- `news_content.filtered_content` ton tai de dem mention count cua target entity
- `news_content.content` ton tai de dua vao LLM prompt
- `news_metadata.crawl_date` ton tai de chia bucket

`publish` mong doi:

- `news_entities` co canonical mentions de tinh `mention_count_24h`

## Non-Goals

- Khong crawl bai moi.
- Khong tao summary.
- Khong goi LLM.
- Khong publish Supabase.
- Khong tinh timeline windows.

## Debug Checklist

Neu service chay nhung processed=0:

1. Kiem tra co article trong `news_metadata` khong.
2. Kiem tra cac article do da co `news_entities` chua.
3. Kiem tra `--limit` co qua nho khong.
4. Kiem tra Mongo DB name dung chua.

Neu entity qua nhieu hoac qua it:

1. Kiem tra `ENTITY_EXTRACTION_MIN_CONFIDENCE`.
2. Kiem tra service dang dung `filtered_content` hay khong.
3. Kiem tra canonical alias catalog co replace sai alias chung chung khong.
4. Kiem tra model/device log luc load model.

Neu frontend top entities thieu player/coach:

1. Kiem tra `news_entities.entities.label` co `PLAYER`/`COACH` khong.
2. Kiem tra mentions co `canonical_entity_id` va `canonical_name` khong.
3. Chay publish de refresh `entities.mention_count_24h`.

## Safe Changes

Co the sua trong boundary service nay:

- threshold
- device CPU/GPU
- alias replacement
- canonical mapping
- extraction logging
- backlog selection

Khong nen sua o day:

- LLM prompt
- 3h window planning
- Supabase schema
- frontend routing

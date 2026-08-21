# Version 2 Source Of Truth: Entity Timeline Architecture

## Status

Accepted working target for the current refactor direction.

## Date

2026-08-20

## Purpose

Tai lieu nay la nguon mo ta chuan cho muc tieu hien tai cua FootballPulse v2.
Khi cac docs khac mau thuan voi tai lieu nay, uu tien sua cac docs khac theo tai
lieu nay.

Tai lieu nay mo ta:

- flow nghiep vu muc tieu
- boundary giua cac service
- logic tao timeline theo entity
- trach nhiem cua Mongo, Supabase, backend API, va frontend

No khong co muc tieu mo ta lich su implementation cu.

## Product Goal

FootballPulse v2 khong con tap trung vao viec chi crawl va hien thi danh sach bai
bao raw.

Muc tieu moi:

- crawl bai bao tu nhieu nguon
- trich xuat entity cho moi bai
- nhom bai bao theo entity trong cua so thoi gian 3 gio
- dung LLM tao bai tong hop cho tung entity
- tao title va content cho timeline item cua entity do
- publish du lieu tong hop len Supabase PostgreSQL
- backend API doc Supabase
- frontend hien thi entity noi bat va timeline rieng cho tung entity

## High-Level System Flow

```text
Airflow-managed pipeline:
(1) crawler -> (2) entities-extraction-service -> (3) content-summary-service -> (4) publish

Serving layer:
backend-api -> frontend
```

Serving layer:

- `backend-api` doc doc quyen tu Supabase PostgreSQL read model (khong doc Mongo)
- `frontend` goi `backend-api`
- `frontend` deploy tren Vercel
- `backend-api` deploy tren Render

## Service Boundaries

### 1. `crawler`

Trach nhiem:

- crawl bai bao nguon
- canonicalize URL
- luu metadata bai bao
- luu cleaned content cua bai bao

Mongo output toi thieu:

- `news_metadata`
- `news_content`

Crawler khong tao timeline.

### 2. `entities-extraction-service`

Trach nhiem:

- tim backlog bai can trich xuat entity
- extract entities tu article content
- luu ket qua vao `news_entities`

Backlog rule:

```text
news_metadata exists
news_entities missing
```

Hay noi cach khac:

- service nay lay cac bai da duoc crawl
- nhung chua co document `news_entities`
- sau do extract entity va ghi vao `news_entities`

Mongo output:

- `news_entities`

Service nay la owner cua runtime entity extraction.
NER runtime va config cua no phai nam tai boundary nay, khong nam o service khac.

Canonical entity/alias data nam trong Mongo collection `canonical_entities`.
Alias khong can publish sang PostgreSQL. Pipeline dung aliases de rewrite cac bien
the trong `clean_content` ve `canonical_name` truoc khi extract/group.

Vi du:

- `MU`
- `Man United`
- `Man Utd`

duoc rewrite ve:

```text
Manchester United
```

Chi tiet schema xem:

- `docs/version2/mongo-canonical-entities-schema.md`

### 3. `content-summary-service`

Trach nhiem:

- tao timeline item theo tung entity
- gom cac bai lien quan trong cua so 3 gio theo `news_metadata.crawl_date`
- chi generate timeline theo quota 24h: top 50 `PLAYER`, top 30 `COACH`,
  top 30 `CLUB`
- goi LLM 1 lan de tao `title` va `content`
- luu ket qua tong hop vao DB

Service nay khong crawl va khong extract entity.
No su dung du lieu da co trong:

- `news_metadata`
- `news_content`
- `news_entities`

### 4. `publish`

Trach nhiem:

- materialize du lieu tu Mongo sang Supabase PostgreSQL
- publish du lieu timeline/entity summary phuc vu backend API va frontend

Publish khong tao summary moi.
No chi chuyen read model can thiet len Supabase.

### 5. `backend-api`

Trach nhiem:

- chi doc du lieu tu Supabase PostgreSQL
- expose API cho frontend

Backend API khong doc Mongo trong target architecture nay.

### 6. `frontend`

Trach nhiem:

- hien thi danh sach entities noi bat
- cho phep di vao timeline rieng cua tung entity
- render timeline items duoc tong hop san

Frontend khong goi worker, khong doc DB truc tiep.

## Core Timeline Concept

Moi entity co timeline rieng cua no.

Vi du:

- Arsenal co timeline rieng
- Real Madrid co timeline rieng
- Vinicius Junior co timeline rieng
- Premier League co timeline rieng neu duoc track nhu mot entity

Mot bai bao co the dong gop vao nhieu timeline neu bai do chua nhieu entity.

## Timeline Window Rule

Window muc tieu hien tai:

```text
3 hours
```

Moi timeline item duoc tao dua tren cac bai bao cua mot entity trong cua so 3
gio gan nhat. Window duoc chia theo UTC va dung `news_metadata.crawl_date` lam
timestamp bucket. Khong dung `published_time` de chia bucket summary, vi
`crawl_date` phan anh thoi diem pipeline nhin thay bai bao.

## Content Summary Service Logic

### Step 0: Select entities to update

Moi lan chay summary mac dinh se quet cac bucket 3 gio trong 7 ngay gan nhat,
dua tren `news_metadata.crawl_date`.

Neu mot bucket/window chua co summary thi service tao summary cho bucket do.
Neu summary cua entity/window da ton tai voi status `COMPLETED` thi service skip,
tru khi chay voi che do force recompute.

Co the chay mot window cu the bang `--window-start` va `--window-end`.

Service khong update timeline cho moi entity trong DB.

Service chi lay entities xuat hien trong nhieu distinct articles nhat trong 24
gio gan nhat, tinh theo `news_metadata.crawl_date`, theo quota:

- top 50 `PLAYER`
- top 30 `COACH`
- top 30 `CLUB`

Moi article chi dong gop toi da 1 count cho moi entity.

Chi cac entities trong quota nay moi duoc generate timeline summaries cho window
dang chay.

### Step A: Select articles for one entity

Cho mot entity `X`, service se lay:

- tat ca bai bao co chua entity `X`
- trong `news_entities`
- va nam trong time window 3 gio theo `news_metadata.crawl_date`

De tiet kiem token LLM, service khong gui tat ca bai vao prompt.

Tu candidate articles cua entity `X`, service chon toi da 5 bai co so lan nhac
entity `X` nhieu nhat trong `news_content.filtered_content`.

Ranking:

1. mention count cua canonical entity `X` trong `filtered_content`, giam dan
2. `crawl_date`, moi nhat truoc

Neu co it hon 5 bai thi dung tat ca. Neu chi co 1 bai thi van tao title va
content nhu binh thuong.

Input thuc te cua buoc tong hop duoc tao tu:

- `news_content.content` cho LLM prompt
- `news_content.filtered_content` de dem so lan nhac target entity
- `news_metadata.crawl_date` de chia window va sap xep thoi gian

Tat ca bai duoc gui vao LLM theo thu tu `crawl_date` moi nhat len truoc.

### Step B: LLM Call - Timeline title and content

Input:

- toi da 5 cleaned content cua cac bai co entity `X`, da chon theo mention
  count trong `filtered_content`
- thu tu bai theo `crawl_date` moi nhat len truoc
- prompt bang tieng Anh

Output:

- `title`: headline ngan gon de hien tren timeline
- `content`: ban tong hop thong tin tu tap bai cua entity `X`

Y nghia:

- `title` la noi dung ngan de UI hien thi tren timeline
- `content` la noi dung tong hop chi tiet hon cho timeline item

### Step C: Persist summary results

Sau LLM call, service luu:

- content/aggregated news
- title
- metadata can thiet de gan voi entity va time window
- selected `article_ids` da gui vao prompt

Summary records duoc luu vao Mongo collection `entity_timeline_summaries`.

## Publish Logic

### Initial/backfill summary before publish

Truoc khi publish, `content-summary-service` can tao summary cho cac bucket 3
gio trong 7 ngay gan nhat. Command mac dinh:

```bash
python -m footballpulse_pipeline summary
```

Command nay chi tao phan con thieu; cac entity/window da co summary `COMPLETED`
se duoc skip.

Muc tieu la tao bo timeline co san trong Mongo `entity_timeline_summaries`, sau
do publish materialize sang PostgreSQL de backend va frontend doc.

### Incremental publish

Nhung lan publish sau:

- chi can dua timeline moi len
- khong can rebuild toan bo lich su neu khong co yeu cau replay

## Data Ownership

### MongoDB

Mongo la pipeline store.

No chua:

- raw-ish metadata va cleaned article content
- entity extraction results
- summary/intermediate timeline generation results

Mongo khong phai serving database cuoi cho frontend production.

### Supabase PostgreSQL
 
Supabase la serving/read database.
 
No chua toan bo read model day du cho serving layer:
 
- `entities`: canonical entities voi 24h distinct article mention counts, aliases, slugs
- `source_articles`: metadata day du cua cac bai bao nguon
- `entity_timeline_items`: cac timeline items duoc tong hop theo entity va 3h window
- `timeline_item_articles`: quan he N-N mapping giua timeline item va source articles
 
Backend API va frontend chi doc du lieu tu PostgreSQL, hoan toan khong truy van MongoDB.

`mention_count_24h` phai duoc publish tu Mongo `news_entities` + `news_metadata`
theo distinct article count trong 24 gio gan nhat. No khong duoc tinh tu
`entity_timeline_items`, vi frontend can hien top entities ke ca khi entity do
chua co timeline summary moi.

## Frontend/Product Expectations

Frontend can nhan duoc tu backend API:

- danh sach entities noi bat, sap xep theo muc do xuat hien/noi bat
- home page hien toi da top 100 entities trong 24h, ke ca entity chua co
  timeline summary
- tab `/cau-thu` hien top 50 `PLAYER` trong 24h
- tab `/hlv` hien top 30 `COACH` trong 24h
- tab `/clb` hien top 30 `CLUB` trong 24h
- timeline rieng cua tung entity
- timeline item da co:
  - title
  - content tong hop
  - timestamp/time bucket

UI khong hien raw worker details, khong phu thuoc vao Mongo.

## Naming Direction

Target naming tu tai lieu nay:

- `entities-extraction-service` la ten boundary dung cho stage sau crawler
- `content-summary-service` la ten boundary dung cho stage tong hop theo entity

Neu codebase hien tai con ten cu nhu:

- `ai-content-service`
- runtime entity extraction dat o `intelligence-service`

thi do duoc xem la implementation chua refactor xong, khong phai target
architecture.

## Rules For Updating Other Docs

Khi sua cac docs khac:

1. Uu tien boundary moi:
   - `crawler`
   - `entities-extraction-service`
   - `content-summary-service`
   - `publish`
2. Khong mo ta stage sau crawler la `ai-content-service` neu dang noi ve target architecture.
3. Khong dat runtime entity extraction o `intelligence-service` trong docs target.
4. Moi timeline phai duoc mo ta la timeline theo entity.
5. Summary generation phai duoc mo ta la flow 1 LLM call tra ve `title` va
   `content`; khong con dung thresholds `>=50%`/`>=80%`.
6. Backend API va frontend van giu mo hinh serving:
   - Render backend
   - Vercel frontend
   - Supabase PostgreSQL la read database

## Out Of Scope For This Document

Tai lieu nay khong mo ta chi tiet:

- prompt text bang tieng Anh cu the
- retry policy, scheduler policy, va idempotency details

Nhung moi quyet dinh tiep theo phai tuong thich voi architecture trong tai lieu
nay.

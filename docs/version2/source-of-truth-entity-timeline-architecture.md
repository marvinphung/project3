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
- tao short description/title cho timeline item cua entity do
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
- gom cac bai lien quan trong cua so 3 gio
- goi LLM 2 lan de tao summary va short description/title
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
gio gan nhat.

## Content Summary Service Logic

### Step A: Select articles for one entity

Cho mot entity `X`, service se lay:

- tat ca bai bao co chua entity `X`
- trong `news_entities`
- va nam trong time window 3 gio gan nhat

Input thuc te cua buoc tong hop duoc tao tu:

- `news_content.content`
- `news_metadata.published_time` hoac timestamp pipeline phu hop
- entity distribution trong tap bai cua entity `X`

Tat ca bai duoc sap xep theo thu tu moi nhat len truoc.

### Step B: Entity frequency thresholds

Service can tinh tan suat xuat hien entity trong tap bai da chon.

Hai nguong quan trong:

- `>= 50%` so bai
- `>= 80%` so bai

Nhung nguong nay duoc dung cho 2 LLM calls khac nhau.

### Step C: LLM Call 1 - Aggregated News

Input:

- tat ca cleaned content cua cac bai co entity `X`
- thu tu bai moi nhat len truoc
- prompt bang tieng Anh
- danh sach entities xuat hien trong `>= 50%` so bai

Output:

- mot ban `aggregated news`

Y nghia:

- day la ban tong hop thong tin tu tap bai cua entity `X`
- no phai chua va uu tien cac entities xuat hien trong `>= 50%` so bai

### Step D: LLM Call 2 - Short Description / Title

Input:

- aggregated news vua tao
- prompt bang tieng Anh
- danh sach entities xuat hien trong `>= 80%` so bai

Output:

- `short description`

Trong architecture hien tai, `short description` co the duoc xem nhu:

- title
- hoac timeline headline

No phai chua cac entities xuat hien trong `>= 80%` so bai.

### Step E: Persist summary results

Sau 2 LLM calls, service luu:

- aggregated news
- short description/title
- metadata can thiet de gan voi entity va time window

Tai lieu nay chua chot ten collection/table cu the cho summary records.
Dieu do se duoc dinh nghia o docs schema sau.

## Publish Logic

### Initial publish

Lan publish dau tien can tao du lieu timeline cho cac moc:

```text
0h, 3h, 6h, 12h, 15h, 18h, 21h
```

Moi moc se dung:

- time window 3 gio
- du lieu summary/entity timeline tuong ung

Muc tieu la tao bo timeline co san trong PostgreSQL de backend va frontend doc.

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

## Frontend/Product Expectations

Frontend can nhan duoc tu backend API:

- danh sach entities noi bat, sap xep theo muc do xuat hien/noi bat
- timeline rieng cua tung entity
- timeline item da co:
  - title hoac short description
  - aggregated content neu can
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
5. Summary generation phai duoc mo ta la flow 2 LLM calls.
6. Backend API va frontend van giu mo hinh serving:
   - Render backend
   - Vercel frontend
   - Supabase PostgreSQL la read database

## Out Of Scope For This Document

Tai lieu nay chua chot:

- schema cu the cua summary/timeline collections trong Mongo
- schema cu the cua timeline tables trong Supabase
- prompt text bang tieng Anh cu the
- retry policy, scheduler policy, va idempotency details
- exact API contract cho frontend

Nhung moi quyet dinh tiep theo phai tuong thich voi architecture trong tai lieu
nay.

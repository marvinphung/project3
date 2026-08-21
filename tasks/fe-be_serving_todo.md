# FE-BE Serving Todo

## Phase 1: Fix Entity Timeline API

- [x] Task 1: Fix `GET /api/v2/entities/{entity_id}/timeline` SQL binding for timeline item article lookup.
- [x] Task 2: Add regression test for timeline endpoint with at least one linked source article.
- [x] Task 3: Verify entity detail page can load timeline data without browser CORS/network errors.
- [x] Checkpoint: Clicking a top/search entity opens a populated timeline page.

## Phase 2: Complete PostgreSQL Article Read Model

- [x] Task 4: Add required serving fields to `source_articles` or a compatible article read-model table.
- [x] Task 5: Update publisher to copy article title, URL, image, source, timestamps, excerpt/body fields from Mongo into PostgreSQL.
- [x] Task 6: Make schema/bootstrap reproducible instead of relying on manual local PostgreSQL patches.
- [x] Checkpoint: Backend can serve public article lists from PostgreSQL only.

## Phase 3: Add Public Article API

- [x] Task 7: Implement `GET /api/v2/articles?limit=&cursor=` for the latest-news page.
- [x] Task 8: Implement article detail API if frontend routes require opening a news article.
- [x] Task 9: Add API tests covering empty state, populated list, pagination/cursor, and response shape.
- [x] Checkpoint: `/tin-moi` loads real PostgreSQL-backed articles.

## Phase 4: Align Frontend Entity Contract

- [x] Task 10: Update frontend entity models to use backend fields such as `canonical_name`, `entity_type`, `mention_count_24h`, and aliases.
- [x] Task 11: Fix entity directory pages for `/clb`, `/cau-thu`, and `/hlv`.
- [x] Task 12: Ensure entity cards link by stable `entity_id` and do not depend on missing `name` fields.
- [x] Checkpoint: Entity directory pages render data and do not hit React error boundaries.

## Phase 5: Finish Public News UX

- [x] Task 13: Wire latest-news UI to the new article API contract.
- [x] Task 14: Define behavior for "Xem thêm tin" using pagination or remove/disable it intentionally when no next page exists.
- [x] Task 15: Add empty and error states that distinguish "no data" from "API failure".
- [x] Checkpoint: Latest-news page has usable data loading and button behavior.

## Phase 6: Route Hygiene

- [x] Task 16: Decide whether footer/static links need pages or should be removed.
- [x] Task 17: Add minimal routes for required public pages or remove dead navigation links.
- [x] Checkpoint: Visible links either navigate to real pages or are intentionally unavailable.

## Phase 7: Full UI Verification

- [x] Task 18: Rebuild/restart backend API and frontend after implementation.
- [x] Task 19: Run Playwright audit over home, search, entity detail, latest news, and entity directories.
- [x] Task 20: Save audit results and fix any remaining missing-data, broken-button, or frontend crash issues.
- [x] Checkpoint: Frontend connects only to backend API, backend reads only PostgreSQL, and all visible public flows are usable.

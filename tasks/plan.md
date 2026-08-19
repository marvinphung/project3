# FootballPulse V2 Completion Harness

## 0. Harness Metadata

```yaml
project: footballpulse
target: version2-complete
executor: antigravity
workspace: /home/pmv259/Documents/personal-projects/project3
primary_compose: docker-compose.v2.yml
primary_api: services/api-gateway/src/footballpulse_api_gateway/runtime_v2.py
primary_data_flow: crawl -> Mongo -> Kafka -> process -> Kaggle -> Mongo -> PostgreSQL -> API -> frontend
mode: autonomous-implementation
```

## 1. Execution Contract

Antigravity must follow these rules:

1. Execute work items in ID order. Do not skip a failed prerequisite.
2. Before editing, inspect the current file and preserve unrelated user changes.
3. Use `apply_patch` for manual edits.
4. After every work item, run its verification commands.
5. Do not claim a work item complete without command output proving its exit criteria.
6. If a verification fails, stop the current phase, preserve logs, fix the root cause, then rerun the failed verification.
7. Do not introduce mock data, demo data, human review, batch-log tables, or a second scheduler.
8. Do not delete production data or Docker volumes unless a work item explicitly says so and a backup has been verified.
9. Keep Airflow as the only scheduler after Phase 1.
10. Keep PostgreSQL v2 tables in the `public` schema unless this plan is explicitly revised.

## 2. Invariants

These must remain true throughout implementation:

- Mongo stores crawl products and processed/enrichment products.
- PostgreSQL/Supabase stores the public read model.
- Article identity is deterministic from canonical URL.
- Re-running crawl/process/publish is idempotent.
- No human review is required between crawl, process, enrichment, and publish.
- Kafka remains in the pipeline.
- Airflow remains in the pipeline.
- Frontend calls only public API v2.
- Operational logs are not persisted in Mongo or PostgreSQL.

## 3. Baseline Gate

### H-000: Capture Baseline

**Goal:** Record the current working state before structural changes.

**Preconditions:** Docker is available; `.env` exists; no destructive database operation is allowed.

**Implementation:**

- Record `git status --short`.
- Record current Docker service state.
- Inspect Mongo collection names and document counts.
- Inspect PostgreSQL public tables and row counts.
- Verify API health and one public article response.
- Verify current Airflow files and current compose service list.

**Files:** No source edits.

**Verification:**

```bash
docker compose -f docker-compose.v2.yml ps
curl --fail --silent http://127.0.0.1:8000/health
curl --fail --silent 'http://127.0.0.1:8000/api/v2/articles?limit=1'
docker compose -f docker-compose.v2.yml config --quiet
```

**Exit criteria:** Baseline commands pass and their output is recorded in the task report.

**Do not proceed if:** Existing services are unhealthy or database access cannot be verified.

### Phase 0 Test Gate

Run the baseline smoke checks and preserve their output before any edit:

```bash
git status --short
docker compose -f docker-compose.v2.yml config --quiet
docker compose -f docker-compose.v2.yml ps
curl --fail --silent http://127.0.0.1:8000/health
curl --fail --silent 'http://127.0.0.1:8000/api/v2/articles?limit=1'
```

Expected result: the current stack is understood and reproducible. If the API or database is already unhealthy, record that as a pre-existing failure and resolve it before changing scheduler behavior.

## 4. Phase 1: Airflow Scheduler Ownership

### H-101: Map `news-aggregator` Airflow Topology

**Goal:** Reproduce the relevant Airflow execution model from `../news-aggregator` without copying unrelated services.

**Preconditions:** H-000 passed; inspect `../news-aggregator` compose, DAGs, executor, healthchecks, and volume layout.

**Implementation:**

- Document the selected executor and required Airflow services.
- Identify Airflow metadata database requirements.
- Identify how DAG tasks access the local workspace and `.env`.
- Identify retry, timeout, task dependency, and log behavior.

**Files:** `docs/version2/local-development.md`, `docs/version2/proposed-pipeline-flow.md` if needed.

**Verification:** Produce a short mapping table in the implementation report: reference service -> v2 service -> reason.

**Exit criteria:** Executor, services, networking, volumes, and task command strategy are explicit.

**Do not proceed if:** Airflow topology is guessed instead of inspected from `../news-aggregator`.

### H-102: Add Airflow Services To Compose

**Goal:** Make Airflow webserver and scheduler runnable from `docker-compose.v2.yml`.

**Preconditions:** H-101 passed.

**Implementation:**

- Add only the Airflow services required by the selected executor.
- Add Airflow metadata database/schema without mixing it with the public read model.
- Mount `airflow/dags`.
- Add healthchecks and explicit dependency conditions.
- Pass Mongo, Kafka, PostgreSQL, Kaggle, and repository path configuration.
- Keep secrets in environment variables, never in compose literals.

**Files:** `docker-compose.v2.yml`, `.env.example`, `airflow/README.md`, `docs/version2/local-development.md`.

**Verification:**

```bash
docker compose -f docker-compose.v2.yml config --quiet
docker compose -f docker-compose.v2.yml up -d --build
docker compose -f docker-compose.v2.yml ps
```

**Exit criteria:** Airflow webserver and scheduler are healthy; all three v2 DAGs are visible.

**Do not proceed if:** Airflow metadata initialization changes or drops public product tables.

### H-103: Convert Workers To One-Shot Commands

**Goal:** Remove the second scheduler from Docker workers.

**Preconditions:** H-102 passed.

**Implementation:**

- Remove `while true` loops from crawler, processor, and publisher compose commands.
- Make each command process one bounded execution and return a meaningful exit code.
- Remove worker loop interval variables from active runtime configuration.
- Keep retry and timeout ownership in Airflow.
- Update DAG commands to pass explicit limits and environment.

**Files:** `docker-compose.v2.yml`, `airflow/dags/footballpulse_crawl_v2.py`, `airflow/dags/footballpulse_process_v2.py`, `airflow/dags/footballpulse_publish_v2.py`, `.env.example`.

**Verification:**

```bash
rg -n "while true|LOOP_SECONDS" docker-compose.v2.yml .env.example airflow
docker compose -f docker-compose.v2.yml up -d --build
docker compose -f docker-compose.v2.yml ps
```

**Exit criteria:** No active Docker worker loop remains; Airflow task execution starts and stops one worker run.

### H-104: Set DAG Schedules And Dependencies

**Goal:** Make the automatic sequence deterministic.

**Preconditions:** H-103 passed.

**Implementation:**

- Crawl: every 30 minutes.
- Process/enrichment: every 30 minutes, preferably triggered after crawl completion.
- Publish: every 15 minutes, preferably triggered after process completion.
- Set `catchup=False`, `max_active_runs=1`, bounded retries, retry delay, execution timeout.
- Ensure a failed upstream task prevents unsafe downstream publishing.

**Files:** `airflow/dags/footballpulse_crawl_v2.py`, `airflow/dags/footballpulse_process_v2.py`, `airflow/dags/footballpulse_publish_v2.py`.

**Verification:** Trigger each DAG manually and trigger the chained flow. Confirm task order in Airflow.

**Exit criteria:** Airflow is the only scheduler and no overlapping uncontrolled run exists.

### Phase 1 Gate

- [ ] H-101 through H-104 passed.
- [ ] Airflow is healthy.
- [ ] Three v2 DAGs are visible and triggerable.
- [ ] Docker workers are one-shot.
- [ ] No duplicate schedule source remains.

### Phase 1 Test Gate

Run before starting Phase 2:

```bash
docker compose -f docker-compose.v2.yml config --quiet
docker compose -f docker-compose.v2.yml ps
docker compose -f docker-compose.v2.yml exec -T airflow-scheduler airflow dags list
docker compose -f docker-compose.v2.yml exec -T airflow-scheduler airflow dags trigger footballpulse_crawl
```

Expected result: compose is valid, Airflow is healthy, all v2 DAGs are visible, and the crawl DAG creates one bounded run. If any command fails, stop and fix Phase 1.

## 5. Phase 2: Real Kaggle Enrichment

### H-201: Remove `local_skip` Runtime Override

**Goal:** Use Kaggle as the real enrichment provider in production-like local execution.

**Preconditions:** Phase 1 Gate passed; Kaggle credentials are valid and not printed.

**Implementation:**

- Remove `FOOTBALLPULSE_AI_PROVIDER=local_skip` from compose.
- Use configured Kaggle provider by default.
- Validate required Kaggle environment at process start.
- Classify missing credentials as a clear retryable configuration failure.

**Files:** `docker-compose.v2.yml`, `.env.example`, `packages/pipeline/src/footballpulse_pipeline/cli.py`, `packages/pipeline/src/footballpulse_pipeline/v2_enrichment_runtime.py`.

**Verification:**

```bash
docker compose -f docker-compose.v2.yml run --rm processor python -m footballpulse_pipeline process --limit 1
```

Confirm logs identify Kaggle and never expose credentials.

**Exit criteria:** No production-like path uses `local_skip`.

### H-202: Upload Full Pending Dataset And Run Kernel

**Goal:** Send all currently pending articles to one Kaggle dataset/kernel execution.

**Preconditions:** H-201 passed.

**Implementation:**

- Query Mongo for all articles without a terminal valid enrichment.
- Build one manifest and dataset artifact.
- Include article IDs, input hashes, cleaned content, and source metadata required by the kernel.
- Upload dataset.
- Submit configured Kaggle kernel with GPU accelerator.
- Poll with bounded timeout and retry classification.
- Download output artifacts.

**Files:** `packages/pipeline/src/footballpulse_pipeline/v2_enrichment_runtime.py`, `services/ai-content-service/src/footballpulse_ai_content_service/batch/kaggle_cli.py`, `services/ai-content-service/src/footballpulse_ai_content_service/batch/coordinator.py`.

**Verification:** Run one real batch and verify Kaggle dataset, kernel, GPU accelerator, output files, and article count.

**Exit criteria:** The dataset count equals the pending Mongo input count and output is downloaded.

### H-203: Validate And Persist Results

**Goal:** Persist only grounded, schema-valid enrichment results.

**Preconditions:** H-202 passed.

**Implementation:**

- Validate article ID and input hash.
- Validate output schema, summary, event type, claims, evidence, and grounding.
- Upsert valid results into `news_enrichments` with `VALIDATED`.
- Mark retryable failures without creating duplicate documents.
- Never require manual approval.

**Files:** enrichment contracts, result importer, Mongo enrichment repository, focused verification scripts.

**Verification:** Inspect Mongo counts and statuses; inject one invalid result and confirm rejection; rerun the same result.

**Exit criteria:** Valid results are `VALIDATED`; invalid results are rejected/retryable; replay is idempotent.

### Phase 2 Gate

- [ ] Kaggle provider is active.
- [ ] Real GPU kernel execution is proven.
- [ ] All pending inputs are included.
- [ ] Validated results are stored in Mongo.
- [ ] No human review task exists.

### Phase 2 Test Gate

Run one real, non-mock enrichment execution before starting Phase 3:

```bash
docker compose -f docker-compose.v2.yml run --rm processor \
  python -m footballpulse_pipeline process --limit 1
docker compose -f docker-compose.v2.yml exec -T mongodb mongosh \
  --quiet --eval 'db.getSiblingDB("footballpulse_v2").news_enrichments.countDocuments({validation_status:"VALIDATED"})'
```

Expected result: Kaggle execution is visible in logs, the command exits successfully, and at least one validated enrichment exists or the run reports an explicit empty-backlog result. Do not proceed with a silent local fallback.

## 6. Phase 3: Crawl Limits And Deduplication

### H-301: Normalize Candidate And Fetch Limits

**Goal:** Enforce the approved 500-candidate/source rule.

**Preconditions:** Phase 1 Gate passed.

**Implementation:**

- Candidate limit: 500 URLs/source/run.
- Scheduled fetch limit: 100 new articles/source/run.
- Bootstrap fetch limit: 500 new articles/source/run.
- Use the same variable names in `.env`, compose, DAGs, and crawler code.
- Remove conflicting default values.

**Files:** `.env`, `.env.example`, `docker-compose.v2.yml`, `scripts/run-real-crawl.py`, crawler configuration.

**Verification:** Run source with more than 500 candidates and assert the logged/processed candidate count is at most 500.

**Exit criteria:** Runtime configuration and code enforce the same limits.

### H-302: Dedupe Before Fetch

**Goal:** Never refetch a known canonical article.

**Preconditions:** H-301 passed.

**Implementation:**

- Canonicalize URL before Mongo lookup.
- Generate UUID from canonical URL.
- Check existing article before HTTP fetch.
- Ignore tracking query parameters.
- Compare content hash after fetch; only create a new version if content changed.

**Files:** crawler catalog/discovery, `services/crawler-service/src/footballpulse_crawler_service/persistence/mongo_v2.py`, `scripts/run-real-crawl.py`, shared URL identity helper.

**Verification:** Run the same source twice; assert second run makes no article HTTP fetches for existing URLs and document counts do not grow.

**Exit criteria:** Duplicate URL and duplicate tracking variants produce one article identity.

### H-303: Add Mongo Indexes And Atomic Product Writes

**Goal:** Keep deduplication correct under concurrent crawl.

**Preconditions:** H-302 passed.

**Implementation:**

- Add indexes for canonical URL, content hash, and enrichment lookup state.
- Use atomic upsert/update semantics.
- Avoid partial metadata/content writes where possible.
- Ensure retry does not create a second document.

**Files:** Mongo model/index initialization and v2 writer.

**Verification:** Run concurrent same-URL crawl and compare counts before/after.

**Exit criteria:** Concurrent retries preserve one canonical product.

### Phase 3 Gate

- [ ] Each source checks at most 500 candidates.
- [ ] Existing articles are skipped before fetch.
- [ ] Repeated crawl is idempotent.
- [ ] Concurrent duplicate crawl is safe.

### Phase 3 Test Gate

Run the real crawler twice against the same source set:

```bash
docker compose -f docker-compose.v2.yml run --rm crawler \
  python -m footballpulse_pipeline crawl --source "BBC Sport Football" --max-articles 2
docker compose -f docker-compose.v2.yml run --rm crawler \
  python -m footballpulse_pipeline crawl --source "BBC Sport Football" --max-articles 2
```

Expected result: the second run reports existing/duplicate articles and does not create additional Mongo product documents for the same canonical URLs. Also verify the candidate count never exceeds 500.

## 7. Phase 4: Parallelism

### H-401: Parallelize Sources Safely

**Goal:** Crawl independent sources concurrently without uncontrolled load.

**Implementation:** Add per-source concurrency/rate limits, global concurrency cap, independent timeout/retry, and source-level failure isolation.

**Verification:** Use two slow sources and prove overlapping execution; fail one source and prove the other completes.

**Exit criteria:** Source parallelism is observable and bounded.

### H-402: Parallelize Kafka Processing

**Goal:** Scale entity processing with Kafka consumer groups.

**Implementation:** Partition by article ID, commit offset only after Mongo persistence, support multiple processor workers, and make writes idempotent.

**Verification:** Start multiple workers, process a backlog, restart one worker, and verify no lost/duplicated final result.

**Exit criteria:** Work is distributed and recoverable.

### H-403: Preserve Full Backlog Semantics For Kaggle

**Goal:** One enrichment execution sees all pending work intended for that run.

**Implementation:** Atomic pending selection/lease, complete manifest count, retry only incomplete/retryable IDs, no accidental truncation by worker limit.

**Verification:** Create a backlog larger than the default process limit and verify selection behavior against the configured run policy.

**Exit criteria:** No pending article is silently omitted.

### Phase 4 Gate

- [ ] Sources overlap safely.
- [ ] Multiple Kafka workers process correctly.
- [ ] Full intended backlog reaches Kaggle.
- [ ] Restart/retry produces no loss or duplicate.

### Phase 4 Test Gate

Run the bounded concurrency smoke flow:

```bash
docker compose -f docker-compose.v2.yml up -d --scale processor=2
docker compose -f docker-compose.v2.yml ps
docker compose -f docker-compose.v2.yml logs --tail=200 processor
```

Expected result: two processor workers share the Kafka backlog, no article receives conflicting final results, and a worker restart does not lose messages. Stop the scaled workers before continuing if the local environment cannot support the configured concurrency.

## 8. Phase 5: PostgreSQL Schema/API Convergence

### H-501: Make `public` The Single V2 Schema

**Goal:** Remove schema drift between migration, publisher, repositories, and API.

**Implementation:**

- Keep v2 read model tables in `public`.
- Update v2 repositories to use `public`.
- Remove or isolate old editorial/source/intelligence schema repositories not used by v2.
- Do not drop live tables before backup and dependency scan.

**Files:** `supabase/migrations/202608180001_v2_product_schema.sql`, publisher, API repositories, admin repositories as needed.

**Verification:** Create a clean PostgreSQL database and run all migrations; query every public v2 endpoint.

**Exit criteria:** No v2 runtime path queries a missing schema.

### H-502: Align Columns, Constraints, And Indexes

**Goal:** Make all writers/readers use one exact contract.

**Implementation:**

- Align `publications`, `articles`, `sources`, `stories`, entities, and timeline columns.
- Add required unique/foreign-key constraints.
- Add indexes for slug, published time, story, source, and entity filters.
- Add identity/admin migration only if those endpoints remain active.

**Verification:** Publisher insert, API list/detail/source/timeline/entity queries, and `EXPLAIN` for paginated queries.

**Exit criteria:** Clean migration, publisher, admin/public API all agree.

### Phase 5 Gate

- [ ] Clean database migration passes.
- [ ] Publisher writes successfully.
- [ ] Public API reads successfully.
- [ ] No `relation does not exist` errors.
- [ ] Pagination and indexes are verified.

### Phase 5 Test Gate

Run schema and API verification against the active local database:

```bash
docker compose -f docker-compose.v2.yml exec -T postgres psql \
  -U footballpulse -d footballpulse_v2 \
  -c '\dt public.*' \
  -c 'select count(*) from public.publications;'
curl --fail --silent http://127.0.0.1:8000/health
curl --fail --silent 'http://127.0.0.1:8000/api/v2/articles?limit=2'
```

Expected result: all required public tables exist, publisher rows are readable, and the API returns schema-valid JSON. Run this against a clean database as a separate migration check before marking the phase complete.

## 9. Phase 6: Publisher Idempotency

### H-601: Atomic Enrichment Claim

**Goal:** Prevent concurrent publishers from processing the same article.

**Implementation:** Add `READY`, `PUBLISHING`, `PUBLISHED`, `PUBLISH_FAILED` state; atomic claim; lease timeout; recovery of expired claims.

**Verification:** Run two publishers against the same article and kill one during publish.

**Exit criteria:** One final publication and recoverable state.

### H-602: Transactional PostgreSQL Publish

**Goal:** Make Mongo-to-PostgreSQL publication safe across crashes.

**Implementation:** PostgreSQL transaction, unique publication identity/slug, `ON CONFLICT`, mark Mongo published only after commit, safe replay after Mongo update failure.

**Verification:** Repeat publish, kill between commit and Mongo update, restart, and verify one publication.

**Exit criteria:** Publish is idempotent and recoverable.

### Phase 6 Test Gate

Publish the same validated article twice and compare PostgreSQL counts:

```bash
docker compose -f docker-compose.v2.yml run --rm publisher \
  python -m footballpulse_pipeline publish --limit 1
docker compose -f docker-compose.v2.yml run --rm publisher \
  python -m footballpulse_pipeline publish --limit 1
docker compose -f docker-compose.v2.yml exec -T postgres psql \
  -U footballpulse -d footballpulse_v2 \
  -c 'select slug, count(*) from public.publications group by slug having count(*) > 1;'
```

Expected result: the second run is a no-op for the already published article and the duplicate query returns zero rows. Also perform one controlled publisher restart during execution.

## 10. Phase 7: Deployment And Security

### H-701: Render Backend

- Start command uses `runtime_v2`.
- Supabase IPv4 pooler configuration is explicit.
- Health check passes before traffic.
- CORS allows only configured Vercel origins.

### H-702: Vercel Frontend

- Frontend uses only `/api/v2`.
- `VITE_API_BASE_URL` is environment-specific.
- Production build passes.
- Loading, empty, error, and API failure states are visible.

### H-703: Secrets And Logs

- `.env` is not tracked.
- Rotate any credential that was exposed.
- Never print passwords, tokens, or connection strings.
- Render/Vercel secrets are configured in platform environment variables.

**Verification:** `git ls-files .env`, production build, secret-pattern scan, CORS request, and health checks.

### Phase 7 Test Gate

Run deployment and security checks before the final E2E phase:

```bash
git ls-files .env
docker compose -f docker-compose.v2.yml config --quiet
curl --fail --silent http://127.0.0.1:8000/health
```

Expected result: `.env` is not tracked, compose remains valid, health is green, frontend production build passes, and logs contain no credentials.

## 11. Final E2E Harness

### H-801: Execute Full Flow

Run in this exact order:

1. Start Docker infrastructure and Airflow.
2. Verify Mongo replica set.
3. Verify Kafka broker and topics.
4. Verify PostgreSQL migrations and indexes.
5. Trigger crawl DAG.
6. Verify new Mongo article documents.
7. Verify Kafka `news.crawled.v1` events.
8. Trigger process DAG.
9. Verify real Kaggle GPU execution.
10. Verify `news_enrichments.validation_status=VALIDATED`.
11. Trigger publish DAG.
12. Verify PostgreSQL publication.
13. Call `/health`, article list, article detail, source, timeline, and entity endpoints.
14. Verify frontend displays the new article.
15. Repeat the full flow and compare counts for idempotency.
16. Run outage checks: Kafka unavailable, Kaggle timeout, PostgreSQL unavailable, duplicate crawl, publisher restart.

**Final exit criteria:**

- [ ] Airflow is the only scheduler.
- [ ] No worker loop runs outside Airflow.
- [ ] Real Kaggle enrichment succeeds.
- [ ] Crawl checks 500 candidates/source and skips known URLs.
- [ ] Parallel crawl/process works with bounded concurrency.
- [ ] Mongo/PostgreSQL contracts are aligned.
- [ ] Publisher is idempotent and recoverable.
- [ ] Local, Render, and Vercel deployment paths are documented and verified.
- [ ] Full E2E flow passes twice without duplicate products/publications.

## 12. Stop Conditions

Stop and report instead of guessing when:

- `../news-aggregator` uses an executor or topology incompatible with the current environment.
- Kaggle credentials or kernel/dataset ownership is unavailable.
- A schema migration would require destructive data loss.
- Existing user changes conflict with a required edit.
- A failure repeats three times without a new diagnostic signal.

When stopping, report: work item ID, exact command, relevant error, preserved state, and the smallest decision needed to continue.

# Implementation Plan: FootballPulse

Current canonical refactor plan:
[`docs/version2/refactor-implementation-plan.md`](../docs/version2/refactor-implementation-plan.md).

Current architecture decision:
[`docs/version2/adr-0001-version2-local-pipeline-supabase-serving.md`](../docs/version2/adr-0001-version2-local-pipeline-supabase-serving.md).

## Execution contract

For the current refactor flow, the user explicitly authorized autonomous
implementation and verification on August 17, 2026:

1. Execute one completion task at a time in dependency order.
2. Run focused tests, Docker smoke and proportional broader verification.
3. Report concise checkpoints, but continue without waiting for approval.
4. Stop only for missing credentials/artifacts, an irreversible action, or a
   decision that materially changes the approved MVP scope.
5. Do not mark the MVP complete until the final Docker/E2E verification passes.

## Phase order

1. Foundation schema, shared identity, and Mongo/Supabase models.
2. Local pipeline: crawler, processor, enrichment, publisher.
3. Public/backend split: Render API + Vercel frontend + Supabase read model.
4. Legacy removal: runtime, public API v1, compose v1, docs v1.
5. Final production hardening and deployment cleanup.

## Current next action

Hoan tat cleanup cac tai lieu/task con tro vao ke hoach V1 da xoa, sau do tiep
tuc hardening va deployment docs cho V2.

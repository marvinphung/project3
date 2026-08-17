from __future__ import annotations

import logging
from datetime import UTC, datetime
from secrets import compare_digest
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException
from footballpulse_runtime_config import RequestLoggingMiddleware
from pydantic import BaseModel, Field

from footballpulse_ai_content_service.contracts.batch import BatchRecord
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput
from footballpulse_ai_content_service.providers.base import EnrichmentProvider

LOGGER = logging.getLogger("footballpulse.ai.http")


class EnrichmentBatchRequest(BaseModel):
    collection_batch_ids: list[str] = Field(min_length=1, max_length=100)
    window_started_at: datetime


class EnrichmentBatchResponse(BaseModel):
    id: UUID
    status: str
    collection_batch_ids: list[str]
    created_at: datetime
    success_count: int = 0
    error_count: int = 0
    results: list[BatchRecord] = Field(default_factory=list)


class EnrichmentBatchCompleteRequest(BaseModel):
    status: str = Field(pattern=r"^(COMPLETED|PARTIAL|FAILED_RETRYABLE|FAILED_TERMINAL)$")
    success_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)


class EnrichmentBatchStartRequest(BaseModel):
    articles: list[ArticleEnrichmentInput] = Field(default_factory=list, max_length=100)


class EnrichmentBatchRegistry:
    def __init__(self, provider: EnrichmentProvider | None = None) -> None:
        self._batches: dict[UUID, EnrichmentBatchResponse] = {}
        self._provider = provider

    def create(self, request: EnrichmentBatchRequest) -> EnrichmentBatchResponse:
        batch = EnrichmentBatchResponse(
            id=uuid4(),
            status="PREPARING",
            collection_batch_ids=request.collection_batch_ids,
            created_at=datetime.now(UTC),
        )
        self._batches[batch.id] = batch
        return batch

    def get(self, batch_id: UUID) -> EnrichmentBatchResponse | None:
        return self._batches.get(batch_id)

    def list_batches(self, *, limit: int = 100) -> list[EnrichmentBatchResponse]:
        return list(self._batches.values())[-limit:][::-1]

    def retry(self, batch_id: UUID) -> EnrichmentBatchResponse | None:
        current = self._batches.get(batch_id)
        if current is None:
            return None
        if current.status not in {"FAILED_RETRYABLE", "PARTIAL"}:
            return current
        current = current.model_copy(
            update={"status": "PREPARING", "success_count": 0, "error_count": 0, "results": []}
        )
        self._batches[batch_id] = current
        return current

    def start(
        self, batch_id: UUID, articles: list[ArticleEnrichmentInput] | None = None
    ) -> EnrichmentBatchResponse | None:
        current = self._batches.get(batch_id)
        if current is None:
            return None
        if current.status == "PREPARING":
            current = current.model_copy(update={"status": "RUNNING"})
            self._batches[batch_id] = current
            if articles and self._provider is not None:
                try:
                    records = list(self._provider.enrich(tuple(articles)))
                    success_count = sum(record.status == "SUCCESS" for record in records)
                    current = current.model_copy(
                        update={
                            "status": "COMPLETED" if success_count == len(records) else "PARTIAL",
                            "success_count": success_count,
                            "error_count": len(records) - success_count,
                            "results": records,
                        }
                    )
                except Exception:
                    current = current.model_copy(
                        update={
                            "status": "FAILED_RETRYABLE",
                            "error_count": len(articles),
                            "results": [],
                        }
                    )
                self._batches[batch_id] = current
        return current

    def complete(
        self, batch_id: UUID, status: str, success_count: int, error_count: int
    ) -> EnrichmentBatchResponse | None:
        current = self._batches.get(batch_id)
        if current is None:
            return None
        if current.status in {"RUNNING", "PREPARING"}:
            current = current.model_copy(
                update={
                    "status": status,
                    "success_count": success_count,
                    "error_count": error_count,
                }
            )
            self._batches[batch_id] = current
        return current


def create_app(
    *,
    internal_token: str,
    registry: EnrichmentBatchRegistry | None = None,
    provider: EnrichmentProvider | None = None,
) -> FastAPI:
    app = FastAPI(title="FootballPulse AI Content Service", version="0.1.0")
    batches = registry or EnrichmentBatchRegistry(provider=provider)

    app.add_middleware(RequestLoggingMiddleware, logger=LOGGER)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"service": "ai-content-service", "status": "ok"}

    @app.post(
        "/internal/v1/enrichment-batches",
        status_code=202,
        response_model=EnrichmentBatchResponse,
    )
    async def create_enrichment_batch(
        request: EnrichmentBatchRequest, authorization: str | None = Header(default=None)
    ) -> EnrichmentBatchResponse:
        if (
            authorization is None
            or not authorization.startswith("Bearer ")
            or not compare_digest(authorization[7:], internal_token)
        ):
            raise HTTPException(status_code=401, detail="invalid bearer token")
        return batches.create(request)

    @app.get(
        "/internal/v1/enrichment-batches/{batch_id}",
        response_model=EnrichmentBatchResponse,
    )
    async def get_enrichment_batch(
        batch_id: UUID, authorization: str | None = Header(default=None)
    ) -> EnrichmentBatchResponse:
        if (
            authorization is None
            or not authorization.startswith("Bearer ")
            or not compare_digest(authorization[7:], internal_token)
        ):
            raise HTTPException(status_code=401, detail="invalid bearer token")
        batch = batches.get(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="enrichment batch not found")
        return batch

    @app.get(
        "/internal/v1/enrichment-batches",
        response_model=list[EnrichmentBatchResponse],
    )
    async def list_enrichment_batches(
        limit: int = 100, authorization: str | None = Header(default=None)
    ) -> list[EnrichmentBatchResponse]:
        if (
            authorization is None
            or not authorization.startswith("Bearer ")
            or not compare_digest(authorization[7:], internal_token)
        ):
            raise HTTPException(status_code=401, detail="invalid bearer token")
        if not 1 <= limit <= 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        return batches.list_batches(limit=limit)

    @app.post(
        "/internal/v1/enrichment-batches/{batch_id}/start",
        response_model=EnrichmentBatchResponse,
    )
    async def start_enrichment_batch(
        batch_id: UUID,
        request: EnrichmentBatchStartRequest | None = None,
        authorization: str | None = Header(default=None),
    ) -> EnrichmentBatchResponse:
        if (
            authorization is None
            or not authorization.startswith("Bearer ")
            or not compare_digest(authorization[7:], internal_token)
        ):
            raise HTTPException(status_code=401, detail="invalid bearer token")
        batch = batches.start(batch_id, request.articles if request else None)
        if batch is None:
            raise HTTPException(status_code=404, detail="enrichment batch not found")
        return batch

    @app.post(
        "/internal/v1/enrichment-batches/{batch_id}/retry",
        response_model=EnrichmentBatchResponse,
    )
    async def retry_enrichment_batch(
        batch_id: UUID, authorization: str | None = Header(default=None)
    ) -> EnrichmentBatchResponse:
        if (
            authorization is None
            or not authorization.startswith("Bearer ")
            or not compare_digest(authorization[7:], internal_token)
        ):
            raise HTTPException(status_code=401, detail="invalid bearer token")
        batch = batches.retry(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="enrichment batch not found")
        return batch

    @app.post(
        "/internal/v1/enrichment-batches/{batch_id}/complete",
        response_model=EnrichmentBatchResponse,
    )
    async def complete_enrichment_batch(
        batch_id: UUID,
        request: EnrichmentBatchCompleteRequest,
        authorization: str | None = Header(default=None),
    ) -> EnrichmentBatchResponse:
        if (
            authorization is None
            or not authorization.startswith("Bearer ")
            or not compare_digest(authorization[7:], internal_token)
        ):
            raise HTTPException(status_code=401, detail="invalid bearer token")
        batch = batches.complete(
            batch_id, request.status, request.success_count, request.error_count
        )
        if batch is None:
            raise HTTPException(status_code=404, detail="enrichment batch not found")
        return batch

    return app

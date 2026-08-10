from __future__ import annotations

from datetime import UTC, datetime
from secrets import compare_digest
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


class EnrichmentBatchRequest(BaseModel):
    collection_batch_ids: list[str] = Field(min_length=1, max_length=100)
    window_started_at: datetime


class EnrichmentBatchResponse(BaseModel):
    id: UUID
    status: str
    collection_batch_ids: list[str]
    created_at: datetime


class EnrichmentBatchRegistry:
    def __init__(self) -> None:
        self._batches: dict[UUID, EnrichmentBatchResponse] = {}

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

    def start(self, batch_id: UUID) -> EnrichmentBatchResponse | None:
        current = self._batches.get(batch_id)
        if current is None:
            return None
        if current.status == "PREPARING":
            current = current.model_copy(update={"status": "RUNNING"})
            self._batches[batch_id] = current
        return current


def create_app(*, internal_token: str, registry: EnrichmentBatchRegistry | None = None) -> FastAPI:
    app = FastAPI(title="FootballPulse AI Content Service", version="0.1.0")
    batches = registry or EnrichmentBatchRegistry()

    @app.post(
        "/internal/v1/enrichment-batches",
        status_code=202,
        response_model=EnrichmentBatchResponse,
    )
    async def create_enrichment_batch(
        request: EnrichmentBatchRequest, authorization: str | None = Header(default=None)
    ) -> EnrichmentBatchResponse:
        if authorization is None or not authorization.startswith("Bearer ") or not compare_digest(
            authorization[7:], internal_token
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
        if authorization is None or not authorization.startswith("Bearer ") or not compare_digest(
            authorization[7:], internal_token
        ):
            raise HTTPException(status_code=401, detail="invalid bearer token")
        batch = batches.get(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="enrichment batch not found")
        return batch

    @app.post(
        "/internal/v1/enrichment-batches/{batch_id}/start",
        response_model=EnrichmentBatchResponse,
    )
    async def start_enrichment_batch(
        batch_id: UUID, authorization: str | None = Header(default=None)
    ) -> EnrichmentBatchResponse:
        if authorization is None or not authorization.startswith("Bearer ") or not compare_digest(
            authorization[7:], internal_token
        ):
            raise HTTPException(status_code=401, detail="invalid bearer token")
        batch = batches.start(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="enrichment batch not found")
        return batch

    return app

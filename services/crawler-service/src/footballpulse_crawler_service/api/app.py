from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from secrets import compare_digest
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime
from starlette.exceptions import HTTPException as StarletteHTTPException

from footballpulse_crawler_service.api.schemas import (
    CrawlBatchCompleteRequest,
    CrawlBatchOpenRequest,
    CrawlBatchResponse,
    CrawlTriggerRequest,
    ErrorBody,
    ErrorEnvelope,
    SourceConfigurationRequest,
    SourceListResponse,
    SourceResponse,
    SourceToggleRequest,
    SourceUpdateRequest,
)
from footballpulse_crawler_service.application.source_service import (
    CrawlBatchService,
    SourceService,
)
from footballpulse_crawler_service.domain.errors import (
    DomainValidationError,
    SourceConflictError,
    SourceNotFoundError,
)
from footballpulse_crawler_service.health import liveness

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
}
BEARER_SCHEME = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    pass


def error_response(
    status_code: int, code: str, message: str, details: list[dict[str, object]] | None = None
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, details=[] if details is None else details)
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


def bearer_dependency(expected_token: str) -> Callable[..., None]:
    def authorize(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER_SCHEME)],
    ) -> None:
        if credentials is None or not compare_digest(credentials.credentials, expected_token):
            raise AuthenticationError

    return authorize


def create_app(
    *,
    source_service: SourceService,
    batch_service: CrawlBatchService,
    admin_token: str,
    internal_token: str,
) -> FastAPI:
    app = FastAPI(title="FootballPulse Crawler Service", version="0.1.0")
    admin_auth = bearer_dependency(admin_token)
    internal_auth = bearer_dependency(internal_token)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return liveness()

    @app.exception_handler(AuthenticationError)
    async def authentication_handler(_: Request, __: AuthenticationError) -> JSONResponse:
        return error_response(401, "UNAUTHORIZED", "invalid bearer token")

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = jsonable_encoder(exc.errors())
        return error_response(
            422, "REQUEST_VALIDATION_FAILED", "request validation failed", details
        )

    @app.exception_handler(DomainValidationError)
    async def domain_validation_handler(_: Request, exc: DomainValidationError) -> JSONResponse:
        return error_response(422, "DOMAIN_VALIDATION_FAILED", str(exc))

    @app.exception_handler(SourceNotFoundError)
    async def not_found_handler(_: Request, exc: SourceNotFoundError) -> JSONResponse:
        return error_response(404, "SOURCE_NOT_FOUND", str(exc))

    @app.exception_handler(SourceConflictError)
    async def conflict_handler(_: Request, exc: SourceConflictError) -> JSONResponse:
        return error_response(409, "SOURCE_CONFLICT", str(exc))

    @app.post(
        "/admin/v1/sources",
        status_code=201,
        response_model=SourceResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(admin_auth)],
    )
    def create_source(request: SourceConfigurationRequest) -> SourceResponse:
        return SourceResponse.from_domain(source_service.create(request.to_domain()))

    @app.get(
        "/admin/v1/sources",
        response_model=SourceListResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(admin_auth)],
    )
    def list_sources(
        limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)
    ) -> SourceListResponse:
        return SourceListResponse(
            items=[
                SourceResponse.from_domain(source)
                for source in source_service.list_sources(limit=limit, offset=offset)
            ]
        )

    @app.patch(
        "/admin/v1/sources/{source_id}",
        response_model=SourceResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(admin_auth)],
    )
    def update_source(source_id: UUID, request: SourceUpdateRequest) -> SourceResponse:
        return SourceResponse.from_domain(
            source_service.update(
                source_id,
                request.to_domain(),
                expected_version=request.expected_version,
            )
        )

    @app.post(
        "/admin/v1/sources/{source_id}/toggle",
        response_model=SourceResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(admin_auth)],
    )
    def toggle_source(source_id: UUID, request: SourceToggleRequest) -> SourceResponse:
        return SourceResponse.from_domain(
            source_service.toggle(
                source_id,
                enabled=request.enabled,
                expected_version=request.expected_version,
            )
        )

    @app.post(
        "/admin/v1/sources/{source_id}/crawl",
        status_code=201,
        response_model=CrawlBatchResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(admin_auth)],
    )
    def trigger_crawl(source_id: UUID, request: CrawlTriggerRequest) -> CrawlBatchResponse:
        return CrawlBatchResponse.from_domain(
            batch_service.open(
                source_id=source_id,
                idempotency_key=request.idempotency_key,
                window_started_at=datetime.now(UTC),
            )
        )

    @app.get(
        "/admin/v1/crawl-batches/{batch_id}",
        response_model=CrawlBatchResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(admin_auth)],
    )
    def get_crawl_batch(batch_id: UUID) -> CrawlBatchResponse:
        batch = batch_service.get(batch_id)
        return CrawlBatchResponse.from_domain(batch)

    @app.get(
        "/internal/v1/sources/due",
        response_model=SourceListResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(internal_auth)],
    )
    def due_sources(
        at: Annotated[AwareDatetime, Query()], limit: int = Query(100, ge=1, le=200)
    ) -> SourceListResponse:
        return SourceListResponse(
            items=[
                SourceResponse.from_domain(source)
                for source in source_service.due(at=at, limit=limit)
            ]
        )

    @app.post(
        "/internal/v1/crawl-batches",
        status_code=201,
        response_model=CrawlBatchResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(internal_auth)],
    )
    def open_batch(request: CrawlBatchOpenRequest) -> CrawlBatchResponse:
        return CrawlBatchResponse.from_domain(
            batch_service.open(
                source_id=request.source_id,
                idempotency_key=request.idempotency_key,
                window_started_at=request.window_started_at,
            )
        )

    @app.post(
        "/internal/v1/crawl-batches/{batch_id}/complete",
        response_model=CrawlBatchResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(internal_auth)],
    )
    def complete_batch(batch_id: UUID, request: CrawlBatchCompleteRequest) -> CrawlBatchResponse:
        return CrawlBatchResponse.from_domain(
            batch_service.complete(
                batch_id,
                status=request.status,
                discovered_count=request.discovered_count,
                fetched_count=request.fetched_count,
                failed_count=request.failed_count,
            )
        )

    return app

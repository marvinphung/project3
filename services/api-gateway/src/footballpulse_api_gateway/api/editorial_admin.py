from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from secrets import compare_digest
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from footballpulse_content_service.editorial.publication import PublicationConflictError
from footballpulse_content_service.editorial.repository import RevisionConflictError
from pydantic import BaseModel

from footballpulse_api_gateway.auth import Role, TokenService


@dataclass(frozen=True, slots=True)
class EditorialRevisionView:
    generated_article_id: UUID
    revision_id: UUID
    revision_number: int
    story_version: int
    state: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class EditorialRevisionDetailView(EditorialRevisionView):
    story_id: UUID
    title_en: str
    body_en: str
    title_vi: str
    body_vi: str


@dataclass(frozen=True, slots=True)
class PublicationView:
    id: UUID
    generated_article_id: UUID
    revision_id: UUID
    story_id: UUID
    story_version: int
    slug: str
    title_vi: str
    body_vi: str
    published_at: datetime


@dataclass(frozen=True, slots=True)
class SourceArticleView:
    id: str
    title: str
    source_url: str
    collected_at: datetime
    extraction_status: str
    duplicate_type: str


@dataclass(frozen=True, slots=True)
class SourceArticlePage:
    items: tuple[SourceArticleView, ...]
    total: int


@dataclass(frozen=True, slots=True)
class OperationsSummaryView:
    source_articles_total: int
    source_articles_today: int
    enrichments_validated: int
    enrichments_needs_content_review: int
    revisions_by_state: dict[str, int]
    publications_total: int


@dataclass(frozen=True, slots=True)
class AdminStoryView:
    id: UUID
    event_type: str
    status: str
    confidence_score: float
    version: int
    last_seen_at: datetime
    source_count: int


@dataclass(frozen=True, slots=True)
class AdminPublicationView:
    id: UUID
    slug: str
    title_vi: str
    story_id: UUID
    published_at: datetime


@dataclass(frozen=True, slots=True)
class ProcessingFailureView:
    id: str
    stage: str
    status: str
    message: str
    attempts: int
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class EditorialRevisionPage:
    items: tuple[EditorialRevisionDetailView, ...]
    total: int


class EditorialAdminService(Protocol):
    def list_revisions_page(
        self, *, limit: int, offset: int, state: str | None
    ) -> tuple[list[EditorialRevisionDetailView], int]: ...

    def get_revision(self, article_id: UUID) -> EditorialRevisionDetailView: ...

    def update_content(
        self,
        article_id: UUID,
        *,
        expected_revision_number: int,
        title_vi: str,
        body_vi: str,
        now: datetime,
    ) -> EditorialRevisionDetailView: ...
    def submit_for_review(
        self, article_id: UUID, *, expected_revision_number: int, now: datetime
    ) -> EditorialRevisionView: ...

    def approve(
        self, article_id: UUID, *, expected_revision_number: int, now: datetime
    ) -> EditorialRevisionView: ...

    def reject(
        self, article_id: UUID, *, expected_revision_number: int, now: datetime
    ) -> EditorialRevisionView: ...

    def publish(
        self, article_id: UUID, *, slug: str, idempotency_key: str, now: datetime
    ) -> PublicationView: ...


class SourceArticleReadRepository(Protocol):
    def list_source_articles(
        self, *, limit: int, offset: int, query: str | None
    ) -> SourceArticlePage: ...


class OperationsReadRepository(Protocol):
    def summary(self) -> OperationsSummaryView: ...


class AdminStoryReadRepository(Protocol):
    def list_stories(self, *, limit: int, offset: int, status: str | None) -> tuple[list[AdminStoryView], int]: ...


class AdminPublicationReadRepository(Protocol):
    def list_publications(self, *, limit: int, offset: int) -> tuple[list[AdminPublicationView], int]: ...


class ProcessingFailureReadRepository(Protocol):
    def list_failures(self, *, limit: int, offset: int) -> tuple[list[ProcessingFailureView], int]: ...


class RevisionTransitionRequest(BaseModel):
    expected_revision_number: int


class RevisionContentRequest(RevisionTransitionRequest):
    title_vi: str
    body_vi: str


class PublishRequest(BaseModel):
    slug: str
    idempotency_key: str


class EditorialRevisionResponse(BaseModel):
    generated_article_id: UUID
    revision_id: UUID
    revision_number: int
    story_version: int
    state: str
    updated_at: datetime


class EditorialRevisionDetailResponse(EditorialRevisionResponse):
    story_id: UUID
    title_en: str
    body_en: str
    title_vi: str
    body_vi: str


class EditorialRevisionListResponse(BaseModel):
    items: list[EditorialRevisionDetailResponse]
    total: int
    limit: int
    offset: int
    next_offset: int | None


class PublicationResponse(BaseModel):
    id: UUID
    generated_article_id: UUID
    revision_id: UUID
    story_id: UUID
    story_version: int
    slug: str
    title_vi: str
    body_vi: str
    published_at: datetime


class SourceArticleResponse(BaseModel):
    id: str
    title: str
    source_url: str
    collected_at: datetime
    extraction_status: str
    duplicate_type: str


class SourceArticleListResponse(BaseModel):
    items: list[SourceArticleResponse]
    total: int
    limit: int
    offset: int
    next_offset: int | None


class OperationsSummaryResponse(BaseModel):
    source_articles_total: int
    source_articles_today: int
    enrichments_validated: int
    enrichments_needs_content_review: int
    revisions_by_state: dict[str, int]
    publications_total: int


class AdminStoryResponse(BaseModel):
    id: UUID
    event_type: str
    status: str
    confidence_score: float
    version: int
    last_seen_at: datetime
    source_count: int


class AdminStoryListResponse(BaseModel):
    items: list[AdminStoryResponse]
    total: int
    limit: int
    offset: int
    next_offset: int | None


class AdminPublicationResponse(BaseModel):
    id: UUID
    slug: str
    title_vi: str
    story_id: UUID
    published_at: datetime


class AdminPublicationListResponse(BaseModel):
    items: list[AdminPublicationResponse]
    total: int
    limit: int
    offset: int
    next_offset: int | None


class ProcessingFailureResponse(BaseModel):
    id: str
    stage: str
    status: str
    message: str
    attempts: int
    occurred_at: datetime


class ProcessingFailureListResponse(BaseModel):
    items: list[ProcessingFailureResponse]
    total: int
    limit: int
    offset: int
    next_offset: int | None


BEARER_SCHEME = HTTPBearer(auto_error=False)


class ForbiddenError(Exception):
    pass


def create_editorial_admin_app(
    service: EditorialAdminService,
    *,
    admin_token: str,
    editor_token: str | None = None,
    token_service: TokenService | None = None,
    source_article_repository: SourceArticleReadRepository | None = None,
    operations_repository: OperationsReadRepository | None = None,
    story_repository: AdminStoryReadRepository | None = None,
    publication_repository: AdminPublicationReadRepository | None = None,
    failure_repository: ProcessingFailureReadRepository | None = None,
) -> FastAPI:
    app = FastAPI(title="FootballPulse Editorial Admin API", version="0.1.0")

    async def authorize_editor(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER_SCHEME)],
    ) -> None:
        if credentials is None:
            raise PermissionError
        if compare_digest(credentials.credentials, admin_token):
            return
        if editor_token is not None and compare_digest(credentials.credentials, editor_token):
            return
        if token_service is None:
            raise PermissionError
        try:
            token_service.decode(credentials.credentials)
        except ValueError as error:
            raise PermissionError from error

    async def authorize_admin(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER_SCHEME)],
    ) -> None:
        if credentials is None:
            raise PermissionError
        if compare_digest(credentials.credentials, admin_token):
            return
        if editor_token is not None and compare_digest(credentials.credentials, editor_token):
            raise ForbiddenError
        if token_service is None:
            raise PermissionError
        try:
            claims = token_service.decode(credentials.credentials)
        except ValueError as error:
            raise PermissionError from error
        if claims.role is not Role.ADMIN:
            raise ForbiddenError

    @app.exception_handler(PermissionError)
    async def permission_error_handler(_: Request, __: PermissionError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "UNAUTHORIZED", "message": "invalid bearer token"}},
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_error_handler(_: Request, __: ForbiddenError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "FORBIDDEN", "message": "insufficient role"}},
        )

    @app.exception_handler(RevisionConflictError)
    async def revision_conflict_handler(_: Request, exc: RevisionConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "EDITORIAL_CONFLICT", "message": str(exc)}},
        )

    @app.exception_handler(PublicationConflictError)
    async def publication_conflict_handler(
        _: Request, exc: PublicationConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "PUBLICATION_CONFLICT", "message": str(exc)}},
        )

    @app.exception_handler(ValueError)
    async def validation_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "DOMAIN_VALIDATION_FAILED", "message": str(exc)}},
        )

    def response(view: EditorialRevisionView) -> EditorialRevisionResponse:
        return EditorialRevisionResponse.model_validate(view, from_attributes=True)

    def detail_response(view: EditorialRevisionDetailView) -> EditorialRevisionDetailResponse:
        return EditorialRevisionDetailResponse.model_validate(view, from_attributes=True)

    def publication_response(view: PublicationView) -> PublicationResponse:
        return PublicationResponse.model_validate(view, from_attributes=True)

    def source_article_response(view: SourceArticleView) -> SourceArticleResponse:
        return SourceArticleResponse.model_validate(view, from_attributes=True)

    def operations_summary_response(view: OperationsSummaryView) -> OperationsSummaryResponse:
        return OperationsSummaryResponse.model_validate(view, from_attributes=True)

    def story_response(view: AdminStoryView) -> AdminStoryResponse:
        return AdminStoryResponse.model_validate(view, from_attributes=True)

    def admin_publication_response(view: AdminPublicationView) -> AdminPublicationResponse:
        return AdminPublicationResponse.model_validate(view, from_attributes=True)

    def failure_response(view: ProcessingFailureView) -> ProcessingFailureResponse:
        return ProcessingFailureResponse.model_validate(view, from_attributes=True)

    @app.get(
        "/admin/v1/editorial/revisions",
        response_model=EditorialRevisionListResponse,
        dependencies=[Depends(authorize_editor)],
    )
    async def list_revisions(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        state: str | None = Query(None),
    ) -> EditorialRevisionListResponse:
        if state is not None and state not in {"DRAFT", "NEEDS_REVIEW", "APPROVED", "REJECTED", "STALE"}:
            raise ValueError("unknown editorial revision state")
        items, total = service.list_revisions_page(limit=limit, offset=offset, state=state)
        next_offset = offset + len(items)
        return EditorialRevisionListResponse(
            items=[detail_response(item) for item in items], total=total,
            limit=limit, offset=offset, next_offset=next_offset if next_offset < total else None,
        )

    @app.get(
        "/admin/v1/source-articles",
        response_model=SourceArticleListResponse,
        dependencies=[Depends(authorize_editor)],
    )
    async def list_source_articles(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        q: str | None = Query(None, min_length=1, max_length=200),
    ) -> SourceArticleListResponse:
        if source_article_repository is None:
            raise ValueError("source article repository is not configured")
        page = source_article_repository.list_source_articles(
            limit=limit,
            offset=offset,
            query=q,
        )
        next_offset = offset + len(page.items)
        return SourceArticleListResponse(
            items=[source_article_response(item) for item in page.items],
            total=page.total,
            limit=limit,
            offset=offset,
            next_offset=next_offset if next_offset < page.total else None,
        )

    @app.get(
        "/admin/v1/operations/summary",
        response_model=OperationsSummaryResponse,
        dependencies=[Depends(authorize_editor)],
    )
    async def operations_summary() -> OperationsSummaryResponse:
        if operations_repository is None:
            raise ValueError("operations repository is not configured")
        return operations_summary_response(operations_repository.summary())

    @app.get("/admin/v1/stories", response_model=AdminStoryListResponse, dependencies=[Depends(authorize_editor)])
    async def list_stories(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), status: str | None = None) -> AdminStoryListResponse:
        if story_repository is None:
            raise ValueError("story repository is not configured")
        items, total = story_repository.list_stories(limit=limit, offset=offset, status=status)
        next_offset = offset + len(items)
        return AdminStoryListResponse(items=[story_response(item) for item in items], total=total, limit=limit, offset=offset, next_offset=next_offset if next_offset < total else None)

    @app.get("/admin/v1/publications", response_model=AdminPublicationListResponse, dependencies=[Depends(authorize_editor)])
    async def list_publications(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> AdminPublicationListResponse:
        if publication_repository is None:
            raise ValueError("publication repository is not configured")
        items, total = publication_repository.list_publications(limit=limit, offset=offset)
        next_offset = offset + len(items)
        return AdminPublicationListResponse(items=[admin_publication_response(item) for item in items], total=total, limit=limit, offset=offset, next_offset=next_offset if next_offset < total else None)

    @app.get("/admin/v1/processing-failures", response_model=ProcessingFailureListResponse, dependencies=[Depends(authorize_editor)])
    async def list_processing_failures(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> ProcessingFailureListResponse:
        if failure_repository is None:
            raise ValueError("failure repository is not configured")
        items, total = failure_repository.list_failures(limit=limit, offset=offset)
        next_offset = offset + len(items)
        return ProcessingFailureListResponse(items=[failure_response(item) for item in items], total=total, limit=limit, offset=offset, next_offset=next_offset if next_offset < total else None)

    @app.get(
        "/admin/v1/articles/{article_id}/revision",
        response_model=EditorialRevisionDetailResponse,
        dependencies=[Depends(authorize_editor)],
    )
    async def get_revision(article_id: UUID) -> EditorialRevisionDetailResponse:
        return detail_response(service.get_revision(article_id))

    @app.put(
        "/admin/v1/articles/{article_id}/revision",
        response_model=EditorialRevisionDetailResponse,
        dependencies=[Depends(authorize_editor)],
    )
    async def update_revision(
        article_id: UUID, request: RevisionContentRequest
    ) -> EditorialRevisionDetailResponse:
        from datetime import UTC, datetime

        return detail_response(
            service.update_content(
                article_id,
                expected_revision_number=request.expected_revision_number,
                title_vi=request.title_vi,
                body_vi=request.body_vi,
                now=datetime.now(UTC),
            )
        )

    @app.post(
        "/admin/v1/articles/{article_id}/submit",
        response_model=EditorialRevisionResponse,
        dependencies=[Depends(authorize_editor)],
    )
    async def submit(
        article_id: UUID, request: RevisionTransitionRequest
    ) -> EditorialRevisionResponse:
        from datetime import UTC, datetime

        return response(
            service.submit_for_review(
                article_id,
                expected_revision_number=request.expected_revision_number,
                now=datetime.now(UTC),
            )
        )

    @app.post(
        "/admin/v1/articles/{article_id}/approve",
        response_model=EditorialRevisionResponse,
        dependencies=[Depends(authorize_editor)],
    )
    async def approve(
        article_id: UUID, request: RevisionTransitionRequest
    ) -> EditorialRevisionResponse:
        from datetime import UTC, datetime

        return response(
            service.approve(
                article_id,
                expected_revision_number=request.expected_revision_number,
                now=datetime.now(UTC),
            )
        )

    @app.post(
        "/admin/v1/articles/{article_id}/reject",
        response_model=EditorialRevisionResponse,
        dependencies=[Depends(authorize_editor)],
    )
    async def reject(
        article_id: UUID, request: RevisionTransitionRequest
    ) -> EditorialRevisionResponse:
        from datetime import UTC, datetime

        return response(
            service.reject(
                article_id,
                expected_revision_number=request.expected_revision_number,
                now=datetime.now(UTC),
            )
        )

    @app.post(
        "/admin/v1/articles/{article_id}/publish",
        response_model=PublicationResponse,
        dependencies=[Depends(authorize_admin)],
    )
    async def publish(article_id: UUID, request: PublishRequest) -> PublicationResponse:
        from datetime import UTC, datetime

        return publication_response(
            service.publish(
                article_id,
                slug=request.slug,
                idempotency_key=request.idempotency_key,
                now=datetime.now(UTC),
            )
        )

    return app

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from secrets import compare_digest
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from footballpulse_content_service.editorial.publication import PublicationConflictError
from footballpulse_content_service.editorial.repository import RevisionConflictError
from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class EditorialRevisionView:
    generated_article_id: UUID
    revision_id: UUID
    revision_number: int
    story_version: int
    state: str
    updated_at: datetime


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


class EditorialAdminService(Protocol):
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


class RevisionTransitionRequest(BaseModel):
    expected_revision_number: int


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


BEARER_SCHEME = HTTPBearer(auto_error=False)


def create_editorial_admin_app(
    service: EditorialAdminService, *, admin_token: str
) -> FastAPI:
    app = FastAPI(title="FootballPulse Editorial Admin API", version="0.1.0")

    async def authorize(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER_SCHEME)],
    ) -> None:
        if credentials is None or not compare_digest(credentials.credentials, admin_token):
            raise PermissionError

    @app.exception_handler(PermissionError)
    async def permission_error_handler(_: Request, __: PermissionError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "UNAUTHORIZED", "message": "invalid bearer token"}},
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

    def publication_response(view: PublicationView) -> PublicationResponse:
        return PublicationResponse.model_validate(view, from_attributes=True)

    @app.post(
        "/admin/v1/articles/{article_id}/submit",
        response_model=EditorialRevisionResponse,
        dependencies=[Depends(authorize)],
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
        dependencies=[Depends(authorize)],
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
        dependencies=[Depends(authorize)],
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
        dependencies=[Depends(authorize)],
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

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from secrets import compare_digest
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class EditorialRevisionView:
    generated_article_id: UUID
    revision_id: UUID
    revision_number: int
    story_version: int
    state: str
    updated_at: datetime


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


class RevisionTransitionRequest(BaseModel):
    expected_revision_number: int


class EditorialRevisionResponse(BaseModel):
    generated_article_id: UUID
    revision_id: UUID
    revision_number: int
    story_version: int
    state: str
    updated_at: datetime


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

    def response(view: EditorialRevisionView) -> EditorialRevisionResponse:
        return EditorialRevisionResponse.model_validate(view, from_attributes=True)

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

    return app

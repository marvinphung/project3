from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from footballpulse_api_gateway.api.editorial_admin import (
    EditorialRevisionView,
    OperationsSummaryView,
    PublicationView,
    SourceArticlePage,
    SourceArticleView,
    create_editorial_admin_app,
)
from footballpulse_api_gateway.auth import Role, TokenService
from footballpulse_content_service.editorial.repository import RevisionConflictError

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
ARTICLE_ID = UUID(int=1)


class MemoryEditorialService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID, int]] = []

    def _result(self, action: str, article_id: UUID, expected_revision_number: int):
        self.calls.append((action, article_id, expected_revision_number))
        return EditorialRevisionView(
            generated_article_id=article_id,
            revision_id=UUID(int=2),
            revision_number=expected_revision_number,
            story_version=4,
            state={"submit": "NEEDS_REVIEW", "approve": "APPROVED", "reject": "REJECTED"}[action],
            updated_at=NOW,
        )

    def submit_for_review(self, article_id, *, expected_revision_number, now):
        return self._result("submit", article_id, expected_revision_number)

    def approve(self, article_id, *, expected_revision_number, now):
        return self._result("approve", article_id, expected_revision_number)

    def reject(self, article_id, *, expected_revision_number, now):
        return self._result("reject", article_id, expected_revision_number)

    def publish(self, article_id, *, slug, idempotency_key, now):
        return PublicationView(
            id=UUID(int=3),
            generated_article_id=article_id,
            revision_id=UUID(int=2),
            story_id=UUID(int=4),
            story_version=4,
            slug=slug,
            title_vi="Arsenal hỏi mua",
            body_vi="Arsenal đã gửi đề nghị.",
            published_at=now,
        )

    def list_revisions_page(self, *, limit, offset, state):
        revisions = [
            self._detail("NEEDS_REVIEW", UUID(int=10)),
            self._detail("APPROVED", UUID(int=11)),
        ]
        filtered = [item for item in revisions if state is None or item.state == state]
        return filtered[offset:offset + limit], len(filtered)

    @staticmethod
    def _detail(state, article_id):
        from footballpulse_api_gateway.api.editorial_admin import EditorialRevisionDetailView

        return EditorialRevisionDetailView(
            generated_article_id=article_id, revision_id=UUID(int=2), revision_number=1,
            story_version=1, state=state, updated_at=NOW, story_id=UUID(int=3),
            title_en="Title", body_en="Body", title_vi="Tiêu đề", body_vi="Nội dung",
        )


class MemorySourceArticleRepository:
    def list_source_articles(self, *, limit, offset, query=None):
        assert limit == 50
        assert offset == 0
        assert query == "Arsenal"
        return SourceArticlePage(
            items=(
                SourceArticleView(
                    id="source-article-1",
                    title="Arsenal agree transfer terms",
                    source_url="https://www.bbc.com/sport/football/example",
                    collected_at=NOW,
                    extraction_status="SUCCESS",
                    duplicate_type="NONE",
                ),
            ),
            total=1655,
        )


class MemoryOperationsRepository:
    def summary(self):
        return OperationsSummaryView(
            source_articles_total=1655,
            source_articles_today=247,
            enrichments_validated=1,
            enrichments_needs_content_review=1192,
            revisions_by_state={"DRAFT": 2, "NEEDS_REVIEW": 3, "APPROVED": 4},
            publications_total=7,
        )


@pytest.mark.asyncio
async def test_editorial_admin_routes_require_token_and_transition_revision() -> None:
    service = MemoryEditorialService()
    transport = httpx.ASGITransport(
        app=create_editorial_admin_app(service, admin_token="admin-token")
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.post(
            f"/admin/v1/articles/{ARTICLE_ID}/submit",
            json={"expected_revision_number": 1},
        )
        approved = await client.post(
            f"/admin/v1/articles/{ARTICLE_ID}/approve",
            headers={"Authorization": "Bearer admin-token"},
            json={"expected_revision_number": 1},
        )

    assert unauthorized.status_code == 401
    assert approved.status_code == 200
    assert approved.json()["state"] == "APPROVED"
    assert service.calls == [("approve", ARTICLE_ID, 1)]


@pytest.mark.asyncio
async def test_editorial_admin_publish_uses_idempotency_key() -> None:
    service = MemoryEditorialService()
    transport = httpx.ASGITransport(
        app=create_editorial_admin_app(service, admin_token="admin-token")
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/admin/v1/articles/{ARTICLE_ID}/publish",
            headers={"Authorization": "Bearer admin-token"},
            json={"slug": "arsenal-bid", "idempotency_key": "publish-1"},
        )

    assert response.status_code == 200
    assert response.json()["slug"] == "arsenal-bid"


@pytest.mark.asyncio
async def test_editorial_admin_maps_revision_conflict_to_409() -> None:
    class ConflictService(MemoryEditorialService):
        def approve(self, article_id, *, expected_revision_number, now):
            raise RevisionConflictError("expected revision is no longer current")

    transport = httpx.ASGITransport(
        app=create_editorial_admin_app(ConflictService(), admin_token="admin-token")
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/admin/v1/articles/{ARTICLE_ID}/approve",
            headers={"Authorization": "Bearer admin-token"},
            json={"expected_revision_number": 1},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EDITORIAL_CONFLICT"


@pytest.mark.asyncio
async def test_editor_token_can_review_but_cannot_publish() -> None:
    service = MemoryEditorialService()
    transport = httpx.ASGITransport(
        app=create_editorial_admin_app(
            service, admin_token="admin-token", editor_token="editor-token"
        )
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        approved = await client.post(
            f"/admin/v1/articles/{ARTICLE_ID}/approve",
            headers={"Authorization": "Bearer editor-token"},
            json={"expected_revision_number": 1},
        )
        publication = await client.post(
            f"/admin/v1/articles/{ARTICLE_ID}/publish",
            headers={"Authorization": "Bearer editor-token"},
            json={"slug": "arsenal-bid", "idempotency_key": "publish-1"},
        )

    assert approved.status_code == 200
    assert publication.status_code == 403
    assert publication.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_jwt_role_controls_editorial_routes() -> None:
    service = MemoryEditorialService()
    token_service = TokenService("local-secret-012345678901234567890123", clock=lambda: NOW)
    editor_jwt = token_service.issue(subject="editor", role=Role.EDITOR, now=NOW)
    admin_jwt = token_service.issue(subject="admin", role=Role.ADMIN, now=NOW)
    transport = httpx.ASGITransport(
        app=create_editorial_admin_app(
            service,
            admin_token="static-admin-token",
            token_service=token_service,
        )
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        reviewed = await client.post(
            f"/admin/v1/articles/{ARTICLE_ID}/approve",
            headers={"Authorization": f"Bearer {editor_jwt}"},
            json={"expected_revision_number": 1},
        )
        forbidden = await client.post(
            f"/admin/v1/articles/{ARTICLE_ID}/publish",
            headers={"Authorization": f"Bearer {editor_jwt}"},
            json={"slug": "arsenal-bid", "idempotency_key": "publish-1"},
        )
        published = await client.post(
            f"/admin/v1/articles/{ARTICLE_ID}/publish",
            headers={"Authorization": f"Bearer {admin_jwt}"},
            json={"slug": "arsenal-bid", "idempotency_key": "publish-2"},
        )

    assert reviewed.status_code == 200
    assert forbidden.status_code == 403
    assert published.status_code == 200


@pytest.mark.asyncio
async def test_editorial_admin_lists_source_articles_with_pagination_and_query() -> None:
    transport = httpx.ASGITransport(
        app=create_editorial_admin_app(
            MemoryEditorialService(),
            admin_token="admin-token",
            source_article_repository=MemorySourceArticleRepository(),
        )
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/admin/v1/source-articles?limit=50&offset=0&q=Arsenal",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "source-article-1",
                "title": "Arsenal agree transfer terms",
                "source_url": "https://www.bbc.com/sport/football/example",
                "collected_at": "2026-08-10T12:00:00Z",
                "extraction_status": "SUCCESS",
                "duplicate_type": "NONE",
            }
        ],
        "total": 1655,
        "limit": 50,
        "offset": 0,
        "next_offset": 1,
    }


@pytest.mark.asyncio
async def test_editorial_admin_returns_live_operations_summary() -> None:
    transport = httpx.ASGITransport(
        app=create_editorial_admin_app(
            MemoryEditorialService(),
            admin_token="admin-token",
            operations_repository=MemoryOperationsRepository(),
        )
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/admin/v1/operations/summary",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.json()["source_articles_total"] == 1655
    assert response.json()["enrichments_needs_content_review"] == 1192
    assert response.json()["revisions_by_state"]["NEEDS_REVIEW"] == 3


@pytest.mark.asyncio
async def test_editorial_admin_paginates_and_filters_revisions() -> None:
    transport = httpx.ASGITransport(
        app=create_editorial_admin_app(MemoryEditorialService(), admin_token="admin-token")
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/admin/v1/editorial/revisions?state=NEEDS_REVIEW&limit=50&offset=0",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["state"] for item in response.json()["items"]] == ["NEEDS_REVIEW"]

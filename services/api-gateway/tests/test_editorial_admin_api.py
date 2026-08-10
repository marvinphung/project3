from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from footballpulse_api_gateway.api.editorial_admin import (
    EditorialRevisionView,
    create_editorial_admin_app,
)

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

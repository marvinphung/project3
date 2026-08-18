from __future__ import annotations

from sqlalchemy import Engine, text
from footballpulse_api_gateway.api.editorial_admin import AdminPublicationView


class AdminPublicationReadRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_publications(self, *, limit: int, offset: int) -> tuple[list[AdminPublicationView], int]:
        with self._engine.connect() as connection:
            rows = connection.execute(text("SELECT id, slug, title_vi, story_id, published_at FROM content_schema.publications ORDER BY published_at DESC LIMIT :limit OFFSET :offset"), {"limit": limit, "offset": offset}).mappings().all()
            total = int(connection.execute(text("SELECT COUNT(*) FROM content_schema.publications")).scalar_one())
        return [AdminPublicationView(id=row["id"], slug=row["slug"], title_vi=row["title_vi"], story_id=row["story_id"], published_at=row["published_at"]) for row in rows], total

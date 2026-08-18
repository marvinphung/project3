from __future__ import annotations

from sqlalchemy import Engine, text

from footballpulse_api_gateway.api.editorial_admin import AdminStoryView


class AdminStoryReadRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_stories(self, *, limit: int, offset: int, status: str | None) -> tuple[list[AdminStoryView], int]:
        where = "WHERE s.status = :status" if status else ""
        params = {"limit": limit, "offset": offset, "status": status}
        query = text(f"SELECT s.id, s.event_type, s.status, s.confidence_score, s.version, s.last_seen_at, COUNT(ss.id) AS source_count FROM intelligence_schema.stories s LEFT JOIN intelligence_schema.story_sources ss ON ss.story_id = s.id {where} GROUP BY s.id, s.event_type, s.status, s.confidence_score, s.version, s.last_seen_at ORDER BY s.last_seen_at DESC LIMIT :limit OFFSET :offset")
        count = text(f"SELECT COUNT(*) FROM intelligence_schema.stories s {where}")
        with self._engine.connect() as connection:
            rows = connection.execute(query, params).mappings().all()
            total = int(connection.execute(count, params).scalar_one())
        return [AdminStoryView(id=row["id"], event_type=row["event_type"], status=row["status"], confidence_score=float(row["confidence_score"]), version=row["version"], last_seen_at=row["last_seen_at"], source_count=int(row["source_count"])) for row in rows], total

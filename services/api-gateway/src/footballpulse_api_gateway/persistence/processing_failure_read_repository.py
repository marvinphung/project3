from __future__ import annotations

from sqlalchemy import Engine, text
from footballpulse_api_gateway.api.editorial_admin import ProcessingFailureView


class ProcessingFailureReadRepository:
    def __init__(self, engine: Engine) -> None: self._engine = engine
    def list_failures(self, *, limit: int, offset: int) -> tuple[list[ProcessingFailureView], int]:
        predicate = "state = 'FAILED'"
        with self._engine.connect() as connection:
            rows = connection.execute(text(f"SELECT event_id, state, last_error, attempt_count, COALESCE(last_failed_at, created_at) AS occurred_at FROM content_schema.publication_outbox WHERE {predicate} ORDER BY occurred_at DESC LIMIT :limit OFFSET :offset"), {"limit": limit, "offset": offset}).mappings().all()
            total = int(connection.execute(text(f"SELECT COUNT(*) FROM content_schema.publication_outbox WHERE {predicate}")).scalar_one())
        return [ProcessingFailureView(id=f"publication:{row['event_id']}", stage="Publication outbox", status=row["state"], message=row["last_error"] or "Publication delivery failed", attempts=row["attempt_count"], occurred_at=row["occurred_at"]) for row in rows], total

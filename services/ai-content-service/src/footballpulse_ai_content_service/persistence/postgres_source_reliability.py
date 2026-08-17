from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine


class PostgresSourceReliabilityRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, source_id: UUID) -> int:
        with self._engine.connect() as connection:
            value = connection.execute(
                sa.text("SELECT reliability_tier FROM source_schema.sources WHERE id = :source_id"),
                {"source_id": source_id},
            ).scalar_one_or_none()
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
            raise ValueError("source reliability tier was not found")
        return value

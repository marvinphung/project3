from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo.database import Database
from sqlalchemy import Engine, text

from footballpulse_api_gateway.api.editorial_admin import OperationsSummaryView


class OperationsReadRepository:
    """Read-only operational counts for the editorial dashboard."""

    def __init__(self, mongo_database: Database[dict[str, Any]], engine: Engine) -> None:
        self._mongo_database = mongo_database
        self._engine = engine

    def summary(self) -> OperationsSummaryView:
        source_articles = self._mongo_database["source_articles"]
        enrichments = self._mongo_database["article_enrichments"]
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        enrichment_counts = {
            str(row["_id"]): int(row["count"])
            for row in enrichments.aggregate(
                [{"$group": {"_id": "$validation_status", "count": {"$sum": 1}}}]
            )
            if row.get("_id") is not None
        }
        with self._engine.connect() as connection:
            revision_rows = connection.execute(
                text(
                    "SELECT state, COUNT(*) AS count "
                    "FROM content_schema.editorial_revisions GROUP BY state"
                )
            ).mappings()
            revisions_by_state = {
                str(row["state"]): int(row["count"])
                for row in revision_rows
            }
            publications_total = int(
                connection.execute(
                    text("SELECT COUNT(*) FROM content_schema.publications")
                ).scalar_one()
            )
        return OperationsSummaryView(
            source_articles_total=source_articles.count_documents({}),
            source_articles_today=source_articles.count_documents(
                {"collected_at": {"$gte": today_start}}
            ),
            enrichments_validated=enrichment_counts.get("VALIDATED", 0),
            enrichments_needs_content_review=enrichment_counts.get(
                "NEEDS_CONTENT_REVIEW", 0
            ),
            revisions_by_state=revisions_by_state,
            publications_total=publications_total,
        )

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend(
    [
        str(ROOT / "services/content-summary-service/src"),
        str(ROOT / "packages/mongo-models/src"),
    ]
)

from footballpulse_content_summary_service.summary_generator import SummaryGenerator
from footballpulse_content_summary_service.llm_client import MockLLMClient
from footballpulse_content_summary_service.window_planner import get_latest_closed_3h_window


def main() -> None:
    mongo_url = os.getenv("FOOTBALLPULSE_V2_MONGODB_URL", "mongodb://127.0.0.1:27117/?directConnection=true")
    mongo = MongoClient(mongo_url, uuidRepresentation="standard")
    database = mongo[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2")]

    generator = SummaryGenerator(database=database, llm_client=MockLLMClient())
    w_start, w_end = get_latest_closed_3h_window(datetime.now(UTC))

    created = generator.generate_for_window(window_start=w_start, window_end=w_end, force=True)
    print(f"v2 summary smoke passed: generated={created} window={w_start.isoformat()}-{w_end.isoformat()}")


if __name__ == "__main__":
    main()

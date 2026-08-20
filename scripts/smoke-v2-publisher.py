from __future__ import annotations

import os
import sys
from pathlib import Path

from pymongo import MongoClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend(
    [
        str(ROOT / "services/publisher-service/src"),
    ]
)

from footballpulse_publisher_service.publisher import V2Publisher


def main() -> None:
    mongo_url = os.getenv("FOOTBALLPULSE_V2_MONGODB_URL", "mongodb://127.0.0.1:27117/?directConnection=true")
    mongo = MongoClient(mongo_url, uuidRepresentation="standard")
    database = mongo[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2")]

    postgres_url = os.getenv("FOOTBALLPULSE_V2_POSTGRES_URL")
    if postgres_url:
        engine = create_engine(postgres_url, pool_pre_ping=True)
    elif os.getenv("SUPABASE_DB_HOST"):
        url = URL.create(
            "postgresql+psycopg",
            username=os.environ["SUPABASE_DB_USER"],
            password=os.environ["SUPABASE_DB_PASSWORD"],
            host=os.environ["SUPABASE_DB_HOST"],
            port=int(os.environ.get("SUPABASE_DB_PORT", "5432")),
            database=os.environ.get("SUPABASE_DB_NAME", "postgres"),
        )
        engine = create_engine(url, pool_pre_ping=True)
    else:
        url = URL.create(
            "postgresql+psycopg",
            username=os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
            password=os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_v2_local"),
            host=os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "15432")),
            database=os.getenv("FOOTBALLPULSE_POSTGRES_DB", "footballpulse_v2"),
        )
        engine = create_engine(url, pool_pre_ping=True)

    publisher = V2Publisher(mongo=database, postgres=engine)
    published = publisher.publish_pending(limit=50)

    with engine.begin() as conn:
        entity_count = conn.execute(text("select count(*) from entities")).scalar_one()
        timeline_count = conn.execute(text("select count(*) from entity_timeline_items")).scalar_one()

    print(
        f"v2 publisher smoke passed: published={published} entities={entity_count} timeline_items={timeline_count}"
    )


if __name__ == "__main__":
    main()


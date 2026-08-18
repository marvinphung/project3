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
        str(ROOT / 'services/publisher-service/src'),
    ]
)

from footballpulse_publisher_service.publisher import V2Publisher


def main() -> None:
    mongo = MongoClient(
        'mongodb://127.0.0.1:27117/?directConnection=true',
        uuidRepresentation='standard',
    )
    database = mongo['footballpulse_v2']
    metadata = database.news_metadata.find_one(sort=[('crawl_date', -1)])
    if metadata is None:
        raise AssertionError('no crawled article found')
    article_id = metadata['_id']

    url = URL.create(
        'postgresql+psycopg',
        username=os.environ['SUPABASE_DB_USER'],
        password=os.environ['SUPABASE_DB_PASSWORD'],
        host=os.environ['SUPABASE_DB_HOST'],
        port=int(os.environ['SUPABASE_DB_PORT']),
        database=os.environ['SUPABASE_DB_NAME'],
    )
    engine = create_engine(url, pool_pre_ping=True)
    publisher = V2Publisher(mongo=database, postgres=engine)
    published = publisher.publish_article(article_id)
    if not published:
        raise AssertionError('publisher refused the enriched article')

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """select p.slug, p.title_vi, a.canonical_url, s.domain_name
                from publications p
                join stories st on st.id = p.story_id
                join story_sources ss on ss.story_id = st.id
                join articles a on a.id = ss.article_id
                join sources s on s.id = ss.source_id
                where p.id = :article_id"""
            ),
            {'article_id': article_id},
        ).mappings().one()
    print(
        'v2 publisher smoke passed: '
        f"slug={row['slug']} domain={row['domain_name']} canonical_url={row['canonical_url']}"
    )


if __name__ == '__main__':
    main()

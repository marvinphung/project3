from __future__ import annotations

import re
import sys
from pathlib import Path

from confluent_kafka import Consumer, Producer
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend(
    [
        str(ROOT / 'packages/event-contracts/src'),
        str(ROOT / 'services/crawler-service/src'),
        str(ROOT / 'services/ai-content-service/src'),
    ]
)

from footballpulse_crawler_service.messaging.v2 import V2NewsCrawledPublisher
from footballpulse_ai_content_service.v2_processor import V2EntityProcessor, V2NewsCrawledConsumer


def extract_entities(text: str) -> list[dict[str, object]]:
    patterns = {
        'PLAYER': ['Vinícius Júnior', 'Vinicius Júnior', 'Vinicius', 'Haaland', 'Mbappe', 'Saka', 'Salah'],
        'CLUB': ['Real Madrid', 'Arsenal', 'Chelsea', 'Liverpool', 'Man City', 'City', 'United'],
    }
    entities: list[dict[str, object]] = []
    for label, values in patterns.items():
        for value in values:
            for match in re.finditer(re.escape(value), text, re.IGNORECASE):
                entities.append(
                    {
                        'label': label,
                        'text': match.group(0),
                        'score': 0.99,
                        'start': match.start(),
                        'end': match.end(),
                        'canonical_entity_id': None,
                        'canonical_name': match.group(0),
                    }
                )
    if not entities:
        # Fallback to extracting first capitalized words
        for match in re.finditer(r'\b[A-Z][a-z]{2,}\b', text):
            entities.append(
                {
                    'label': 'PERSON',
                    'text': match.group(0),
                    'score': 0.75,
                    'start': match.start(),
                    'end': match.end(),
                    'canonical_entity_id': None,
                    'canonical_name': match.group(0),
                }
            )
            if len(entities) >= 3:
                break
    return entities


def main() -> None:
    mongo = MongoClient(
        'mongodb://127.0.0.1:27117/?directConnection=true',
        uuidRepresentation='standard',
    )
    database = mongo['footballpulse_v2']
    metadata = database.news_metadata.find_one(sort=[('crawl_date', -1)])
    if metadata is None:
        raise AssertionError('no crawled article found; run smoke-v2-crawler.py first')
    article_id = metadata['_id']

    producer = Producer({'bootstrap.servers': '127.0.0.1:19092'})
    publisher = V2NewsCrawledPublisher(producer, source_name='Fixture Source')
    publisher.publish(article_id=article_id, canonical_url=metadata['canonical_url'])
    producer.flush(5.0)

    from uuid import uuid4
    consumer = Consumer(
        {
            'bootstrap.servers': '127.0.0.1:19092',
            'group.id': f'footballpulse-v2-smoke-{uuid4()}',
            'enable.auto.commit': False,
            'auto.offset.reset': 'earliest',
        }
    )
    processor = V2EntityProcessor(database=database, extractor=extract_entities, workers=2)
    worker = V2NewsCrawledConsumer(consumer=consumer, processor=processor)
    processed = worker.run_once(timeout_seconds=10.0)
    consumer.close()

    if processed is None:
        raise AssertionError('processor did not return any article id')
    document = database.news_entities.find_one({'_id': processed})
    if document is None:
        raise AssertionError('processor did not write news_entities')
    entities = document.get('entities', [])
    if not isinstance(entities, list) or not entities:
        raise AssertionError('processor wrote an empty entity list')
    print(f'v2 processor smoke passed: article_id={processed} entities={len(entities)}')


if __name__ == '__main__':
    main()

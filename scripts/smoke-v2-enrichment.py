from __future__ import annotations

import json
import tempfile
from pathlib import Path

from confluent_kafka import Consumer, Producer
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.extend(
    [
        str(ROOT / 'services/ai-content-service/src'),
    ]
)

from footballpulse_ai_content_service.v2_enrichment_sink import V2EnrichmentSink
from footballpulse_ai_content_service.v2_kaggle_dataset import V2KaggleDatasetBuilder


def main() -> None:
    mongo = MongoClient(
        'mongodb://127.0.0.1:27117/?directConnection=true',
        uuidRepresentation='standard',
    )
    database = mongo['footballpulse_v2']

    with tempfile.TemporaryDirectory(prefix='footballpulse-v2-kaggle-') as tmp_dir:
        output_path = Path(tmp_dir) / 'dataset'
        builder = V2KaggleDatasetBuilder(database)
        count = builder.build(output_path)
        rows = (output_path / 'articles.jsonl').read_text(encoding='utf-8').strip().splitlines()
        if count < 1 or len(rows) != count:
            raise AssertionError('kaggle backlog builder did not export the expected rows')

    metadata = database.news_metadata.find_one(sort=[('crawl_date', -1)])
    if metadata is None:
        raise AssertionError('no crawled article available for enrichment smoke')
    article_id = metadata['_id']

    producer = Producer({'bootstrap.servers': '127.0.0.1:19092'})
    sink = V2EnrichmentSink(database=database, producer=producer)
    accepted = sink.persist_validated(
        article_id=article_id,
        output={
            'validation_status': 'VALIDATED',
            'event_type': 'CONTRACT',
            'summary_en': 'Real Madrid opened contract talks with Vinicius Junior.',
            'summary_vi': 'Real Madrid đã mở đàm phán hợp đồng với Vinicius Junior.',
            'claims': [
                {
                    'subject': 'Real Madrid',
                    'subject_entity_id': None,
                    'predicate': 'NEGOTIATING_CONTRACT',
                    'object': 'Vinicius Junior',
                    'object_entity_id': None,
                    'object_value': None,
                    'certainty': 'REPORTED',
                    'evidence_quote': 'Real Madrid have opened talks with forward Vinícius Júnior over a new contract.',
                    'evidence_start': 0,
                    'evidence_end': 82,
                }
            ],
            'model_name': 'qwen3',
            'model_version': 'fixture-runtime',
            'prompt_version': 'article-enrichment-v1',
        },
    )
    if not accepted:
        raise AssertionError('validated enrichment was not accepted')

    stored = database.news_enrichments.find_one({'_id': article_id})
    if stored is None or stored.get('validation_status') != 'VALIDATED':
        raise AssertionError('validated enrichment was not written to Mongo')

    producer.flush(5.0)

    from uuid import uuid4
    consumer = Consumer(
        {
            'bootstrap.servers': '127.0.0.1:19092',
            'group.id': f'footballpulse-v2-enrichment-smoke-{uuid4()}',
            'enable.auto.commit': False,
            'auto.offset.reset': 'earliest',
        }
    )
    consumer.subscribe(['news.enriched.v1'])
    matched = False
    for _ in range(10):
        message = consumer.poll(2.0)
        if message is None or message.error() is not None:
            continue
        payload = json.loads(message.value().decode('utf-8'))
        if payload.get('article_id') == str(article_id):
            matched = True
            break
    consumer.close()
    if not matched:
        raise AssertionError(f'did not receive news.enriched.v1 event for {article_id}')

    print(f'v2 enrichment smoke passed: backlog_rows={count} article_id={article_id}')


if __name__ == '__main__':
    main()

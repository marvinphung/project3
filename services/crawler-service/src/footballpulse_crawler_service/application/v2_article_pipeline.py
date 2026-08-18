from __future__ import annotations

from uuid import UUID

from footballpulse_crawler_service.extraction.service import ExtractedArticle
from footballpulse_crawler_service.messaging.v2 import V2NewsCrawledPublisher
from footballpulse_crawler_service.persistence.mongo_v2 import V2MongoArticleWriter


class V2ArticlePipeline:
    """Persist Mongo first, then emit the lightweight Kafka pointer."""

    def __init__(
        self,
        *,
        mongo: V2MongoArticleWriter,
        kafka: V2NewsCrawledPublisher,
    ) -> None:
        self._mongo = mongo
        self._kafka = kafka

    def persist_and_publish(self, article: ExtractedArticle) -> UUID | None:
        article_id = self._mongo.write(article, source_name=article.source_key)
        if article_id is None:
            return None
        self._kafka.publish(article_id=article_id, canonical_url=article.final_url)
        return article_id

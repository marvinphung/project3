"""Versioned Kafka event contracts for FootballPulse."""

from importlib.metadata import version

from .article_discovered import ArticleDiscoveredPayloadV1, ArticleDiscoveredV1

__version__ = version("footballpulse-event-contracts")

__all__ = [
    "ArticleDiscoveredPayloadV1",
    "ArticleDiscoveredV1",
    "__version__",
]

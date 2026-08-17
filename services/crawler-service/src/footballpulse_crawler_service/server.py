from __future__ import annotations

import logging
import os

import uvicorn
from footballpulse_runtime_config import configure_logging, log_event

LOGGER = logging.getLogger("footballpulse.crawler.api")


def main() -> None:
    configure_logging(
        service="crawler-api",
        level=os.getenv("FOOTBALLPULSE_LOG_LEVEL", "INFO"),
        force=True,
    )
    log_event(LOGGER, "service_started", port=int(os.getenv("FOOTBALLPULSE_CRAWLER_PORT", "8011")))
    uvicorn.run(
        "footballpulse_crawler_service.runtime:app",
        host=os.getenv("FOOTBALLPULSE_CRAWLER_HOST", "127.0.0.1"),
        port=int(os.getenv("FOOTBALLPULSE_CRAWLER_PORT", "8011")),
    )

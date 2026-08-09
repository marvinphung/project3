from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "footballpulse_crawler_service.runtime:app",
        host="127.0.0.1",
        port=int(os.getenv("FOOTBALLPULSE_CRAWLER_PORT", "8011")),
    )

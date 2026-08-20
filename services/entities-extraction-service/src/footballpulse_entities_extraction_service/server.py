from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from footballpulse_runtime_config import configure_logging

from footballpulse_entities_extraction_service.health import liveness


def build_app() -> FastAPI:
    app = FastAPI(title="FootballPulse Entities Extraction Service", version="0.1.0")

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return liveness()

    return app


app = build_app()


def main() -> None:
    configure_logging(
        service="entities-extraction-service",
        level=os.getenv("FOOTBALLPULSE_LOG_LEVEL", "INFO"),
        force=True,
    )
    uvicorn.run(
        "footballpulse_entities_extraction_service.server:app",
        host=os.getenv("FOOTBALLPULSE_ENTITIES_HOST", "0.0.0.0"),
        port=int(os.getenv("FOOTBALLPULSE_ENTITIES_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()

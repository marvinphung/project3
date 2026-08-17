from __future__ import annotations

import logging
import os
from collections.abc import Mapping

import uvicorn
from fastapi import FastAPI
from footballpulse_runtime_config import configure_logging, log_event

from footballpulse_ai_content_service.api.app import create_app
from footballpulse_ai_content_service.providers.base import ProviderName
from footballpulse_ai_content_service.providers.config import ProviderSettings
from footballpulse_ai_content_service.providers.factory import build_provider_from_environment

LOGGER = logging.getLogger("footballpulse.ai.api")


def create_runtime_app(values: Mapping[str, str]) -> FastAPI:
    token = values.get("FOOTBALLPULSE_AI_INTERNAL_TOKEN", "").strip()
    if not token:
        raise RuntimeError("FOOTBALLPULSE_AI_INTERNAL_TOKEN is required")
    settings = ProviderSettings.from_environment(values)
    provider = (
        None
        if settings.provider is ProviderName.KAGGLE
        else build_provider_from_environment(values)
    )
    return create_app(internal_token=token, provider=provider)


def main() -> None:
    configure_logging(
        service="ai-content-service",
        level=os.getenv("FOOTBALLPULSE_LOG_LEVEL", "INFO"),
        force=True,
    )
    log_event(LOGGER, "service_started", provider=os.getenv("FOOTBALLPULSE_AI_PROVIDER", "kaggle"))
    uvicorn.run(
        create_runtime_app(os.environ),
        host=os.getenv("FOOTBALLPULSE_AI_HOST", "0.0.0.0"),
        port=int(os.getenv("FOOTBALLPULSE_AI_PORT", "8000")),
    )


if __name__ == "__main__":
    main()

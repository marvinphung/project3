from __future__ import annotations

import os
from collections.abc import Mapping

import uvicorn
from fastapi import FastAPI

from footballpulse_ai_content_service.api.app import create_app
from footballpulse_ai_content_service.providers.factory import build_provider_from_environment


def create_runtime_app(values: Mapping[str, str]) -> FastAPI:
    token = values.get("FOOTBALLPULSE_AI_INTERNAL_TOKEN", "").strip()
    if not token:
        raise RuntimeError("FOOTBALLPULSE_AI_INTERNAL_TOKEN is required")
    return create_app(
        internal_token=token,
        provider=build_provider_from_environment(values),
    )


def main() -> None:
    uvicorn.run(
        create_runtime_app(os.environ),
        host=os.getenv("FOOTBALLPULSE_AI_HOST", "0.0.0.0"),
        port=int(os.getenv("FOOTBALLPULSE_AI_PORT", "8000")),
    )


if __name__ == "__main__":
    main()

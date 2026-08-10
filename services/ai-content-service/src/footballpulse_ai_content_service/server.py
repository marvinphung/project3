from __future__ import annotations

import os

import uvicorn

from footballpulse_ai_content_service.api.app import create_app


def main() -> None:
    token = os.environ.get("FOOTBALLPULSE_AI_INTERNAL_TOKEN")
    if not token:
        raise RuntimeError("FOOTBALLPULSE_AI_INTERNAL_TOKEN is required")
    uvicorn.run(
        create_app(internal_token=token),
        host=os.getenv("FOOTBALLPULSE_AI_HOST", "0.0.0.0"),
        port=int(os.getenv("FOOTBALLPULSE_AI_PORT", "8000")),
    )

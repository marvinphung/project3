from __future__ import annotations

import os

import uvicorn

from footballpulse_ai_content_service.api.app import create_app
from footballpulse_ai_content_service.providers.offline import DeterministicOfflineProvider


def main() -> None:
    token = os.environ.get("FOOTBALLPULSE_AI_INTERNAL_TOKEN")
    if not token:
        raise RuntimeError("FOOTBALLPULSE_AI_INTERNAL_TOKEN is required")
    offline_worker = os.getenv("FOOTBALLPULSE_AI_OFFLINE_WORKER", "false").casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }
    uvicorn.run(
        create_app(
            internal_token=token,
            provider=DeterministicOfflineProvider() if offline_worker else None,
        ),
        host=os.getenv("FOOTBALLPULSE_AI_HOST", "0.0.0.0"),
        port=int(os.getenv("FOOTBALLPULSE_AI_PORT", "8000")),
    )


if __name__ == "__main__":
    main()

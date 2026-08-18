from __future__ import annotations

import pytest
from footballpulse_ai_content_service.server import create_runtime_app


def test_runtime_app_rejects_removed_mock_provider() -> None:
    with pytest.raises(ValueError, match="kaggle or local"):
        create_runtime_app(
            {
                "FOOTBALLPULSE_ENV": "demo",
                "FOOTBALLPULSE_AI_INTERNAL_TOKEN": "test-token",
                "FOOTBALLPULSE_AI_PROVIDER": "mock",
            }
        )


def test_runtime_app_requires_internal_token() -> None:
    with pytest.raises(RuntimeError, match="AI_INTERNAL_TOKEN"):
        create_runtime_app(
            {
                "FOOTBALLPULSE_ENV": "production",
                "FOOTBALLPULSE_AI_PROVIDER": "kaggle",
            }
        )

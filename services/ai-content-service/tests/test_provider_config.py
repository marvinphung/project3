from __future__ import annotations

from pathlib import Path

import pytest
from footballpulse_ai_content_service.providers.base import ProviderName
from footballpulse_ai_content_service.providers.config import ProviderSettings


def test_default_provider_is_kaggle_without_loading_local_model() -> None:
    settings = ProviderSettings.from_environment({"FOOTBALLPULSE_ENV": "local"})

    assert settings.provider is ProviderName.KAGGLE
    assert settings.allow_local_fallback is False
    assert settings.local_model is None


def test_local_config_builds_lazy_model_settings() -> None:
    settings = ProviderSettings.from_environment(
        {
            "FOOTBALLPULSE_ENV": "local",
            "FOOTBALLPULSE_AI_PROVIDER": "local",
            "FOOTBALLPULSE_LOCAL_MODEL_PATH": "/models/qwen3-4b-q4_k_m.gguf",
            "FOOTBALLPULSE_LOCAL_MODEL_SHA256": "a" * 64,
            "FOOTBALLPULSE_LOCAL_MODEL_N_CTX": "16384",
            "FOOTBALLPULSE_LOCAL_MODEL_N_THREADS": "6",
        }
    )

    assert settings.local_model is not None
    assert settings.local_model.model_path == Path("/models/qwen3-4b-q4_k_m.gguf")
    assert settings.local_model.model_sha256 == "a" * 64
    assert settings.local_model.n_ctx == 16_384
    assert settings.local_model.n_threads == 6


def test_local_fallback_requires_model_path() -> None:
    with pytest.raises(ValueError, match="LOCAL_MODEL_PATH"):
        ProviderSettings.from_environment(
            {
                "FOOTBALLPULSE_ENV": "local",
                "FOOTBALLPULSE_AI_ALLOW_LOCAL_FALLBACK": "true",
            }
        )


def test_mock_is_forbidden_outside_test_or_demo() -> None:
    with pytest.raises(ValueError, match="test or demo"):
        ProviderSettings.from_environment(
            {
                "FOOTBALLPULSE_ENV": "local",
                "FOOTBALLPULSE_AI_PROVIDER": "mock",
                "FOOTBALLPULSE_AI_ALLOW_MOCK": "true",
                "FOOTBALLPULSE_MOCK_FIXTURE_PATH": "/fixtures/mock.jsonl",
            }
        )

    settings = ProviderSettings.from_environment(
        {
            "FOOTBALLPULSE_ENV": "demo",
            "FOOTBALLPULSE_AI_PROVIDER": "mock",
            "FOOTBALLPULSE_AI_ALLOW_MOCK": "true",
            "FOOTBALLPULSE_MOCK_FIXTURE_PATH": "/fixtures/mock.jsonl",
        }
    )
    assert settings.provider is ProviderName.MOCK


def test_deterministic_offline_mock_needs_no_fixture_in_demo() -> None:
    settings = ProviderSettings.from_environment(
        {
            "FOOTBALLPULSE_ENV": "demo",
            "FOOTBALLPULSE_AI_PROVIDER": "mock",
            "FOOTBALLPULSE_AI_ALLOW_MOCK": "true",
            "FOOTBALLPULSE_AI_DETERMINISTIC_OFFLINE": "true",
        }
    )

    assert settings.deterministic_offline is True
    assert settings.mock_fixture_path is None


@pytest.mark.parametrize(
    "values",
    [
        {
            "FOOTBALLPULSE_ENV": "local",
            "FOOTBALLPULSE_AI_PROVIDER": "mock",
            "FOOTBALLPULSE_AI_ALLOW_MOCK": "true",
            "FOOTBALLPULSE_AI_DETERMINISTIC_OFFLINE": "true",
        },
        {
            "FOOTBALLPULSE_ENV": "demo",
            "FOOTBALLPULSE_AI_PROVIDER": "kaggle",
            "FOOTBALLPULSE_AI_DETERMINISTIC_OFFLINE": "true",
        },
    ],
)
def test_deterministic_offline_mode_fails_closed(values: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="deterministic offline"):
        ProviderSettings.from_environment(values)


def test_boolean_and_numeric_config_fail_closed() -> None:
    with pytest.raises(ValueError, match="boolean"):
        ProviderSettings.from_environment(
            {
                "FOOTBALLPULSE_ENV": "local",
                "FOOTBALLPULSE_AI_ALLOW_LOCAL_FALLBACK": "sometimes",
            }
        )

    with pytest.raises(ValueError, match="integer"):
        ProviderSettings.from_environment(
            {
                "FOOTBALLPULSE_ENV": "local",
                "FOOTBALLPULSE_AI_PROVIDER": "local",
                "FOOTBALLPULSE_LOCAL_MODEL_PATH": "/models/model.gguf",
                "FOOTBALLPULSE_LOCAL_MODEL_N_THREADS": "many",
            }
        )

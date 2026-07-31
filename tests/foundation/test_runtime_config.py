from pathlib import Path
from typing import Any, cast

import pytest
from footballpulse_runtime_config import RuntimeSettings
from pydantic import ValidationError

ENV_EXAMPLE_PATH = Path(__file__).parents[2] / ".env.example"


def valid_environment() -> dict[str, str]:
    return {
        "FOOTBALLPULSE_ENVIRONMENT": "test",
        "FOOTBALLPULSE_LOG_LEVEL": "INFO",
        "FOOTBALLPULSE_POSTGRES_DSN": (
            "postgresql+psycopg://footballpulse:secret@postgres/footballpulse"
        ),
        "FOOTBALLPULSE_MONGODB_DSN": "mongodb://mongodb:27017/?replicaSet=rs0",
        "FOOTBALLPULSE_REDIS_DSN": "redis://:secret@redis:6379/0",
        "FOOTBALLPULSE_KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
        "FOOTBALLPULSE_JWT_SECRET": "jwt-secret-with-at-least-32-characters",
        "FOOTBALLPULSE_INTERNAL_API_TOKEN": ("internal-token-with-at-least-32-chars"),
        "FOOTBALLPULSE_AI_PROVIDER": "mock",
    }


def load_settings(
    monkeypatch: pytest.MonkeyPatch, environment: dict[str, str]
) -> RuntimeSettings:
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    settings_factory = cast(Any, RuntimeSettings)
    return cast(RuntimeSettings, settings_factory(_env_file=None))


def test_settings_parse_explicit_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(monkeypatch, valid_environment())

    assert settings.environment == "test"
    assert settings.kafka_bootstrap_servers == ("kafka:9092",)
    assert settings.ai_provider == "mock"


def test_settings_reject_default_or_short_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = valid_environment()
    environment["FOOTBALLPULSE_JWT_SECRET"] = "change-me"

    with pytest.raises(ValidationError):
        load_settings(monkeypatch, environment)


def test_settings_repr_and_dump_redact_all_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = valid_environment()
    settings = load_settings(monkeypatch, environment)

    rendered = repr(settings)
    dumped = settings.safe_dump()

    for secret in (
        environment["FOOTBALLPULSE_POSTGRES_DSN"],
        environment["FOOTBALLPULSE_REDIS_DSN"],
        environment["FOOTBALLPULSE_JWT_SECRET"],
        environment["FOOTBALLPULSE_INTERNAL_API_TOKEN"],
    ):
        assert secret not in rendered
        assert secret not in str(dumped)

    assert (
        dumped["postgres_dsn"] == "postgresql+psycopg://***:***@postgres/footballpulse"
    )
    assert dumped["mongodb_dsn"] == "mongodb://mongodb:27017/?replicaSet=rs0"
    assert dumped["redis_dsn"] == "redis://***:***@redis:6379/0"


def test_settings_do_not_read_unprefixed_process_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET", "unsafe-unprefixed-secret")

    with pytest.raises(ValidationError):
        cast(Any, RuntimeSettings)(_env_file=None)


def test_env_example_uses_runtime_prefix_for_application_settings() -> None:
    names = {
        line.partition("=")[0]
        for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }

    assert {
        "FOOTBALLPULSE_POSTGRES_DSN",
        "FOOTBALLPULSE_MONGODB_DSN",
        "FOOTBALLPULSE_REDIS_DSN",
        "FOOTBALLPULSE_KAFKA_BOOTSTRAP_SERVERS",
        "FOOTBALLPULSE_JWT_SECRET",
        "FOOTBALLPULSE_INTERNAL_API_TOKEN",
        "FOOTBALLPULSE_AI_PROVIDER",
    } <= names
    assert {"JWT_SECRET", "INTERNAL_API_TOKEN", "AI_PROVIDER"}.isdisjoint(names)

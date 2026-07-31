from typing import Annotated, Any, Literal
from urllib.parse import SplitResult, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MINIMUM_SECRET_LENGTH = 32
UNSAFE_SECRET_MARKERS = ("change-me", "replace-me", "example")


class RuntimeSettings(BaseSettings):
    """Cross-service runtime settings with explicit FootballPulse env names."""

    model_config = SettingsConfigDict(
        env_prefix="FOOTBALLPULSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    environment: Literal["local", "test", "demo"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    postgres_dsn: SecretStr
    mongodb_dsn: SecretStr
    redis_dsn: SecretStr
    kafka_bootstrap_servers: Annotated[tuple[str, ...], NoDecode]
    jwt_secret: SecretStr = Field(min_length=MINIMUM_SECRET_LENGTH)
    internal_api_token: SecretStr = Field(min_length=MINIMUM_SECRET_LENGTH)
    ai_provider: Literal["mock", "openai", "openrouter"] = "mock"
    openai_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None

    @field_validator("kafka_bootstrap_servers", mode="before")
    @classmethod
    def split_bootstrap_servers(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @model_validator(mode="after")
    def reject_placeholder_secrets(self) -> "RuntimeSettings":
        for name in ("jwt_secret", "internal_api_token"):
            value = getattr(self, name).get_secret_value().lower()
            if any(marker in value for marker in UNSAFE_SECRET_MARKERS):
                raise ValueError(f"{name} must not contain a placeholder marker")
        return self

    def safe_dump(self) -> dict[str, Any]:
        """Return diagnostics safe for logs and support output."""

        return {
            "environment": self.environment,
            "log_level": self.log_level,
            "postgres_dsn": _redact_dsn(self.postgres_dsn.get_secret_value()),
            "mongodb_dsn": _redact_dsn(self.mongodb_dsn.get_secret_value()),
            "redis_dsn": _redact_dsn(self.redis_dsn.get_secret_value()),
            "kafka_bootstrap_servers": self.kafka_bootstrap_servers,
            "jwt_secret": "**********",
            "internal_api_token": "**********",
            "ai_provider": self.ai_provider,
            "openai_api_key": "**********" if self.openai_api_key else None,
            "openrouter_api_key": "**********" if self.openrouter_api_key else None,
        }


def _redact_dsn(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.username is None and parsed.password is None:
        return value

    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    redacted = SplitResult(
        scheme=parsed.scheme,
        netloc=f"***:***@{hostname}{port}",
        path=parsed.path,
        query=parsed.query,
        fragment=parsed.fragment,
    )
    return urlunsplit(redacted)

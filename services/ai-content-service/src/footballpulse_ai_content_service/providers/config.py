from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from footballpulse_ai_content_service.providers.base import ProviderName, ProviderPolicy
from footballpulse_ai_content_service.providers.local import LocalModelSettings


def _boolean(values: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = values.get(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _integer(values: Mapping[str, str], name: str, default: int) -> int:
    raw = values.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    provider: ProviderName
    environment: str
    allow_local_fallback: bool
    local_model: LocalModelSettings | None

    @classmethod
    def from_environment(cls, values: Mapping[str, str]) -> ProviderSettings:
        environment = values.get("FOOTBALLPULSE_ENV", "local").strip().casefold()
        try:
            provider = ProviderName(values.get("FOOTBALLPULSE_AI_PROVIDER", "kaggle"))
        except ValueError:
            raise ValueError("FOOTBALLPULSE_AI_PROVIDER must be kaggle or local") from None
        allow_local = _boolean(values, "FOOTBALLPULSE_AI_ALLOW_LOCAL_FALLBACK")

        model_path = values.get("FOOTBALLPULSE_LOCAL_MODEL_PATH", "").strip()
        if (provider is ProviderName.LOCAL or allow_local) and not model_path:
            raise ValueError("FOOTBALLPULSE_LOCAL_MODEL_PATH is required for local inference")
        local_model = None
        if model_path:
            checksum = values.get("FOOTBALLPULSE_LOCAL_MODEL_SHA256", "").strip() or None
            local_model = LocalModelSettings(
                model_path=Path(model_path),
                model_sha256=checksum,
                model_version=values.get(
                    "FOOTBALLPULSE_LOCAL_MODEL_VERSION",
                    "Qwen3-4B-Instruct-GGUF-Q4_K_M",
                ),
                n_ctx=_integer(values, "FOOTBALLPULSE_LOCAL_MODEL_N_CTX", 8_192),
                n_threads=_integer(values, "FOOTBALLPULSE_LOCAL_MODEL_N_THREADS", 8),
            )
        return cls(
            provider,
            environment,
            allow_local,
            local_model,
        )

    def policy(self) -> ProviderPolicy:
        return ProviderPolicy(
            primary=self.provider,
            allow_local_fallback=self.allow_local_fallback,
        )

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_PREFIX = "FOOTBALLPULSE_"
_SECRET_MARKERS = ("KEY", "PASSWORD", "SECRET", "TOKEN")
_VALID_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    environment: str = "local"
    log_level: str = "INFO"
    timezone: str = "Asia/Ho_Chi_Minh"

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> RuntimeSettings:
        values = os.environ if environment is None else environment
        log_level = values.get("FOOTBALLPULSE_LOG_LEVEL", "INFO").upper()
        if log_level not in _VALID_LOG_LEVELS:
            raise ValueError(f"FOOTBALLPULSE_LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}")

        return cls(
            environment=values.get("FOOTBALLPULSE_ENV", "local"),
            log_level=log_level,
            timezone=values.get("FOOTBALLPULSE_TIMEZONE", "Asia/Ho_Chi_Minh"),
        )


def diagnostic_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    values = os.environ if environment is None else environment
    diagnostics = {
        name: "***" if any(marker in name.upper() for marker in _SECRET_MARKERS) else value
        for name, value in values.items()
        if name.startswith(_PREFIX)
    }
    return dict(sorted(diagnostics.items()))

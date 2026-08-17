from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import IO

_CONTEXT: ContextVar[dict[str, object] | None] = ContextVar(
    "footballpulse_log_context", default=None
)
_SECRET_MARKERS = ("authorization", "cookie", "credential", "key", "password", "secret", "token")
_SECRET_TEXT = re.compile(
    r"(?i)(authorization|cookie|credential|key|password|secret|token)\s*[:=]\s*\S+"
)


def _redact_value(name: str, value: object) -> object:
    if any(marker in name.casefold() for marker in _SECRET_MARKERS):
        return "***"
    if isinstance(value, Mapping):
        return {str(key): _redact_value(str(key), item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_redact_value(name, item) for item in value]
    if isinstance(value, str) and _SECRET_TEXT.search(value):
        return "***"
    return value


def _safe_fields(fields: Mapping[str, object]) -> dict[str, object]:
    return {name: _redact_value(name, value) for name, value in fields.items()}


@contextmanager
def bind_log_context(**fields: object) -> Iterator[None]:
    """Bind correlation fields to every log event within the current context."""

    token = _CONTEXT.set({**(_CONTEXT.get() or {}), **_safe_fields(fields)})
    try:
        yield
    finally:
        _CONTEXT.reset(token)


class JsonLogFormatter(logging.Formatter):
    """Render one machine-readable JSON object per log record."""

    def __init__(self, *, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "event_fields", {})
        payload: dict[str, object] = {
            "timestamp": (
                datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z")
            ),
            "level": record.levelname,
            "service": self._service,
            "logger": record.name,
            "event": getattr(record, "event_name", record.getMessage()),
            "correlation_id": "-",
            **(_CONTEXT.get() or {}),
            **fields,
        }
        return json.dumps(
            _safe_fields(payload),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )


def configure_logging(
    *,
    service: str,
    level: str = "INFO",
    stream: IO[str] | None = None,
    force: bool = False,
) -> None:
    """Configure immediate structured stdout logging for a service process."""

    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonLogFormatter(service=service))
    logging.basicConfig(level=level.upper(), handlers=[handler], force=force)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    error: BaseException | None = None,
    **fields: object,
) -> None:
    """Emit a stable event with allowlisted structured fields."""

    values = dict(fields)
    if error is not None:
        values["error_type"] = type(error).__name__
        values["error_detail"] = str(error)
    logger.log(
        level,
        event,
        extra={"event_name": event, "event_fields": _safe_fields(values)},
        exc_info=error if error is not None and level >= logging.ERROR else None,
    )

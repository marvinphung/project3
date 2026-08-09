from __future__ import annotations

from typing import Any

import pytest
from footballpulse_ai_content_service.providers.llama_cpp_runtime import LlamaCppRuntime
from footballpulse_ai_content_service.providers.local import (
    LocalGenerationTimeout,
    LocalRuntimeFatalError,
)


class FakeLlama:
    def __init__(self, *, content: str = '{"ok":true}') -> None:
        self.content = content
        self.kwargs: dict[str, Any] | None = None
        self.closed = False
        self.error: Exception | None = None
        self.before_return: Any = None

    def create_chat_completion(self, **kwargs: Any) -> dict[str, object]:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        if self.before_return is not None:
            self.before_return(kwargs)
        return {"choices": [{"message": {"content": self.content}}]}

    def close(self) -> None:
        self.closed = True


def test_runtime_requests_deterministic_json_schema_completion() -> None:
    client = FakeLlama()
    runtime = LlamaCppRuntime(client, monotonic=lambda: 10.0)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}

    output = runtime.complete(
        messages=[{"role": "user", "content": "input"}],
        response_schema=schema,
        max_tokens=2_500,
        timeout_seconds=300,
    )

    assert output == '{"ok":true}'
    assert client.kwargs is not None
    assert client.kwargs["temperature"] == 0.0
    assert client.kwargs["max_tokens"] == 2_500
    assert client.kwargs["response_format"] == {"type": "json_object", "schema": schema}
    assert len(client.kwargs["stopping_criteria"]) == 1


def test_runtime_stopping_criterion_enforces_deadline() -> None:
    now = [0.0]
    client = FakeLlama()

    def cross_deadline(kwargs: dict[str, Any]) -> None:
        now[0] = 6.0
        assert kwargs["stopping_criteria"][0](None, None) is True

    client.before_return = cross_deadline
    runtime = LlamaCppRuntime(client, monotonic=lambda: now[0])

    with pytest.raises(LocalGenerationTimeout):
        runtime.complete(
            messages=[{"role": "user", "content": "input"}],
            response_schema={"type": "object"},
            max_tokens=10,
            timeout_seconds=5,
        )


def test_runtime_wraps_native_failure_as_fatal_and_closes_client() -> None:
    client = FakeLlama()
    client.error = RuntimeError("native backend crashed")
    runtime = LlamaCppRuntime(client)

    with pytest.raises(LocalRuntimeFatalError, match="llama.cpp generation failed"):
        runtime.complete(
            messages=[{"role": "user", "content": "input"}],
            response_schema={"type": "object"},
            max_tokens=10,
            timeout_seconds=5,
        )

    runtime.close()
    assert client.closed is True

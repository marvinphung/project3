from __future__ import annotations

import importlib
from collections.abc import Callable
from time import monotonic
from typing import Any, Protocol

from footballpulse_ai_content_service.providers.local import (
    LocalGenerationTimeout,
    LocalModelSettings,
    LocalRuntimeFatalError,
)


class LlamaClient(Protocol):
    def create_chat_completion(self, **kwargs: Any) -> object: ...

    def close(self) -> None: ...


class LlamaCppRuntime:
    def __init__(
        self,
        client: LlamaClient,
        *,
        monotonic: Callable[[], float] = monotonic,
    ) -> None:
        self._client = client
        self._monotonic = monotonic

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any],
        max_tokens: int,
        timeout_seconds: float,
    ) -> str:
        deadline = self._monotonic() + timeout_seconds
        stopped_by_deadline = False

        def deadline_reached(*_: object) -> bool:
            nonlocal stopped_by_deadline
            stopped_by_deadline = self._monotonic() >= deadline
            return stopped_by_deadline

        try:
            response = self._client.create_chat_completion(
                messages=messages,
                response_format={"type": "json_object", "schema": response_schema},
                temperature=0.0,
                max_tokens=max_tokens,
                stopping_criteria=[deadline_reached],
            )
        except Exception as error:
            raise LocalRuntimeFatalError("llama.cpp generation failed") from error
        if stopped_by_deadline or self._monotonic() >= deadline:
            raise LocalGenerationTimeout("llama.cpp generation exceeded article deadline")
        return self._content(response)

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _content(response: object) -> str:
        if not isinstance(response, dict):
            raise LocalRuntimeFatalError("llama.cpp returned an invalid response envelope")
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise LocalRuntimeFatalError("llama.cpp response has no completion choice")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise LocalRuntimeFatalError("llama.cpp response choice has no message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LocalRuntimeFatalError("llama.cpp response content is empty")
        return content


class LlamaCppRuntimeFactory:
    def load(self, settings: LocalModelSettings) -> LlamaCppRuntime:
        module = importlib.import_module("llama_cpp")
        llama_class: Any = module.Llama
        client: LlamaClient = llama_class(
            model_path=str(settings.model_path.expanduser().resolve()),
            n_ctx=settings.n_ctx,
            n_threads=settings.n_threads,
            n_gpu_layers=0,
            verbose=False,
        )
        return LlamaCppRuntime(client)

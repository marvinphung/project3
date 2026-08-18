from __future__ import annotations

from collections.abc import Mapping

from footballpulse_ai_content_service.providers.base import EnrichmentProvider, ProviderName
from footballpulse_ai_content_service.providers.config import ProviderSettings
from footballpulse_ai_content_service.providers.llama_cpp_runtime import LlamaCppRuntimeFactory
from footballpulse_ai_content_service.providers.local import LocalModelManager, LocalQwenProvider


def build_provider(
    settings: ProviderSettings,
) -> EnrichmentProvider:
    """Assemble the configured provider lazily.

    Kaggle remains an orchestration adapter and is intentionally not silently
    replaced here.  Local model loading happens only on the first `enrich` call.
    """
    if settings.provider is ProviderName.LOCAL:
        if settings.local_model is None:
            raise ValueError("local provider requires local model settings")
        manager = LocalModelManager(settings.local_model, factory=LlamaCppRuntimeFactory())
        return LocalQwenProvider(manager=manager)
    raise RuntimeError(
        "Kaggle is executed by the batch coordinator; use provider=local "
        "for the in-process enrichment worker"
    )


def build_provider_from_environment(
    values: Mapping[str, str],
) -> EnrichmentProvider:
    return build_provider(ProviderSettings.from_environment(values))

from __future__ import annotations

from typing import Protocol

from pydantic import ValidationError

from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentOutput


class StructuralRepairer(Protocol):
    def repair(self, raw_output: str, validation_error: str) -> str: ...


class AIOutputInvalidError(ValueError):
    """Raised after the single structural repair budget is exhausted."""


def parse_output_with_one_repair(
    raw_output: str,
    *,
    repairer: StructuralRepairer,
) -> ArticleEnrichmentOutput:
    try:
        return ArticleEnrichmentOutput.model_validate_json(raw_output)
    except ValidationError as first_error:
        repaired = repairer.repair(raw_output, str(first_error))
    try:
        return ArticleEnrichmentOutput.model_validate_json(repaired)
    except ValidationError as final_error:
        raise AIOutputInvalidError("AI output remains invalid after one repair") from final_error

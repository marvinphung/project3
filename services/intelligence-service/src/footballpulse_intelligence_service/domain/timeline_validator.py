from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from footballpulse_intelligence_service.domain.timeline import TimelineEntry


class TimelineValidationCode(StrEnum):
    CLAIM_SET_MISMATCH = "CLAIM_SET_MISMATCH"
    SOURCE_SET_MISMATCH = "SOURCE_SET_MISMATCH"


@dataclass(frozen=True, slots=True)
class TimelineValidationResult:
    is_valid: bool
    codes: tuple[TimelineValidationCode, ...]


class TimelineValidator:
    def validate(
        self,
        entry: TimelineEntry,
        *,
        expected_claim_ids: tuple[UUID, ...],
        expected_source_article_ids: tuple[UUID, ...],
    ) -> TimelineValidationResult:
        codes: list[TimelineValidationCode] = []
        if set(entry.used_claim_ids) != set(expected_claim_ids):
            codes.append(TimelineValidationCode.CLAIM_SET_MISMATCH)
        if set(entry.source_article_ids) != set(expected_source_article_ids):
            codes.append(TimelineValidationCode.SOURCE_SET_MISMATCH)
        unique_codes = tuple(dict.fromkeys(codes))
        return TimelineValidationResult(not unique_codes, unique_codes)

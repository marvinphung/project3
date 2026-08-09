from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from footballpulse_ai_content_service.contracts.enrichment import (
    ClaimCertainty,
    Predicate,
)
from footballpulse_ai_content_service.contracts.presentation import VietnameseProjection
from footballpulse_ai_content_service.processing.claims import MergedClaim

_AMOUNT_PATTERN = re.compile(
    r"(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>triệu|million|tỷ|billion|bn)",
    re.IGNORECASE,
)
_CURRENCIES = {
    "EUR": ("eur", "euro", "€"),
    "GBP": ("gbp", "bảng", "£"),
    "USD": ("usd", "đô la", "dollar", "$"),
}
_NEGATION_MARKERS = ("phủ nhận", "không hề", "không có", "bác bỏ")
_CONFIRMATION_MARKERS = ("xác nhận", "chính thức", "đã ký")
_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SCORE_PATTERN = re.compile(r"\b\d{1,3}\s*[-–]\s*\d{1,3}\b")


class TranslationRejectionCode(StrEnum):
    UNKNOWN_CLAIM_ID = "UNKNOWN_CLAIM_ID"
    FACTUAL_ANCHOR_MISMATCH = "FACTUAL_ANCHOR_MISMATCH"
    ENTITY_MISMATCH = "ENTITY_MISMATCH"
    NEGATION_MISMATCH = "NEGATION_MISMATCH"
    CERTAINTY_MISMATCH = "CERTAINTY_MISMATCH"


@dataclass(frozen=True, slots=True)
class TranslationValidationResult:
    is_valid: bool
    codes: tuple[TranslationRejectionCode, ...]


def _extract_amounts(text: str) -> set[int]:
    amounts: set[int] = set()
    for match in _AMOUNT_PATTERN.finditer(text):
        raw_number = match.group("number").replace(",", ".")
        if len(raw_number) > 30:
            amounts.add(-1)
            continue
        try:
            number = Decimal(raw_number)
        except InvalidOperation:
            amounts.add(-1)
            continue
        multiplier = (
            1_000_000 if match.group("unit").casefold() in {"triệu", "million"} else 1_000_000_000
        )
        amounts.add(int(number * multiplier))
    return amounts


def _fold_entity_text(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )


class TranslationValidator:
    def validate(
        self,
        projection: VietnameseProjection,
        claims: tuple[MergedClaim, ...],
        *,
        entity_names: dict[UUID, str],
    ) -> TranslationValidationResult:
        claim_by_id = {claim.claim_id: claim for claim in claims}
        codes: list[TranslationRejectionCode] = []
        unknown_ids = set(projection.used_claim_ids) - claim_by_id.keys()
        if unknown_ids:
            codes.append(TranslationRejectionCode.UNKNOWN_CLAIM_ID)
        used_claims = [
            claim_by_id[claim_id]
            for claim_id in projection.used_claim_ids
            if claim_id in claim_by_id
        ]

        allowed_amounts = {
            claim.qualifiers.amount for claim in used_claims if claim.qualifiers.amount is not None
        }
        summary = projection.summary_vi.casefold()
        folded_summary = _fold_entity_text(summary)
        if not _extract_amounts(summary) <= allowed_amounts:
            codes.append(TranslationRejectionCode.FACTUAL_ANCHOR_MISMATCH)
        allowed_dates = {
            claim.qualifiers.date for claim in used_claims if claim.qualifiers.date is not None
        }
        allowed_scores = {
            claim.qualifiers.score.replace("–", "-")
            for claim in used_claims
            if claim.qualifiers.score is not None
        }
        found_scores = {
            re.sub(r"\s+", "", value.replace("–", "-")) for value in _SCORE_PATTERN.findall(summary)
        }
        if (
            not set(_DATE_PATTERN.findall(summary)) <= allowed_dates
            or not found_scores <= allowed_scores
        ):
            codes.append(TranslationRejectionCode.FACTUAL_ANCHOR_MISMATCH)
        for currency, aliases in _CURRENCIES.items():
            if any(alias in summary for alias in aliases) and not any(
                claim.qualifiers.currency == currency for claim in used_claims
            ):
                codes.append(TranslationRejectionCode.FACTUAL_ANCHOR_MISMATCH)
                break

        allowed_entity_ids = {
            entity_id
            for claim in used_claims
            for entity_id in (claim.subject_entity_id, claim.object_entity_id)
            if entity_id is not None
        }
        mentioned_entity_ids = {
            entity_id
            for entity_id, name in entity_names.items()
            if _fold_entity_text(name) in folded_summary
        }
        if not mentioned_entity_ids <= allowed_entity_ids:
            codes.append(TranslationRejectionCode.ENTITY_MISMATCH)

        if any(marker in summary for marker in _NEGATION_MARKERS) and not any(
            claim.certainty is ClaimCertainty.DENIED or claim.predicate is Predicate.DENIED_REPORT
            for claim in used_claims
        ):
            codes.append(TranslationRejectionCode.NEGATION_MISMATCH)
        if any(marker in summary for marker in _CONFIRMATION_MARKERS) and not any(
            claim.certainty is ClaimCertainty.CONFIRMED for claim in used_claims
        ):
            codes.append(TranslationRejectionCode.CERTAINTY_MISMATCH)

        unique_codes = tuple(dict.fromkeys(codes))
        return TranslationValidationResult(not unique_codes, unique_codes)

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from footballpulse_ai_content_service.contracts.enrichment import (
    ArticleEnrichmentInput,
    ArticleEnrichmentOutput,
    ClaimCertainty,
    ClaimOutput,
    EventType,
    Predicate,
)

_EVENT_PREDICATES = {
    EventType.TRANSFER: {
        Predicate.EXPRESSED_INTEREST,
        Predicate.CONTACTED,
        Predicate.SUBMITTED_BID,
        Predicate.ACCEPTED_BID,
        Predicate.REJECTED_BID,
        Predicate.COMPLETED_TRANSFER,
        Predicate.DENIED_REPORT,
    },
    EventType.CONTRACT: {
        Predicate.NEGOTIATING_CONTRACT,
        Predicate.SIGNED_CONTRACT,
        Predicate.DENIED_REPORT,
    },
    EventType.INJURY: {
        Predicate.SUFFERED_INJURY,
        Predicate.EXPECTED_RETURN,
        Predicate.DENIED_REPORT,
    },
    EventType.MATCH: {
        Predicate.MATCH_SCHEDULED,
        Predicate.MATCH_RESULT,
        Predicate.DENIED_REPORT,
    },
    EventType.MANAGERIAL: {
        Predicate.APPOINTED_COACH,
        Predicate.DISMISSED_COACH,
        Predicate.DENIED_REPORT,
    },
    EventType.DISCIPLINARY: set(),
    EventType.OTHER: set(),
}
_UNCERTAINTY_MARKERS = (
    "reportedly",
    "according to",
    "reports",
    "rumour",
    "rumor",
    "could",
    "may",
    "might",
    "considering",
)
_CONFIRMATION_MARKERS = (
    "confirmed",
    "official",
    "announced",
    "has signed",
    "have signed",
    "completed",
)
_DENIAL_MARKERS = ("denied", "dismissed the report", "not true", "no offer")
_NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")
_CURRENCY_ALIASES = {
    "EUR": ("eur", "euro", "euros", "€"),
    "GBP": ("gbp", "pound", "pounds", "£"),
    "USD": ("usd", "dollar", "dollars", "$"),
}


class ClaimRejectionCode(StrEnum):
    EVIDENCE_MISMATCH = "EVIDENCE_MISMATCH"
    UNKNOWN_ENTITY = "UNKNOWN_ENTITY"
    OBJECT_TEXT_NOT_IN_EVIDENCE = "OBJECT_TEXT_NOT_IN_EVIDENCE"
    EVENT_PREDICATE_MISMATCH = "EVENT_PREDICATE_MISMATCH"
    QUALIFIER_NOT_IN_EVIDENCE = "QUALIFIER_NOT_IN_EVIDENCE"
    CERTAINTY_OVERSTATED = "CERTAINTY_OVERSTATED"
    DENIAL_MISMATCH = "DENIAL_MISMATCH"


class GroundingStatus(StrEnum):
    VALIDATED = "VALIDATED"
    PARTIAL = "PARTIAL"
    NEEDS_CONTENT_REVIEW = "NEEDS_CONTENT_REVIEW"
    AI_OUTPUT_INVALID = "AI_OUTPUT_INVALID"


@dataclass(frozen=True, slots=True)
class RejectedClaim:
    index: int
    claim: ClaimOutput
    codes: tuple[ClaimRejectionCode, ...]


@dataclass(frozen=True, slots=True)
class GroundingResult:
    status: GroundingStatus
    valid_claims: tuple[ClaimOutput, ...]
    rejected_claims: tuple[RejectedClaim, ...]
    summary_en: str | None
    top_level_errors: tuple[str, ...]


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _amount_is_supported(amount: int, evidence: str) -> bool:
    normalized = _normalized(evidence).replace(",", "")
    candidates = {str(amount)}
    for divisor, suffixes in (
        (1_000, ("thousand", "k")),
        (1_000_000, ("million", "m")),
        (1_000_000_000, ("billion", "bn", "b")),
    ):
        if amount % divisor == 0:
            value = str(amount // divisor)
            candidates.update(f"{value} {suffix}" for suffix in suffixes)
            candidates.update(f"{value}{suffix}" for suffix in suffixes)
    return any(
        re.search(rf"(?<![\d.]){re.escape(candidate)}(?![\w.])", normalized)
        for candidate in candidates
    )


def _number_is_supported(number: str, evidence: str) -> bool:
    normalized_number = number.replace(",", "")
    return bool(
        re.search(
            rf"(?<![\d.]){re.escape(normalized_number)}(?![\d.])",
            evidence,
        )
    )


def _qualifiers_are_supported(claim: ClaimOutput) -> bool:
    evidence = _normalized(claim.evidence_quote)
    qualifiers = claim.qualifiers
    if qualifiers.amount is not None and not _amount_is_supported(qualifiers.amount, evidence):
        return False
    if qualifiers.currency is not None:
        aliases = _CURRENCY_ALIASES.get(qualifiers.currency, (qualifiers.currency.casefold(),))
        if not any(alias in evidence for alias in aliases):
            return False
    if qualifiers.date is not None and qualifiers.date.casefold() not in evidence:
        return False
    if qualifiers.injury is not None and _normalized(qualifiers.injury) not in evidence:
        return False
    if qualifiers.score is not None:
        normalized_score = re.sub(r"\s+", "", qualifiers.score.replace("–", "-"))
        normalized_evidence = re.sub(r"\s+", "", evidence.replace("–", "-"))
        if normalized_score not in normalized_evidence:
            return False
    return True


def _summary_is_supported(summary: str, claims: tuple[ClaimOutput, ...]) -> bool:
    normalized_summary = _normalized(summary)
    evidence = _normalized(" ".join(claim.evidence_quote for claim in claims)).replace(",", "")
    for number in _NUMBER_PATTERN.findall(normalized_summary):
        if not _number_is_supported(number, evidence):
            return False
    for currency, aliases in _CURRENCY_ALIASES.items():
        if any(alias in normalized_summary for alias in aliases) and not any(
            claim.qualifiers.currency == currency for claim in claims
        ):
            return False
    if any(marker in normalized_summary for marker in _CONFIRMATION_MARKERS) and not any(
        claim.certainty is ClaimCertainty.CONFIRMED for claim in claims
    ):
        return False
    return not (
        any(marker in normalized_summary for marker in _DENIAL_MARKERS)
        and not any(claim.certainty is ClaimCertainty.DENIED for claim in claims)
    )


class GroundingValidator:
    def validate(
        self,
        source: ArticleEnrichmentInput,
        output: ArticleEnrichmentOutput,
    ) -> GroundingResult:
        top_level_errors: list[str] = []
        if output.article_version_id != source.article_version_id:
            top_level_errors.append("ARTICLE_VERSION_ID_MISMATCH")
        if output.input_hash != source.input_hash:
            top_level_errors.append("INPUT_HASH_MISMATCH")
        if top_level_errors:
            return GroundingResult(
                GroundingStatus.AI_OUTPUT_INVALID,
                (),
                (),
                None,
                tuple(top_level_errors),
            )

        known_entity_ids = {entity.entity_id for entity in source.canonical_entities}
        valid_claims: list[ClaimOutput] = []
        rejected_claims: list[RejectedClaim] = []
        for index, claim in enumerate(output.claims):
            codes: list[ClaimRejectionCode] = []
            if (
                claim.evidence_end > len(source.cleaned_content)
                or source.cleaned_content[claim.evidence_start : claim.evidence_end]
                != claim.evidence_quote
            ):
                codes.append(ClaimRejectionCode.EVIDENCE_MISMATCH)
            if claim.subject_entity_id not in known_entity_ids or (
                claim.object_entity_id is not None
                and claim.object_entity_id not in known_entity_ids
            ):
                codes.append(ClaimRejectionCode.UNKNOWN_ENTITY)
            if claim.object_text is not None and _normalized(claim.object_text) not in _normalized(
                claim.evidence_quote
            ):
                codes.append(ClaimRejectionCode.OBJECT_TEXT_NOT_IN_EVIDENCE)
            if claim.predicate not in _EVENT_PREDICATES[output.event_type]:
                codes.append(ClaimRejectionCode.EVENT_PREDICATE_MISMATCH)
            if not _qualifiers_are_supported(claim):
                codes.append(ClaimRejectionCode.QUALIFIER_NOT_IN_EVIDENCE)

            evidence = _normalized(claim.evidence_quote)
            if claim.certainty is ClaimCertainty.CONFIRMED and (
                any(marker in evidence for marker in _UNCERTAINTY_MARKERS)
                or not any(marker in evidence for marker in _CONFIRMATION_MARKERS)
            ):
                codes.append(ClaimRejectionCode.CERTAINTY_OVERSTATED)
            is_denial_predicate = claim.predicate is Predicate.DENIED_REPORT
            is_denial_certainty = claim.certainty is ClaimCertainty.DENIED
            if is_denial_predicate != is_denial_certainty or (
                is_denial_predicate and not any(marker in evidence for marker in _DENIAL_MARKERS)
            ):
                codes.append(ClaimRejectionCode.DENIAL_MISMATCH)

            unique_codes = tuple(dict.fromkeys(codes))
            if unique_codes:
                rejected_claims.append(RejectedClaim(index, claim, unique_codes))
            else:
                valid_claims.append(claim)

        valid_claim_tuple = tuple(valid_claims)
        summary_supported = bool(valid_claims) and _summary_is_supported(
            output.summary_en,
            valid_claim_tuple,
        )
        if not valid_claims or not summary_supported:
            status = GroundingStatus.NEEDS_CONTENT_REVIEW
        elif rejected_claims:
            status = GroundingStatus.PARTIAL
        else:
            status = GroundingStatus.VALIDATED
        return GroundingResult(
            status,
            valid_claim_tuple,
            tuple(rejected_claims),
            output.summary_en if status is GroundingStatus.VALIDATED else None,
            () if summary_supported else ("SUMMARY_NOT_GROUNDED",),
        )

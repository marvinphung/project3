from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from footballpulse_intelligence_service.domain.story import Claim

_REASON_ORDER: Final = (
    "NEW_CLAIM",
    "CLAIM_SEMANTICS_CHANGED",
    "CONFIRMATION_CHANGED",
)


@dataclass(frozen=True, slots=True)
class MaterialChangeResult:
    changed: bool
    reason_codes: tuple[str, ...]


def _identity_key(claim: Claim) -> tuple[object, ...]:
    return (
        claim.story_id,
        claim.subject_entity_id,
        claim.predicate,
        claim.object_entity_id,
    )


def detect_material_change(
    existing_claims: tuple[Claim, ...],
    incoming_claims: tuple[Claim, ...],
) -> MaterialChangeResult:
    existing_by_fingerprint = {claim.fingerprint: claim for claim in existing_claims}
    existing_by_identity = {_identity_key(claim): claim for claim in existing_claims}
    reasons: set[str] = set()
    for incoming in incoming_claims:
        previous = existing_by_fingerprint.get(incoming.fingerprint)
        if previous is None:
            identity_match = existing_by_identity.get(_identity_key(incoming))
            if identity_match is None:
                reasons.add("NEW_CLAIM")
            else:
                reasons.add("CLAIM_SEMANTICS_CHANGED")
        elif previous.confirmation is not incoming.confirmation:
            reasons.add("CONFIRMATION_CHANGED")
    ordered = tuple(reason for reason in _REASON_ORDER if reason in reasons)
    return MaterialChangeResult(bool(ordered), ordered)

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from .mechanics_fidelity import assess_variant_mechanics

TACTICAL_CAPABILITY_CONTRACT_VERSION = "tactical-candidate-capabilities-2026-08-23-v1"
BASIC_INSTANT_TIMING_CAPABILITY = "INSTANT_TIMING_BASIC_LITERAL_DRAW_SCRY"


def _supports_basic_literal_instant_timing(context: Any, row: dict[str, object]) -> bool:
    if row.get("tier") != "TACTICAL_REQUIRED":
        return False
    if tuple(cast(list[str], row.get("reasons", []))) != ("instant_timing_not_mechanistic",):
        return False
    name = str(row.get("oracle_name", ""))
    card = context.cards.get(name)
    if card is None:
        return False
    profile = card.profile
    return (
        getattr(profile, "timing_window", None) == "instant"
        and (
            getattr(profile, "draw_count", None) is not None
            or getattr(profile, "scry_depth", None) is not None
        )
        and not (
            getattr(profile, "draw_count", None) is None
            and getattr(profile, "scry_depth", None) is None
        )
    )


def assess_tactical_variant_capabilities(
    context: Any,
    *,
    control: Sequence[str],
    candidate: Sequence[str],
    deck_hash: str | None = None,
) -> dict[str, object]:
    """Assess whether a variant's remaining blockers fit a bounded Tactical contract.

    This does not upgrade Structural fidelity. It only proves that all remaining blockers can be
    handed to an explicitly supported Tactical fixture. External/screening blockers stay blocked.
    """

    structural = assess_variant_mechanics(
        context,
        control=control,
        candidate=candidate,
        deck_hash=deck_hash,
    )
    covered: list[dict[str, object]] = []
    remaining: list[dict[str, object]] = []
    for row in cast(list[dict[str, object]], structural.get("blocked_cards", [])):
        if _supports_basic_literal_instant_timing(context, row):
            covered.append(
                {
                    "oracle_name": row.get("oracle_name"),
                    "direction": row.get("direction"),
                    "capability_id": BASIC_INSTANT_TIMING_CAPABILITY,
                }
            )
        else:
            remaining.append(row)

    fully_tactical_evaluable = bool(covered) and not remaining
    return {
        "schema_version": "1.0.0",
        "contract_version": TACTICAL_CAPABILITY_CONTRACT_VERSION,
        "deck_hash": deck_hash,
        "structural_route": structural.get("required_next_evidence_layer"),
        "tactical_capabilities_covered": covered,
        "remaining_blocked_cards": remaining,
        "tactical_evaluable": fully_tactical_evaluable,
        "required_next_evidence_layer": (
            "TACTICAL_EVIDENCE_AVAILABLE"
            if fully_tactical_evaluable
            else structural.get("required_next_evidence_layer")
        ),
        "truth_boundary": (
            "Bounded Tactical handoff only; never upgrades the variant to Structural confirmatory "
            "and never claims external-rules-engine validation."
        ),
    }


__all__ = [
    "BASIC_INSTANT_TIMING_CAPABILITY",
    "TACTICAL_CAPABILITY_CONTRACT_VERSION",
    "assess_tactical_variant_capabilities",
]

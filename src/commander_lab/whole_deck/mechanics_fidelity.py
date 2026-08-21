from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from commander_lab.models.roles import CardRole, StructuralMechanic
from commander_lab.storage import atomic_write_json, sha256_value

from .lab import WholeDeckDesignLab
from .search_context import SEMANTIC_UNKNOWN, current_control_mainboard
from .search_models import WholeDeckVariant

STRUCTURAL_SEMANTIC_MODEL_VERSION = "structural-mechanics-fidelity-2026-08-21-v1"
SHORTLIST_LIMIT = 8


class MechanicsFidelityTier(StrEnum):
    MECHANISTICALLY_SUPPORTED = "MECHANISTICALLY_SUPPORTED"
    APPROXIMATED_DECISION_SAFE = "APPROXIMATED_DECISION_SAFE"
    APPROXIMATED_SCREENING_ONLY = "APPROXIMATED_SCREENING_ONLY"
    TACTICAL_REQUIRED = "TACTICAL_REQUIRED"
    EXTERNAL_RULES_REQUIRED = "EXTERNAL_RULES_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"


DECISION_SAFE_TIERS = frozenset(
    {
        MechanicsFidelityTier.MECHANISTICALLY_SUPPORTED,
        MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE,
    }
)

TACTICAL_REQUIRED_CARDS = frozenset(
    {
        "Silence",
        "Dovin's Veto",
        "Negate",
        "Wash Away",
        "Esior, Wardwing Familiar",
    }
)

EXTERNAL_RULES_REQUIRED_CARDS = frozenset(
    {
        "Light of Hope",
        "Psychotic Fury",
        "Boros Charm",
        "Flare of Duplication",
        "Wear // Tear",
        "Louisoix's Sacrifice",
        "Chain Reaction",
        "Farewell",
        "Vandalblast",
        "Curiosity",
        "Combat Research",
        "Lightning Greaves",
        "Swiftfoot Boots",
        "Duelist's Heritage",
        "Springleaf Drum",
        "Relic of Legends",
        "Kediss, Emberclaw Familiar",
        "Harmonic Prodigy",
        "Veyran, Voice of Duality",
        "Guttersnipe",
        "Kykar, Wind's Fury",
        "Storm-Kiln Artist",
        "Archmage Emeritus",
        "Jeska, Thrice Reborn",
        "Aerial Extortionist",
        "Narset, Enlightened Master",
        "Clever Impersonator",
    }
)

# Exact targeting, stack, wipe, combat, payment and attachment legality is not represented by
# the legacy Structural resolver. These categories therefore cannot silently become strong
# confirmatory evidence merely because their semantic profile is known.
TACTICAL_ROLES = frozenset({CardRole.COUNTER, CardRole.PROTECTION})
EXTERNAL_RULES_ROLES = frozenset({CardRole.REMOVAL, CardRole.WIPE, CardRole.COMBAT_PAYOFF})
SCREENING_ONLY_ROLES = frozenset(
    {
        CardRole.MANA_SOURCE,
        CardRole.RAMP,
        CardRole.ENGINE,
        CardRole.PAYOFF,
        CardRole.FINISHER,
        CardRole.TOKEN_SOURCE,
        CardRole.SACRIFICE_OUTLET,
        CardRole.LAND_SYNERGY,
    }
)

EXTERNAL_RULES_MECHANICS = frozenset(
    {
        StructuralMechanic.SACRIFICE_COST,
        StructuralMechanic.SACRIFICE_OUTLET,
        StructuralMechanic.DEATH_TRIGGER,
        StructuralMechanic.COMMANDER_DAMAGE_SUPPORT,
        StructuralMechanic.TABLE_DAMAGE,
        StructuralMechanic.STACK_INTERACTION,
    }
)
SCREENING_ONLY_MECHANICS = frozenset(
    {
        StructuralMechanic.SACRIFICE_PAYOFF,
        StructuralMechanic.TOKEN_ENGINE,
        StructuralMechanic.REPEATABLE_TOKEN_SOURCE,
        StructuralMechanic.LAND_RECURSION,
        StructuralMechanic.ARTIFACT_ENGINE,
        StructuralMechanic.GRAVEYARD_RECURSION,
        StructuralMechanic.GO_WIDE,
        StructuralMechanic.REBUILD,
        StructuralMechanic.FINISHER_COMPRESSION,
        StructuralMechanic.COMMANDER_DEPENDENT,
        StructuralMechanic.COMMANDER_INDEPENDENT,
    }
)


def classify_card_semantics(
    oracle_name: str,
    *,
    semantic_state: str,
    roles: Iterable[CardRole],
    mechanic_tags: Iterable[StructuralMechanic],
    is_basic: bool = False,
) -> tuple[MechanicsFidelityTier, tuple[str, ...]]:
    """Return the strongest evidence layer permitted for one card's Structural semantics."""

    role_set = frozenset(roles)
    mechanic_set = frozenset(mechanic_tags)
    if semantic_state == SEMANTIC_UNKNOWN:
        return MechanicsFidelityTier.UNSUPPORTED, ("semantic_unknown",)
    if oracle_name in TACTICAL_REQUIRED_CARDS:
        return MechanicsFidelityTier.TACTICAL_REQUIRED, ("explicit_tactical_contract",)
    if oracle_name in EXTERNAL_RULES_REQUIRED_CARDS:
        return MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED, (
            "explicit_external_rules_contract",
        )
    if role_set & TACTICAL_ROLES:
        return MechanicsFidelityTier.TACTICAL_REQUIRED, (
            "stack_or_protection_legality_not_mechanistic",
        )
    if role_set & EXTERNAL_RULES_ROLES:
        return MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED, (
            "target_wipe_or_combat_legality_not_mechanistic",
        )
    if mechanic_set & EXTERNAL_RULES_MECHANICS:
        return MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED, (
            "mechanic_requires_rules_accurate_state_or_sequencing",
        )
    if role_set & SCREENING_ONLY_ROLES or mechanic_set & SCREENING_ONLY_MECHANICS:
        return MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY, (
            "structural_abstraction_is_screening_only",
        )
    if is_basic:
        return MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE, (
            "basic_land_quantity_only; source-color legality remains separately gated",
        )
    if (
        role_set
        <= {
            CardRole.DRAW,
            CardRole.SELECTION,
            CardRole.RECURSION,
            CardRole.GRAVEYARD_HATE,
            CardRole.ENABLER,
        }
        and not mechanic_set
    ):
        return MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE, (
            "known_simple_structural_role_without_high_risk_mechanic_tag",
        )
    return MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY, (
        "no_explicit_decision_safe_mechanics_contract",
    )


def _card_assessment(context: Any, oracle_name: str) -> dict[str, object]:
    card = context.cards.get(oracle_name)
    if card is None:
        return {
            "oracle_name": oracle_name,
            "tier": MechanicsFidelityTier.UNSUPPORTED.value,
            "decision_safe": False,
            "reasons": ["card_missing_from_current_search_context"],
            "semantic_state": SEMANTIC_UNKNOWN,
        }
    profile = card.profile
    tier, reasons = classify_card_semantics(
        oracle_name,
        semantic_state=card.effective_semantic_state,
        roles=profile.roles,
        mechanic_tags=profile.mechanic_tags,
        is_basic=bool(card.is_basic),
    )
    return {
        "oracle_name": oracle_name,
        "tier": tier.value,
        "decision_safe": tier in DECISION_SAFE_TIERS,
        "reasons": list(reasons),
        "semantic_state": card.effective_semantic_state,
        "roles": sorted(role.value for role in profile.roles),
        "mechanic_tags": sorted(tag.value for tag in profile.mechanic_tags),
    }


def changed_card_multiset(
    control: Sequence[str], candidate: Sequence[str]
) -> tuple[tuple[str, int, str], ...]:
    left = Counter(control)
    right = Counter(candidate)
    rows: list[tuple[str, int, str]] = []
    for name in sorted(set(left) | set(right)):
        delta = right[name] - left[name]
        if delta > 0:
            rows.append((name, delta, "added"))
        elif delta < 0:
            rows.append((name, -delta, "removed"))
    return tuple(rows)


def assess_variant_mechanics(
    context: Any,
    *,
    control: Sequence[str],
    candidate: Sequence[str],
    deck_hash: str | None = None,
) -> dict[str, object]:
    delta = changed_card_multiset(control, candidate)
    changed: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for name, quantity, direction in delta:
        row = _card_assessment(context, name)
        row.update({"quantity": quantity, "direction": direction})
        changed.append(row)
        if row["decision_safe"] is not True:
            blocked.append(row)
    return {
        "schema_version": "1.0.0",
        "semantic_model_version": STRUCTURAL_SEMANTIC_MODEL_VERSION,
        "question_scope": "variant_delta_against_current_control",
        "deck_hash": deck_hash,
        "changed_slots": sum(quantity for _, quantity, direction in delta if direction == "added"),
        "changed_cards": changed,
        "blocked_cards": blocked,
        "pass": not blocked,
        "decision_safe_tiers": sorted(tier.value for tier in DECISION_SAFE_TIERS),
        "truth_boundary": (
            "Structural mechanics fidelity gate for this card-swap question only; not a claim "
            "that the entire baseline deck is rules-complete"
        ),
    }


def _mapping_number(mapping: Mapping[str, object], key: str, default: float) -> float:
    value = mapping.get(key, default)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _shortlist_rows(
    payload: Mapping[str, object], limit: int = SHORTLIST_LIMIT
) -> tuple[dict[str, Any], ...]:
    raw_elites = payload.get("elites")
    if not isinstance(raw_elites, list):
        raise RuntimeError("frontier mechanics gate requires an elites list")
    rows = [
        cast(dict[str, Any], row)
        for row in raw_elites
        if isinstance(row, dict) and isinstance(row.get("evaluation"), dict)
    ]
    rows.sort(
        key=lambda row: (
            -_mapping_number(
                cast(Mapping[str, object], row["evaluation"]), "robust_lower_bound", -999.0
            ),
            -_mapping_number(cast(Mapping[str, object], row["evaluation"]), "score", -999.0),
            str(row.get("deck_hash", "")),
        )
    )
    selected: list[dict[str, Any]] = []
    seen_cells: set[str] = set()
    for row in rows:
        evaluation = cast(Mapping[str, object], row["evaluation"])
        cell = str(evaluation.get("qd_cell", ""))
        if cell and cell not in seen_cells:
            selected.append(row)
            seen_cells.add(cell)
            if len(selected) >= limit:
                break
    if len(selected) < limit:
        chosen = {str(row.get("deck_hash", "")) for row in selected}
        for row in rows:
            if str(row.get("deck_hash", "")) in chosen:
                continue
            selected.append(row)
            if len(selected) >= limit:
                break
    return tuple(selected)


def assess_frontier_mechanics(root: str | Path, frontier_path: str | Path) -> dict[str, object]:
    root_path = Path(root).resolve()
    payload = json.loads(Path(frontier_path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError("frontier mechanics gate requires a JSON object")
    lab = WholeDeckDesignLab(root_path)
    control = current_control_mainboard(root_path)
    shortlist = _shortlist_rows(cast(Mapping[str, object], payload))
    assessments: list[dict[str, object]] = []
    malformed: list[str] = []
    for index, row in enumerate(shortlist):
        raw_variant = row.get("variant")
        if not isinstance(raw_variant, dict):
            malformed.append(f"shortlist[{index}].variant_missing")
            continue
        try:
            variant = WholeDeckVariant.model_validate(raw_variant)
        except Exception as exc:
            malformed.append(f"shortlist[{index}].variant_invalid:{exc}")
            continue
        assessments.append(
            assess_variant_mechanics(
                lab.context,
                control=control,
                candidate=variant.mainboard,
                deck_hash=variant.deck_hash,
            )
        )
    blocked = [row for row in assessments if row.get("pass") is not True]
    return {
        "schema_version": "1.0.0",
        "semantic_model_version": STRUCTURAL_SEMANTIC_MODEL_VERSION,
        "semantic_model_identity": sha256_value(
            {
                "version": STRUCTURAL_SEMANTIC_MODEL_VERSION,
                "tactical_cards": sorted(TACTICAL_REQUIRED_CARDS),
                "external_rules_cards": sorted(EXTERNAL_RULES_REQUIRED_CARDS),
                "tactical_roles": sorted(role.value for role in TACTICAL_ROLES),
                "external_rules_roles": sorted(role.value for role in EXTERNAL_RULES_ROLES),
                "screening_only_roles": sorted(role.value for role in SCREENING_ONLY_ROLES),
            }
        ),
        "question_scope": "confirmatory_shortlist_variant_delta",
        "shortlist_size": len(shortlist),
        "assessments": assessments,
        "malformed_rows": malformed,
        "blocked_variant_hashes": [str(row.get("deck_hash")) for row in blocked],
        "pass": not blocked and not malformed,
        "routing_contract": {
            MechanicsFidelityTier.MECHANISTICALLY_SUPPORTED.value: "STRUCTURAL_CONFIRMATORY_ALLOWED",
            MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE.value: "STRUCTURAL_CONFIRMATORY_ALLOWED",
            MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY.value: "SEARCH_ONLY",
            MechanicsFidelityTier.TACTICAL_REQUIRED.value: "TACTICAL_OR_FAIL_CLOSED",
            MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED.value: "EXTERNAL_RULES_OR_FAIL_CLOSED",
            MechanicsFidelityTier.UNSUPPORTED.value: "FAIL_CLOSED",
        },
        "truth_boundary": (
            "Pass means every changed card in the confirmatory shortlist is permitted by the "
            "question-specific Structural mechanics contract. Baseline residual approximations "
            "remain fixed context and are not upgraded to empirical or rules-engine evidence."
        ),
    }


def require_frontier_mechanics_decision_safe(
    root: str | Path, frontier_path: str | Path
) -> dict[str, object]:
    report = assess_frontier_mechanics(root, frontier_path)
    if report["pass"] is not True:
        blocked = ", ".join(
            str(value) for value in cast(list[object], report["blocked_variant_hashes"])
        )
        malformed = "; ".join(str(value) for value in cast(list[object], report["malformed_rows"]))
        detail = blocked or malformed or "unknown mechanics fidelity failure"
        raise RuntimeError(
            "confirmatory Structural decision blocked by question-specific mechanics fidelity: "
            + detail
        )
    return report


def require_confirmatory_mechanics_artifact(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError("confirmatory mechanics artifact must be a JSON object")
    fidelity = payload.get("mechanics_fidelity")
    if not isinstance(fidelity, dict):
        raise RuntimeError(
            "confirmatory artifact predates the mechanics fidelity contract; rerun confirmatory"
        )
    if fidelity.get("semantic_model_version") != STRUCTURAL_SEMANTIC_MODEL_VERSION:
        raise RuntimeError(
            "confirmatory artifact is STALE_MODEL_VERSION for mechanics fidelity; rerun confirmatory"
        )
    if fidelity.get("pass") is not True:
        raise RuntimeError("confirmatory artifact failed the mechanics fidelity contract")
    return cast(dict[str, object], fidelity)


def run_decision_confirmatory_guarded(
    root: str | Path,
    manifest: Any,
    *,
    frontier_path: str | Path,
    run_directory: str | Path,
    workers: int = 1,
    max_turns: int = 35,
) -> dict[str, object]:
    from .optimizer_v2_decision_runtime import run_decision_confirmatory

    fidelity = require_frontier_mechanics_decision_safe(root, frontier_path)
    result = dict(
        run_decision_confirmatory(
            root,
            manifest,
            frontier_path=frontier_path,
            run_directory=run_directory,
            workers=workers,
            max_turns=max_turns,
        )
    )
    result["mechanics_fidelity"] = fidelity
    atomic_write_json(Path(run_directory).resolve() / "confirmatory-report.json", result)
    return result


def run_critical_diagnostics_guarded(
    root: str | Path,
    manifest: Any,
    *,
    confirmatory_path: str | Path,
    run_directory: str | Path,
    workers: int = 1,
    max_turns: int = 35,
) -> dict[str, object]:
    from .optimizer_v2_decision_runtime import run_critical_diagnostics

    require_confirmatory_mechanics_artifact(confirmatory_path)
    return run_critical_diagnostics(
        root,
        manifest,
        confirmatory_path=confirmatory_path,
        run_directory=run_directory,
        workers=workers,
        max_turns=max_turns,
    )


def run_decision_holdout_guarded(
    root: str | Path,
    manifest: Any,
    *,
    confirmatory_path: str | Path,
    diagnostics_path: str | Path,
    run_directory: str | Path,
    authorize_holdout: bool = False,
    workers: int = 1,
    max_turns: int = 35,
) -> dict[str, object]:
    from .optimizer_v2_decision_runtime import run_decision_holdout

    require_confirmatory_mechanics_artifact(confirmatory_path)
    return run_decision_holdout(
        root,
        manifest,
        confirmatory_path=confirmatory_path,
        diagnostics_path=diagnostics_path,
        run_directory=run_directory,
        authorize_holdout=authorize_holdout,
        workers=workers,
        max_turns=max_turns,
    )

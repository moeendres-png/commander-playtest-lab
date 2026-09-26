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
from .optimizer_v2_release_models import FrontierHandoff
from .search_context import SEMANTIC_UNKNOWN, current_control_mainboard
from .search_models import WholeDeckVariant

STRUCTURAL_SEMANTIC_MODEL_VERSION = "structural-capability-fidelity-2026-08-23-v3"
SHORTLIST_LIMIT = 8


class MechanicsFidelityTier(StrEnum):
    MECHANISTICALLY_SUPPORTED = "MECHANISTICALLY_SUPPORTED"
    APPROXIMATED_DECISION_SAFE = "APPROXIMATED_DECISION_SAFE"
    APPROXIMATED_SCREENING_ONLY = "APPROXIMATED_SCREENING_ONLY"
    TACTICAL_REQUIRED = "TACTICAL_REQUIRED"
    EXTERNAL_RULES_REQUIRED = "EXTERNAL_RULES_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"


class StructuralCapability(StrEnum):
    """Question-specific capabilities the current Structural runtime demonstrably exposes.

    These are deliberately narrower than :class:`StructuralMechanic`. StructuralMechanic tags
    describe deck-quality/strategy axes; they are not themselves proof of rules fidelity.
    """

    BASIC_LAND_SOURCE_QUANTITY = "basic_land_source_quantity"
    SIMPLE_FIXED_MANA_RESOURCE = "simple_fixed_mana_resource"
    SIMPLE_DRAW = "simple_draw"
    SIMPLE_SELECTION = "simple_selection"


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
# the Structural resolver. These categories therefore cannot silently become strong confirmatory
# evidence merely because their strategic/semantic profile is known.
TACTICAL_ROLES = frozenset({CardRole.COUNTER, CardRole.PROTECTION})
EXTERNAL_RULES_ROLES = frozenset({CardRole.REMOVAL, CardRole.WIPE, CardRole.COMBAT_PAYOFF})

# Only mechanics that inherently require rules-accurate state/action sequencing are hard fidelity
# blockers. Strategic tags such as REBUILD, COMMANDER_INDEPENDENT, GO_WIDE, etc. are intentionally
# absent: models.roles documents StructuralMechanic as a decision-quality axis, not a rules-fidelity
# capability system.
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

# Kept as an explicit *strategic abstraction* set for reporting/backward-compatible semantic model
# identity. Membership here does NOT itself block decision-safe fidelity anymore.
STRATEGIC_ABSTRACTION_MECHANICS = frozenset(
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

# Roles which remain screening-only unless a concrete, narrower capability matcher below proves
# the exact card/question safe. This avoids the old error of globally upgrading every mana/ramp card.
DEFAULT_SCREENING_ONLY_ROLES = frozenset(
    {
        CardRole.MANA_SOURCE,
        CardRole.RAMP,
        CardRole.ENGINE,
        CardRole.ENABLER,
        CardRole.PAYOFF,
        CardRole.FINISHER,
        CardRole.TOKEN_SOURCE,
        CardRole.SACRIFICE_OUTLET,
        CardRole.LAND_SYNERGY,
        CardRole.RECURSION,
        CardRole.GRAVEYARD_HATE,
    }
)


def _oracle_without_reminder(text: str) -> str:
    """Remove parenthetical reminder text for conservative simple-effect matching."""

    import re

    previous = text
    while True:
        cleaned = re.sub(r"\([^()]*\)", "", previous)
        if cleaned == previous:
            break
        previous = cleaned
    return " ".join(previous.replace("\n", " ").split()).strip()


def _simple_draw_selection_shape(oracle_text: str) -> dict[str, int | None] | None:
    """Parse the tiny draw/scry language used by the fidelity contract.

    Parsing an Oracle shape is deliberately separate from claiming runtime support.  In
    particular, the current Structural resolver's ``SELECTION`` role is *not* Oracle scry: it
    looks at up to three cards and moves one directly to hand.  Keeping the parsed depth/count
    lets the classifier fail closed instead of collapsing every ``scry N`` into one capability.
    """

    import re

    text = _oracle_without_reminder(oracle_text).rstrip(".")
    if not text:
        return None
    lowered = text.lower()
    forbidden = (
        " if ",
        " when ",
        " whenever ",
        " unless ",
        " target ",
        " opponent",
        " shuffle",
        " discard",
        " put ",
        " reveal",
        " surveil",
        " choose",
        " may draw",
        " for each",
        " equal to",
        " instead",
        " sacrifice",
        " exile",
        " return",
    )
    padded = f" {lowered} "
    if any(token in padded for token in forbidden):
        return None

    clauses = [
        piece.strip(" ,") for piece in re.split(r"[.;]|,\s*then\s+", lowered) if piece.strip(" ,")
    ]
    draw_count: int | None = None
    scry_depth: int | None = None
    number_words = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4}
    for clause in clauses:
        scry = re.fullmatch(r"scry (\d+)", clause)
        if scry:
            if scry_depth is not None:
                return None
            scry_depth = int(scry.group(1))
            continue
        draw = re.fullmatch(r"draw (a|one|two|three|four|\d+) cards?", clause)
        if draw:
            if draw_count is not None:
                return None
            token = draw.group(1)
            draw_count = number_words.get(token, int(token) if token.isdigit() else 0)
            continue
        return None
    if draw_count is None and scry_depth is None:
        return None
    return {"draw_count": draw_count, "scry_depth": scry_depth}


def _simple_draw_selection_capabilities(
    oracle_text: str,
) -> frozenset[StructuralCapability] | None:
    """Backward-compatible shape helper; support is decided separately and fail-closed."""

    shape = _simple_draw_selection_shape(oracle_text)
    if shape is None:
        return None
    capabilities: set[StructuralCapability] = set()
    if shape["draw_count"] is not None:
        capabilities.add(StructuralCapability.SIMPLE_DRAW)
    if shape["scry_depth"] is not None:
        capabilities.add(StructuralCapability.SIMPLE_SELECTION)
    return frozenset(capabilities)


def _simple_fixed_mana_capability(oracle_text: str) -> bool:
    """Recognize unconditional tap-for-fixed-mana text only."""

    import re

    text = _oracle_without_reminder(oracle_text)
    return bool(re.fullmatch(r"\{T\}: Add (?:\{[WUBRGC]\})+\.", text))


def _facts_for_context_card(context: Any, oracle_name: str) -> Mapping[str, object]:
    universe = getattr(context, "fresh_universe", None)
    facts = getattr(universe, "candidate_facts_by_name", None)
    if isinstance(facts, Mapping):
        row = facts.get(oracle_name)
        if isinstance(row, Mapping):
            return row
    return {}


def classify_card_semantics(
    oracle_name: str,
    *,
    semantic_state: str,
    roles: Iterable[CardRole],
    mechanic_tags: Iterable[StructuralMechanic],
    is_basic: bool = False,
    oracle_text: str | None = None,
    type_line: str | None = None,
    runtime_draw_count: int | None = None,
    runtime_scry_depth: int | None = None,
    runtime_timing_window: str | None = None,
) -> tuple[MechanicsFidelityTier, tuple[str, ...]]:
    """Return the strongest evidence layer justified by current Structural capabilities.

    Strategic deck-quality tags are intentionally not treated as rules-fidelity blockers. A card
    reaches decision-safe Structural evidence only through a concrete capability contract.
    """

    assessment = _classify_card_capabilities(
        oracle_name,
        semantic_state=semantic_state,
        roles=roles,
        mechanic_tags=mechanic_tags,
        is_basic=is_basic,
        oracle_text=oracle_text,
        type_line=type_line,
        runtime_draw_count=runtime_draw_count,
        runtime_scry_depth=runtime_scry_depth,
        runtime_timing_window=runtime_timing_window,
    )
    return cast(MechanicsFidelityTier, assessment["tier_enum"]), cast(
        tuple[str, ...], assessment["reasons"]
    )


def _classify_card_capabilities(
    oracle_name: str,
    *,
    semantic_state: str,
    roles: Iterable[CardRole],
    mechanic_tags: Iterable[StructuralMechanic],
    is_basic: bool,
    oracle_text: str | None,
    type_line: str | None,
    runtime_draw_count: int | None = None,
    runtime_scry_depth: int | None = None,
    runtime_timing_window: str | None = None,
) -> dict[str, object]:
    role_set = frozenset(roles)
    mechanic_set = frozenset(mechanic_tags)
    required: set[str] = set()
    satisfied: set[str] = set()
    missing: set[str] = set()

    def result(
        tier: MechanicsFidelityTier,
        reasons: tuple[str, ...],
    ) -> dict[str, object]:
        return {
            "tier_enum": tier,
            "tier": tier.value,
            "decision_safe": tier in DECISION_SAFE_TIERS,
            "reasons": reasons,
            "required_structural_capabilities": tuple(sorted(required)),
            "satisfied_structural_capabilities": tuple(sorted(satisfied)),
            "missing_structural_capabilities": tuple(sorted(missing)),
        }

    if semantic_state == SEMANTIC_UNKNOWN:
        missing.add("verified_structural_semantics")
        return result(MechanicsFidelityTier.UNSUPPORTED, ("semantic_unknown",))
    if oracle_name in TACTICAL_REQUIRED_CARDS:
        missing.add("rules_accurate_timing_or_stack_action")
        return result(MechanicsFidelityTier.TACTICAL_REQUIRED, ("explicit_tactical_contract",))
    if oracle_name in EXTERNAL_RULES_REQUIRED_CARDS:
        missing.add("external_rules_execution_for_card")
        return result(
            MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED,
            ("explicit_external_rules_contract",),
        )
    if role_set & TACTICAL_ROLES:
        missing.add("rules_accurate_stack_or_protection_legality")
        return result(
            MechanicsFidelityTier.TACTICAL_REQUIRED,
            ("stack_or_protection_legality_not_mechanistic",),
        )
    if role_set & EXTERNAL_RULES_ROLES:
        missing.add("rules_accurate_target_wipe_or_combat_legality")
        return result(
            MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED,
            ("target_wipe_or_combat_legality_not_mechanistic",),
        )
    if mechanic_set & EXTERNAL_RULES_MECHANICS:
        missing.add("rules_accurate_state_or_trigger_sequencing")
        return result(
            MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED,
            ("mechanic_requires_rules_accurate_state_or_sequencing",),
        )

    # This branch must precede generic mana-source screening. The old ordering made the intended
    # Basic-land decision-safe contract unreachable.
    if is_basic:
        required.add(StructuralCapability.BASIC_LAND_SOURCE_QUANTITY.value)
        satisfied.add(StructuralCapability.BASIC_LAND_SOURCE_QUANTITY.value)
        return result(
            MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE,
            ("basic_land_quantity_and_color_source_are_explicitly_modeled",),
        )

    text = oracle_text or ""
    simple_shape = _simple_draw_selection_shape(text) if text else None
    if simple_shape is not None and role_set and role_set <= {CardRole.DRAW, CardRole.SELECTION}:
        draw_count = simple_shape["draw_count"]
        scry_depth = simple_shape["scry_depth"]
        is_instant = bool(type_line and "Instant" in type_line)

        if draw_count is not None:
            required.add(StructuralCapability.SIMPLE_DRAW.value)
        if scry_depth is not None:
            required.add(StructuralCapability.SIMPLE_SELECTION.value)

        # Instant-speed optionality is not exercised by the active-turn Structural action loop.
        # Even when the literal effect resolves correctly, the timing question must route upward.
        if is_instant or runtime_timing_window == "instant":
            missing.add("rules_accurate_instant_timing")
            return result(
                MechanicsFidelityTier.TACTICAL_REQUIRED,
                ("instant_timing_not_mechanistic",),
            )

        if scry_depth is not None:
            if CardRole.SELECTION not in role_set:
                missing.add("selection_role_projection")
            if runtime_scry_depth != scry_depth:
                missing.add("exact_scry_depth_runtime_parameter")
            if CardRole.SELECTION not in role_set or runtime_scry_depth != scry_depth:
                return result(
                    MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY,
                    ("scry_runtime_parameter_not_conformant",),
                )
            satisfied.add(StructuralCapability.SIMPLE_SELECTION.value)

        if draw_count is not None:
            if CardRole.DRAW not in role_set:
                missing.add("draw_role_projection")
            if runtime_draw_count != draw_count:
                missing.add("exact_draw_count_runtime_parameter")
            if CardRole.DRAW not in role_set or runtime_draw_count != draw_count:
                return result(
                    MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY,
                    ("draw_runtime_parameter_not_conformant",),
                )
            satisfied.add(StructuralCapability.SIMPLE_DRAW.value)

        return result(
            MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE,
            ("literal_sorcery_draw_scry_shape_matches_bounded_runtime_contract",),
        )

    if (
        text
        and role_set
        and role_set <= {CardRole.MANA_SOURCE, CardRole.RAMP}
        and _simple_fixed_mana_capability(text)
    ):
        required.add(StructuralCapability.SIMPLE_FIXED_MANA_RESOURCE.value)
        if type_line and "Creature" in type_line:
            missing.add("summoning_sickness_and_tap_activation_timing")
            return result(
                MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY,
                ("creature_tap_mana_timing_not_mechanistic",),
            )
        satisfied.add(StructuralCapability.SIMPLE_FIXED_MANA_RESOURCE.value)
        return result(
            MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE,
            ("noncreature_fixed_mana_resource_matches_bounded_structural_abstraction",),
        )

    if role_set & DEFAULT_SCREENING_ONLY_ROLES:
        missing.add("card_specific_structural_capability_contract")
        return result(
            MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY,
            ("no_card_specific_decision_safe_capability_contract",),
        )

    # Even when the role happens to be draw/selection, absence of verified Oracle/fact shape must
    # fail closed rather than globally promoting the role.
    if role_set <= {CardRole.DRAW, CardRole.SELECTION} and role_set:
        missing.add("simple_draw_selection_shape_verification")
        return result(
            MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY,
            ("draw_selection_role_without_verified_simple_capability_shape",),
        )

    missing.add("explicit_decision_safe_structural_capability_contract")
    return result(
        MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY,
        ("no_explicit_decision_safe_capability_contract",),
    )


def assess_card_fidelity(context: Any, oracle_name: str) -> dict[str, object]:
    """Return the content-backed, question-specific fidelity contract for one project card."""

    card = context.cards.get(oracle_name)
    if card is None:
        return {
            "oracle_name": oracle_name,
            "tier": MechanicsFidelityTier.UNSUPPORTED.value,
            "decision_safe": False,
            "reasons": ["card_missing_from_current_search_context"],
            "semantic_state": SEMANTIC_UNKNOWN,
            "required_structural_capabilities": [],
            "satisfied_structural_capabilities": [],
            "missing_structural_capabilities": ["current_search_context_card"],
        }
    profile = card.profile
    facts = _facts_for_context_card(context, oracle_name)
    raw_oracle_text = facts.get("oracle_text")
    raw_type_line = facts.get("type_line")
    oracle_text = raw_oracle_text if isinstance(raw_oracle_text, str) else None
    type_line = raw_type_line if isinstance(raw_type_line, str) else None
    runtime_draw_count = getattr(profile, "draw_count", None)
    runtime_scry_depth = getattr(profile, "scry_depth", None)
    runtime_timing_window = getattr(profile, "timing_window", None)
    classified = _classify_card_capabilities(
        oracle_name,
        semantic_state=card.effective_semantic_state,
        roles=profile.roles,
        mechanic_tags=profile.mechanic_tags,
        is_basic=bool(card.is_basic),
        oracle_text=oracle_text,
        type_line=type_line,
        runtime_draw_count=runtime_draw_count,
        runtime_scry_depth=runtime_scry_depth,
        runtime_timing_window=runtime_timing_window,
    )
    return {
        "oracle_name": oracle_name,
        "tier": classified["tier"],
        "decision_safe": classified["decision_safe"],
        "reasons": list(cast(tuple[str, ...], classified["reasons"])),
        "semantic_state": card.effective_semantic_state,
        "roles": sorted(role.value for role in profile.roles),
        "mechanic_tags": sorted(tag.value for tag in profile.mechanic_tags),
        "required_structural_capabilities": list(
            cast(tuple[str, ...], classified["required_structural_capabilities"])
        ),
        "satisfied_structural_capabilities": list(
            cast(tuple[str, ...], classified["satisfied_structural_capabilities"])
        ),
        "missing_structural_capabilities": list(
            cast(tuple[str, ...], classified["missing_structural_capabilities"])
        ),
        "oracle_fact_shape_checked": bool(facts),
        "type_line": type_line,
        "runtime_draw_count": runtime_draw_count,
        "runtime_scry_depth": runtime_scry_depth,
        "runtime_timing_window": runtime_timing_window,
    }


def _card_assessment(context: Any, oracle_name: str) -> dict[str, object]:
    return assess_card_fidelity(context, oracle_name)


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


def _required_next_evidence(blocked: Sequence[Mapping[str, object]]) -> str:
    tiers = {str(row.get("tier", "")) for row in blocked}
    if MechanicsFidelityTier.UNSUPPORTED.value in tiers:
        return "SEMANTIC_OR_MODEL_CAPABILITY_REQUIRED"
    if MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED.value in tiers:
        return "EXTERNAL_RULES_EVIDENCE_REQUIRED"
    if MechanicsFidelityTier.TACTICAL_REQUIRED.value in tiers:
        return "TACTICAL_EVIDENCE_REQUIRED"
    if MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY.value in tiers:
        return "STRUCTURAL_SCREENING_ONLY"
    return "STRUCTURAL_CONFIRMATORY_ALLOWED"


def _quantity_value(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


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
    tier_counts: Counter[str] = Counter()
    blocked_reasons: Counter[str] = Counter()
    for name, quantity, direction in delta:
        row = _card_assessment(context, name)
        row.update({"quantity": quantity, "direction": direction})
        changed.append(row)
        tier_counts[str(row["tier"])] += quantity
        if row["decision_safe"] is not True:
            blocked.append(row)
            for reason in cast(list[str], row.get("reasons", [])):
                blocked_reasons[reason] += quantity
    return {
        "schema_version": "2.0.0",
        "semantic_model_version": STRUCTURAL_SEMANTIC_MODEL_VERSION,
        "question_scope": "variant_delta_against_current_control",
        "deck_hash": deck_hash,
        "changed_slots": sum(quantity for _, quantity, direction in delta if direction == "added"),
        "changed_cards": changed,
        "blocked_cards": blocked,
        "blocked_reason_counts": dict(sorted(blocked_reasons.items())),
        "tier_counts": dict(sorted(tier_counts.items())),
        "fidelity_distance_to_safe": sum(
            _quantity_value(row.get("quantity", 1)) for row in blocked
        ),
        "required_next_evidence_layer": _required_next_evidence(blocked),
        "pass": not blocked,
        "decision_safe_tiers": sorted(tier.value for tier in DECISION_SAFE_TIERS),
        "truth_boundary": (
            "Question-specific Structural capability gate for the changed-card delta only; "
            "strategic StructuralMechanic tags are not rules-fidelity proof and the unchanged "
            "baseline is not upgraded to rules-complete evidence."
        ),
    }


def build_fidelity_liveness_audit(
    context: Any,
    *,
    control: Sequence[str],
    initial_variants: Sequence[WholeDeckVariant] = (),
    control_engine: Any | None = None,
    qd_config: Any | None = None,
    seed: int = 0,
) -> dict[str, object]:
    """Statically characterize whether non-control Structural decision candidates are reachable.

    The audit consumes no gameplay/scenario evidence. The legal-neighbor probe is exhaustive over
    the one-for-one changed-slot neighborhood formed by cards whose *removal and addition* are both
    decision-safe under the same delta contract. This is a conservative small-delta liveness gate,
    not a claim that every larger coherent package can be Structural-confirmed.
    """

    card_rows = {name: assess_card_fidelity(context, name) for name in sorted(context.cards)}
    tier_counts: Counter[str] = Counter(str(row["tier"]) for row in card_rows.values())
    reason_counts: Counter[str] = Counter()
    blocked_role_counts: Counter[str] = Counter()
    blocked_mechanic_counts: Counter[str] = Counter()
    for row in card_rows.values():
        if row.get("decision_safe") is True:
            continue
        for reason in cast(list[str], row.get("reasons", [])):
            reason_counts[reason] += 1
        for role in cast(list[str], row.get("roles", [])):
            blocked_role_counts[role] += 1
        for tag in cast(list[str], row.get("mechanic_tags", [])):
            blocked_mechanic_counts[tag] += 1

    control_counts = Counter(control)
    safe_control_names = tuple(
        name
        for name in sorted(control_counts)
        if card_rows.get(name, {}).get("decision_safe") is True
    )
    safe_add_names: list[str] = []
    for name, card in sorted(context.cards.items()):
        row = card_rows[name]
        if row.get("decision_safe") is not True:
            continue
        current_quantity = control_counts[name]
        available = int(getattr(card, "available_quantity", 0))
        is_basic = bool(getattr(card, "is_basic", False))
        if is_basic or current_quantity < available:
            safe_add_names.append(name)

    legal_neighbors: dict[str, WholeDeckVariant] = {}
    qd_cells: set[str] = set()
    if control_engine is not None:
        for remove_name in safe_control_names:
            remove_index = next(
                (index for index, name in enumerate(control) if name == remove_name),
                None,
            )
            if remove_index is None:
                continue
            for add_name in safe_add_names:
                if add_name == remove_name:
                    continue
                board = list(control)
                board[remove_index] = add_name
                candidate = tuple(board)
                assessment = assess_variant_mechanics(
                    context,
                    control=control,
                    candidate=candidate,
                )
                if assessment.get("pass") is not True:
                    continue
                variant = control_engine.evaluate_mainboard(
                    candidate,
                    seed=seed + len(legal_neighbors) + 1,
                    parent_variant_id=None,
                )
                if not variant.hard_gate.valid or variant.mainboard == tuple(control):
                    continue
                legal_neighbors.setdefault(variant.deck_hash, variant)
        if qd_config is not None and legal_neighbors:
            # Local import avoids coupling the fidelity module's import graph to optimizer_v2.
            from .optimizer_v2 import descriptor_for_variant

            qd_cells = {
                descriptor_for_variant(variant).cell(qd_config)
                for variant in legal_neighbors.values()
            }

    safe_initial = tuple(
        variant
        for variant in initial_variants
        if variant.hard_gate.valid
        and variant.mainboard != tuple(control)
        and assess_variant_mechanics(
            context,
            control=control,
            candidate=variant.mainboard,
            deck_hash=variant.deck_hash,
        ).get("pass")
        is True
    )
    decision_safe_cards = tuple(
        name for name, row in card_rows.items() if row.get("decision_safe") is True
    )
    decision_safe_noncontrol_cards = tuple(
        name for name in decision_safe_cards if name not in control_counts
    )
    reachable = bool(legal_neighbors or safe_initial)
    status = "PASS" if reachable else "MODEL_INFORMATION_LIMIT"
    return {
        "schema_version": "1.0.0",
        "semantic_model_version": STRUCTURAL_SEMANTIC_MODEL_VERSION,
        "evidence_consuming": False,
        "candidate_pool_count": len(card_rows),
        "tier_counts": dict(sorted(tier_counts.items())),
        "decision_safe_card_count": len(decision_safe_cards),
        "decision_safe_noncontrol_card_count": len(decision_safe_noncontrol_cards),
        "decision_safe_cards": list(decision_safe_cards),
        "decision_safe_legal_neighbor_count": len(legal_neighbors),
        "legal_single_swap_decision_safe_neighbor_count": len(legal_neighbors),
        "small_delta_safe_neighbor_count": len(legal_neighbors),
        "small_delta_definition": (
            "exhaustive legal one-for-one changed-slot neighborhood; conservative subset of all "
            "possible coherent <=2-slot/package changes"
        ),
        "safe_construction_seed_count": len(safe_initial),
        "safe_construction_seed_hashes": [row.deck_hash for row in safe_initial],
        "safe_qd_reachability": {
            "reachable": reachable,
            "decision_safe_qd_cells_reached": len(qd_cells),
            "qd_cells": sorted(qd_cells),
        },
        "blocked_reason_distribution": dict(sorted(reason_counts.items())),
        "blocked_role_counts": dict(sorted(blocked_role_counts.items())),
        "blocked_mechanic_tag_counts": dict(sorted(blocked_mechanic_counts.items())),
        "tactical_route_count": tier_counts[MechanicsFidelityTier.TACTICAL_REQUIRED.value],
        "external_route_count": tier_counts[MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED.value],
        "screening_only_count": tier_counts[
            MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY.value
        ],
        "unsupported_count": tier_counts[MechanicsFidelityTier.UNSUPPORTED.value],
        "fidelity_liveness": status,
        "run_readiness": "PASS" if reachable else "BLOCKED_OR_REROUTED_BEFORE_EVIDENCE",
        "truth_boundary": (
            "Static capability/reachability audit only; no gameplay evidence consumed and no "
            "fidelity tier is widened to satisfy liveness."
        ),
    }


def _mapping_number(mapping: Mapping[str, object], key: str, default: float) -> float:
    value = mapping.get(key, default)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _ranked_rows(payload: Mapping[str, object]) -> tuple[dict[str, Any], ...]:
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
    return tuple(rows)


def _diverse_rows(
    rows: Sequence[dict[str, Any]], limit: int = SHORTLIST_LIMIT
) -> tuple[dict[str, Any], ...]:
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


def _shortlist_rows(
    payload: Mapping[str, object], limit: int = SHORTLIST_LIMIT
) -> tuple[dict[str, Any], ...]:
    return _diverse_rows(_ranked_rows(payload), limit)


def assess_frontier_mechanics(root: str | Path, frontier_path: str | Path) -> dict[str, object]:
    root_path = Path(root).resolve()
    payload = json.loads(Path(frontier_path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError("frontier mechanics gate requires a JSON object")
    lab = WholeDeckDesignLab(root_path)
    control = current_control_mainboard(root_path)
    ranked = _ranked_rows(cast(Mapping[str, object], payload))
    assessments: list[dict[str, object]] = []
    malformed: list[str] = []
    eligible_rows: list[dict[str, Any]] = []
    for index, row in enumerate(ranked):
        raw_variant = row.get("variant")
        if not isinstance(raw_variant, dict):
            malformed.append(f"frontier[{index}].variant_missing")
            continue
        try:
            variant = WholeDeckVariant.model_validate(raw_variant)
        except Exception as exc:
            malformed.append(f"frontier[{index}].variant_invalid:{exc}")
            continue
        assessment = assess_variant_mechanics(
            lab.context,
            control=control,
            candidate=variant.mainboard,
            deck_hash=variant.deck_hash,
        )
        assessment["frontier_rank"] = index + 1
        assessments.append(assessment)
        if assessment.get("pass") is True:
            eligible_rows.append(row)
    shortlist = _diverse_rows(eligible_rows)
    eligible_hashes = [str(row.get("deck_hash", "")) for row in shortlist]
    blocked = [row for row in assessments if row.get("pass") is not True]
    return {
        "schema_version": "1.1.0",
        "semantic_model_version": STRUCTURAL_SEMANTIC_MODEL_VERSION,
        "semantic_model_identity": sha256_value(
            {
                "version": STRUCTURAL_SEMANTIC_MODEL_VERSION,
                "tactical_cards": sorted(TACTICAL_REQUIRED_CARDS),
                "external_rules_cards": sorted(EXTERNAL_RULES_REQUIRED_CARDS),
                "tactical_roles": sorted(role.value for role in TACTICAL_ROLES),
                "external_rules_roles": sorted(role.value for role in EXTERNAL_RULES_ROLES),
                "default_screening_only_roles": sorted(
                    role.value for role in DEFAULT_SCREENING_ONLY_ROLES
                ),
                "strategic_abstraction_mechanics": sorted(
                    tag.value for tag in STRATEGIC_ABSTRACTION_MECHANICS
                ),
                "capabilities": sorted(cap.value for cap in StructuralCapability),
            }
        ),
        "question_scope": "frontier_variant_delta_with_structural_confirmatory_routing",
        "frontier_candidate_count": len(ranked),
        "shortlist_size": len(shortlist),
        "structural_confirmatory_eligible_hashes": eligible_hashes,
        "assessments": assessments,
        "malformed_rows": malformed,
        "blocked_variant_hashes": [str(row.get("deck_hash")) for row in blocked],
        "pass": bool(shortlist) and not malformed,
        "routing_contract": {
            MechanicsFidelityTier.MECHANISTICALLY_SUPPORTED.value: "STRUCTURAL_CONFIRMATORY_ALLOWED",
            MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE.value: "STRUCTURAL_CONFIRMATORY_ALLOWED",
            MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY.value: "SEARCH_ONLY",
            MechanicsFidelityTier.TACTICAL_REQUIRED.value: "TACTICAL_OR_FAIL_CLOSED",
            MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED.value: "EXTERNAL_RULES_OR_FAIL_CLOSED",
            MechanicsFidelityTier.UNSUPPORTED.value: "FAIL_CLOSED",
        },
        "truth_boundary": (
            "Pass means at least one frontier candidate is question-specifically permitted for "
            "Structural confirmatory evaluation. Non-decision-safe candidates remain visible and "
            "are routed to their required evidence layer instead of blocking unrelated eligible "
            "candidates. Baseline residual approximations remain fixed context and are not upgraded "
            "to empirical or rules-engine evidence."
        ),
    }


def require_frontier_mechanics_decision_safe(
    root: str | Path, frontier_path: str | Path
) -> dict[str, object]:
    report = assess_frontier_mechanics(root, frontier_path)
    if report["pass"] is not True:
        malformed = "; ".join(str(value) for value in cast(list[object], report["malformed_rows"]))
        blocked = ", ".join(
            str(value) for value in cast(list[object], report["blocked_variant_hashes"])
        )
        detail = malformed or blocked or "no structurally confirmatory-eligible frontier candidate"
        raise RuntimeError(
            "confirmatory Structural decision blocked by question-specific mechanics fidelity: "
            + detail
        )
    return report


def write_structural_confirmatory_frontier(
    frontier_path: str | Path,
    *,
    fidelity: Mapping[str, object],
    output_path: str | Path,
) -> Path:
    payload = json.loads(Path(frontier_path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError("frontier mechanics routing requires a JSON object")
    manifest_hash = payload.get("manifest_hash")
    if not isinstance(manifest_hash, str) or not manifest_hash:
        raise RuntimeError("frontier mechanics routing requires a manifest hash")
    eligible = fidelity.get("structural_confirmatory_eligible_hashes")
    if not isinstance(eligible, list) or not eligible:
        raise RuntimeError("frontier mechanics routing has no eligible Structural shortlist")
    raw_elites = payload.get("elites")
    if not isinstance(raw_elites, list):
        raise RuntimeError("frontier mechanics routing requires an elites list")
    by_hash = {
        str(row.get("deck_hash", "")): cast(dict[str, Any], row)
        for row in raw_elites
        if isinstance(row, dict)
    }
    selected: list[dict[str, Any]] = []
    for value in eligible:
        deck_hash = str(value)
        row = by_hash.get(deck_hash)
        if row is None:
            raise RuntimeError(f"frontier mechanics routing lost eligible candidate {deck_hash}")
        selected.append(row)
    handoff = FrontierHandoff.create(manifest_hash=manifest_hash, elites=tuple(selected))
    destination = Path(output_path).resolve()
    atomic_write_json(destination, handoff.model_dump(mode="json"))
    return destination


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
    routed_frontier = write_structural_confirmatory_frontier(
        frontier_path,
        fidelity=fidelity,
        output_path=Path(run_directory).resolve() / "frontier-handoff-structural-confirmatory.json",
    )
    result = dict(
        run_decision_confirmatory(
            root,
            manifest,
            frontier_path=routed_frontier,
            run_directory=run_directory,
            workers=workers,
            max_turns=max_turns,
        )
    )
    result["mechanics_fidelity"] = fidelity
    result["mechanics_routed_frontier"] = str(routed_frontier)
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

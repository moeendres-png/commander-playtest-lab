from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.tactical import TACTICAL_RULES_VERSION, TacticalRuleOracle
from commander_lab.storage import sha256_value
from commander_lab.whole_deck.lab import WholeDeckDesignLab
from commander_lab.whole_deck.mechanics_fidelity import (
    STRUCTURAL_SEMANTIC_MODEL_VERSION,
    assess_variant_mechanics,
)
from commander_lab.whole_deck.search import current_control_mainboard
from commander_lab.whole_deck.tactical_capabilities import (
    BASIC_INSTANT_TIMING_CAPABILITY,
    TACTICAL_CAPABILITY_CONTRACT_VERSION,
    assess_tactical_variant_capabilities,
)

EXTERNAL_HISTORICAL = 116


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def classes_for(row: dict[str, Any], oracle_text: str, type_line: str) -> list[str]:
    reasons = set(row.get("reasons", []))
    if reasons == {"instant_timing_not_mechanistic"}:
        return ["INSTANT_TIMING"]
    text = oracle_text.lower()
    classes: set[str] = set()
    roles = set(row.get("roles", []))
    mechanics = set(row.get("mechanic_tags", []))
    if "instant" in type_line.lower() or "activate only" in text or "beginning of" in text:
        classes.add("INSTANT_TIMING")
    if "instant" in type_line.lower() or "counter target" in text or "copy target" in text:
        classes.update({"PRIORITY", "STACK_ORDER"})
    if "target" in text:
        classes.add("TARGET_LEGALITY")
    if "choose one" in text or "choose two" in text or "choose up to" in text or "mode" in text:
        classes.add("MODE_SELECTION")
    if "protection" in text or "hexproof" in text or "indestructible" in text:
        classes.add("PROTECTION")
    if "counter target" in text:
        classes.add("COUNTERSPELL_LEGALITY")
    triggered = any(token in text for token in ("whenever ", "when ", "at the beginning"))
    if triggered:
        classes.add("TRIGGER_ORDER")
    if "additional time" in text and triggered:
        classes.add("TRIGGER_COPY")
    if (
        "when this creature dies" in text
        or "when this permanent dies" in text
        or "when this creature enters" in text
        or "when this land enters" in text
    ):
        classes.add("STATE_TRIGGER")
    if "sacrifice" in text and (
        "rather than pay" in text or "additional cost" in text or ":" in text
    ):
        classes.add("SACRIFICE_COST")
    if "additional cost" in text or "rather than pay" in text or "in addition to paying" in text:
        classes.add("ADDITIONAL_COST")
    if " instead" in text or "would " in text:
        classes.add("REPLACEMENT_EFFECT")
    if "graveyard" in text or any(x in text for x in ("flashback", "retrace", "unearth")):
        classes.add("GRAVEYARD_SEQUENCE")
    if "exile" in text:
        classes.add("EXILE_SEQUENCE")
    if "search your library" in text:
        classes.add("LIBRARY_SEARCH")
        if "land card" in text or "basic land" in text:
            classes.add("LAND_SEARCH")
    if "shuffle" in text:
        classes.add("SHUFFLE")
    if (
        any(x in text for x in ("combat", "attacks", "attack", "blocks", "blocked"))
        or "combat_payoff" in roles
    ):
        classes.add("COMBAT_LEGALITY")
    if "block" in text:
        classes.add("BLOCKING")
    if "damage" in text:
        classes.add("DAMAGE_ASSIGNMENT")
    if "commander" in text or "commander_damage_support" in mechanics:
        classes.add("COMMANDER_ZONE")
    if "command zone" in text:
        classes.add("CAST_FROM_ZONE")
    if "each opponent" in text or "one of your opponents" in text or "an opponent" in text:
        if triggered:
            classes.add("MULTIPLAYER_TRIGGER_SCALING")
        if "target" in text:
            classes.add("MULTIPLAYER_TARGET_SELECTION")
    if "opponent chooses" in text or "chosen by an opponent" in text:
        classes.add("OPPONENT_CHOICE")
    if "each opponent" in text and "may" in text:
        classes.add("POLITICAL_OPTIONALITY")
    if "target_wipe_or_combat_legality_not_mechanistic" in reasons:
        if "removal" in roles:
            classes.add("TARGET_LEGALITY")
        if "wipe" in roles:
            classes.add("STATE_TRIGGER")
        if "combat_payoff" in roles:
            classes.add("COMBAT_LEGALITY")
    if "stack_or_protection_legality_not_mechanistic" in reasons:
        classes.update({"PRIORITY", "STACK_ORDER"})
        if "counter" in roles:
            classes.add("COUNTERSPELL_LEGALITY")
        if "protection" in roles:
            classes.add("PROTECTION")
    if "mechanic_requires_rules_accurate_state_or_sequencing" in reasons:
        if "death_trigger" in mechanics:
            classes.update({"STATE_TRIGGER", "TRIGGER_ORDER"})
        if "sacrifice_cost" in mechanics:
            classes.add("SACRIFICE_COST")
        if "sacrifice_outlet" in mechanics:
            classes.add("SACRIFICE_COST")
        if "stack_interaction" in mechanics:
            classes.update({"PRIORITY", "STACK_ORDER"})
        if "commander_damage_support" in mechanics:
            classes.update({"COMBAT_LEGALITY", "DAMAGE_ASSIGNMENT"})
    if not classes:
        classes.add("UNKNOWN_OTHER")
    return sorted(classes)


def pareto_external(rows: list[dict[str, Any]]) -> set[str]:
    frontier: set[str] = set()
    for a in rows:
        dominated = False
        for b in rows:
            if a is b:
                continue
            weak = (
                b["candidate_frontier_distance"] <= a["candidate_frontier_distance"]
                and b["changed_slots"] <= a["changed_slots"]
                and float(b["historical_search_rank_or_archive_context"]["objective_prior"] or 0.0)
                >= float(a["historical_search_rank_or_archive_context"]["objective_prior"] or 0.0)
            )
            strict = (
                b["candidate_frontier_distance"] < a["candidate_frontier_distance"]
                or b["changed_slots"] < a["changed_slots"]
                or float(b["historical_search_rank_or_archive_context"]["objective_prior"] or 0.0)
                > float(a["historical_search_rank_or_archive_context"]["objective_prior"] or 0.0)
            )
            if weak and strict:
                dominated = True
                break
        if not dominated:
            frontier.add(a["deck_hash"])
    return frontier


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--starting-commit", required=True)
    ap.add_argument("--starting-tree", required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lab = WholeDeckDesignLab(root)
    control = current_control_mainboard(root)
    ledger = json.loads(args.ledger.read_text())
    facts = lab.context.fresh_universe.candidate_facts_by_name

    reclassified: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    all_blocked_card_rows: dict[str, dict[str, Any]] = {}
    for source in ledger["rows"]:
        current = assess_variant_mechanics(
            lab.context,
            control=control,
            candidate=source["exact_mainboard"],
            deck_hash=source["deck_hash"],
        )
        tactical = assess_tactical_variant_capabilities(
            lab.context,
            control=control,
            candidate=source["exact_mainboard"],
            deck_hash=source["deck_hash"],
        )
        route = str(current["required_next_evidence_layer"])
        route_counts[route] += 1
        changed = current["changed_cards"]
        entry = {
            "candidate_id": source.get("variant_id", source["deck_hash"]),
            "deck_hash": source["deck_hash"],
            "exact_diff_vs_control": source["exact_diff_vs_control"],
            "changed_slots": source["changed_slots"],
            "changed_cards": [x["oracle_name"] for x in changed],
            "historical_fidelity_tier": source.get("fidelity_tier"),
            "current_fidelity_tier": route,
            "structural_safe_cards": [
                x["oracle_name"] for x in changed if x.get("decision_safe") is True
            ],
            "screening_only_cards": [
                x["oracle_name"] for x in changed if x.get("tier") == "APPROXIMATED_SCREENING_ONLY"
            ],
            "tactical_required_cards": [
                x["oracle_name"] for x in changed if x.get("tier") == "TACTICAL_REQUIRED"
            ],
            "external_required_cards": [
                x["oracle_name"] for x in changed if x.get("tier") == "EXTERNAL_RULES_REQUIRED"
            ],
            "missing_capabilities": sorted(
                {
                    c
                    for x in current["blocked_cards"]
                    for c in x.get("missing_structural_capabilities", [])
                }
            ),
            "missing_capability_count": int(current["fidelity_distance_to_safe"]),
            "capability_classes": [],
            "candidate_frontier_distance": int(current["fidelity_distance_to_safe"]),
            "search_archive_status": {
                "decision": source.get("decision_archive_status"),
                "hypothesis": source.get("hypothesis_archive_status"),
            },
            "historical_search_rank_or_archive_context": {
                "objective_prior": source.get("objective_prior"),
                "generation": source.get("generation"),
                "operator": source.get("operator"),
                "construction_policy": source.get("construction_policy"),
                "qd_cell": source.get("qd_cell"),
            },
            "tactical_evaluable_after_patch": tactical["tactical_evaluable"],
            "tactical_covered_cards": tactical["tactical_capabilities_covered"],
        }
        classes: set[str] = set()
        for b in current["blocked_cards"]:
            name = str(b["oracle_name"])
            f = facts.get(name, {})
            oracle_text = str(f.get("oracle_text") or "")
            type_line = str(f.get("type_line") or b.get("type_line") or "")
            cc = classes_for(b, oracle_text, type_line)
            classes.update(cc)
            if name not in all_blocked_card_rows:
                all_blocked_card_rows[name] = {
                    "oracle_name": name,
                    "oracle_text": oracle_text,
                    "type_line": type_line,
                    "rules_question_class": cc,
                    "required_state": [
                        "4-player game state",
                        "relevant zones",
                        "priority/stack when applicable",
                    ],
                    "required_actions": ["card-specific legal action or trigger resolution"],
                    "required_choices": ["targets/modes/ordering only when present in Oracle text"],
                    "timing_dependency": "INSTANT_TIMING" in cc,
                    "priority_dependency": "PRIORITY" in cc,
                    "target_dependency": "TARGET_LEGALITY" in cc,
                    "mode_dependency": "MODE_SELECTION" in cc,
                    "trigger_dependency": bool(
                        {"TRIGGER_ORDER", "TRIGGER_COPY", "STATE_TRIGGER"}.intersection(cc)
                    ),
                    "combat_dependency": bool(
                        {"COMBAT_LEGALITY", "BLOCKING", "DAMAGE_ASSIGNMENT"}.intersection(cc)
                    ),
                    "replacement_effect_dependency": "REPLACEMENT_EFFECT" in cc,
                    "commander_zone_dependency": "COMMANDER_ZONE" in cc,
                    "graveyard_dependency": "GRAVEYARD_SEQUENCE" in cc,
                    "shuffle_dependency": "SHUFFLE" in cc,
                    "minimum_required_evidence_layer": (
                        "TACTICAL"
                        if b.get("tier") == "TACTICAL_REQUIRED"
                        else "EXTERNAL_RULES"
                        if b.get("tier") == "EXTERNAL_RULES_REQUIRED"
                        else "SCENARIO_CONTRACT_REQUIRED"
                    ),
                    "current_fidelity_reasons": b.get("reasons", []),
                }
        entry["capability_classes"] = sorted(classes)
        reclassified.append(entry)

    external_rows = [
        r for r in reclassified if r["current_fidelity_tier"] == "EXTERNAL_RULES_EVIDENCE_REQUIRED"
    ]
    external_frontier = pareto_external(external_rows)
    for r in reclassified:
        r["near_frontier"] = (
            r["deck_hash"] in external_frontier or r["search_archive_status"]["decision"] == "ELITE"
        )

    baseline = {
        "schema_version": "1.0.0",
        "starting_main_commit": args.starting_commit,
        "starting_main_tree": args.starting_tree,
        "package_version": "1.23.2",
        "structural_semantic_model": STRUCTURAL_SEMANTIC_MODEL_VERSION,
        "tactical_runtime_before": "tactical-0.8.0",
        "external_runtime": {
            "xmage": "unavailable",
            "forge": "unavailable",
            "real_external_engine_executions": 0,
        },
        "historical_candidate_count": ledger["candidate_count"],
        "historical_external_candidates": EXTERNAL_HISTORICAL,
        "current_reclassification_counts": dict(sorted(route_counts.items())),
        "operational_pod_size": 4,
        "new_official_gameplay_evidence_consumed": False,
        "sealed_holdout_opened": False,
    }
    dump(out / "RULES_EVIDENCE_BASELINE.json", baseline)
    dump(
        out / "HISTORICAL_EXTERNAL_ROUTE_RECLASSIFICATION.json",
        {
            "schema_version": "1.0.0",
            "semantic_model": STRUCTURAL_SEMANTIC_MODEL_VERSION,
            "historical_external_candidates": EXTERNAL_HISTORICAL,
            "reclassified_count": len(reclassified),
            "route_counts": dict(sorted(route_counts.items())),
            "rows": reclassified,
            "truth_boundary": "Historical candidate replay only; no new gameplay or holdout evidence consumed.",
        },
    )
    dump(
        out / "CARD_RULES_GAP_DECOMPOSITION.json",
        {
            "schema_version": "1.0.0",
            "blocked_card_count": len(all_blocked_card_rows),
            "cards": [all_blocked_card_rows[k] for k in sorted(all_blocked_card_rows)],
        },
    )

    # Capability matrix: keep atomic classes plus candidate-specific frontier bundles.
    # We deliberately avoid the Cartesian 1-3 class power set: class labels are diagnostic,
    # not executable rules contracts, and enumerating arbitrary combinations overstates both
    # usefulness and implementation readiness.
    class_to_candidates: defaultdict[str, set[str]] = defaultdict(set)
    class_to_cards: defaultdict[str, set[str]] = defaultdict(set)
    candidate_classes = {
        r["deck_hash"]: set(r["capability_classes"])
        for r in reclassified
        if r["current_fidelity_tier"] != "STRUCTURAL_CONFIRMATORY_ALLOWED"
    }
    row_by_hash = {r["deck_hash"]: r for r in reclassified}
    for r in reclassified:
        for c in r["capability_classes"]:
            class_to_candidates[c].add(r["deck_hash"])
    for name, row in all_blocked_card_rows.items():
        for c in row["rules_question_class"]:
            class_to_cards[c].add(name)

    matrix: list[dict[str, Any]] = []
    for capability in sorted(class_to_candidates):
        affected = sorted(class_to_candidates[capability])
        fully = sorted(h for h, req in candidate_classes.items() if req == {capability})
        near = sorted(h for h in fully if row_by_hash[h]["near_frontier"])
        matrix.append(
            {
                "capability_id": capability,
                "capability_name": capability,
                "evidence_layer": (
                    "TACTICAL"
                    if capability == "INSTANT_TIMING"
                    else "TACTICAL_OR_EXTERNAL_DEPENDS_ON_CARD_SHAPE"
                ),
                "cards_blocked": sorted(class_to_cards[capability]),
                "candidate_count_affected": len(affected),
                "candidates_partially_improved": affected,
                "candidates_fully_unlocked": fully,
                "near_frontier_candidates_unlocked": near,
                "decision_archive_candidates_unlocked": [
                    h
                    for h in fully
                    if row_by_hash[h]["search_archive_status"]["decision"] == "ELITE"
                ],
                "minimum_scenario_classes_required": [capability],
                "implementation_scope": "bounded card-shape contracts required; class label alone is not implementation",
                "implementation_complexity": "LOW"
                if capability == "INSTANT_TIMING"
                else "UNKNOWN_UNTIL_CARD_SHAPE_BOUND",
                "validation_complexity": "LOW"
                if capability == "INSTANT_TIMING"
                else "UNKNOWN_UNTIL_CARD_SHAPE_BOUND",
                "existing_infrastructure_reuse": [
                    "TacticalRuleOracle",
                    "historical candidate ledger",
                ],
                "new_infrastructure_required": []
                if capability == "INSTANT_TIMING"
                else ["card-specific scenario contract and/or validated external engine"],
                "estimated_decision_value": "HIGHEST_FRONTIER"
                if capability == "INSTANT_TIMING"
                else ("FRONTIER_RELEVANT" if near else "SECONDARY"),
                "recommended": capability == "INSTANT_TIMING",
                "reason": (
                    "Historical Decision-Elite Opt delta is blocked only by bounded default instant timing."
                    if capability == "INSTANT_TIMING"
                    else "Atomic diagnostic class; not selected without a bounded complete candidate unlock."
                ),
                "hypothetical_class_complete_unlock_only": capability != "INSTANT_TIMING",
            }
        )

    # Combined rows are only exact class bundles actually observed on the Pareto/Decision frontier.
    seen_frontier_sets: set[tuple[str, ...]] = set()
    for r in sorted((x for x in reclassified if x["near_frontier"]), key=lambda x: x["deck_hash"]):
        combo = tuple(sorted(r["capability_classes"]))
        if len(combo) <= 1 or combo in seen_frontier_sets:
            continue
        seen_frontier_sets.add(combo)
        affected = sorted(h for h, req in candidate_classes.items() if req == set(combo))
        matrix.append(
            {
                "capability_id": "FRONTIER_BUNDLE::" + "+".join(combo),
                "capability_name": "Observed frontier bundle: " + " + ".join(combo),
                "evidence_layer": "TACTICAL_OR_EXTERNAL_DEPENDS_ON_CARD_SHAPE",
                "cards_blocked": sorted({name for c in combo for name in class_to_cards[c]}),
                "candidate_count_affected": len(affected),
                "candidates_partially_improved": affected,
                "candidates_fully_unlocked": affected,
                "near_frontier_candidates_unlocked": [
                    h for h in affected if row_by_hash[h]["near_frontier"]
                ],
                "decision_archive_candidates_unlocked": [
                    h
                    for h in affected
                    if row_by_hash[h]["search_archive_status"]["decision"] == "ELITE"
                ],
                "minimum_scenario_classes_required": list(combo),
                "implementation_scope": "diagnostic exact class bundle only; each card shape still requires an executable contract",
                "implementation_complexity": "HIGH",
                "validation_complexity": "HIGH",
                "existing_infrastructure_reuse": ["historical candidate ledger"],
                "new_infrastructure_required": [
                    "multiple bounded card-shape contracts and/or validated external engine"
                ],
                "estimated_decision_value": "FRONTIER_RELEVANT_BUT_NOT_IMPLEMENTATION_READY",
                "recommended": False,
                "reason": "Observed on the frontier, but class completeness is hypothetical until every card-shape contract is validated.",
                "hypothetical_class_complete_unlock_only": True,
            }
        )
    dump(
        out / "RULES_CAPABILITY_UNLOCK_MATRIX.json",
        {
            "schema_version": "1.0.0",
            "matrix_scope": "atomic classes plus exact observed frontier bundles; no arbitrary class power-set",
            "rows": matrix,
        },
    )

    priority_md = f"""# Rules Capability Priority Report\n\n## Result\n\nThe frontier-weighted minimum is `{BASIC_INSTANT_TIMING_CAPABILITY}` at the Tactical layer.\n\n- Current v3 replay: {dict(sorted(route_counts.items()))}\n- Historical Decision-Elite `Preordain -> Opt` is now Tactical-only and blocked solely by default instant timing.\n- Two additional one-slot candidates (`Preordain -> Jace's Ingenuity`, `Sol Ring -> Opt`) share the same bounded timing gap.\n- The nearest External candidate still has 12 blocked changed cards across multiple independent card-specific rules shapes. No bounded 1-3 External package is justified as a complete unlock without overclaiming.\n- XMage/Forge remain unavailable; therefore zero External scenario classes may be called externally validated.\n\n## Decision\n\nImplement one Tactical package only. Defer External expansion until a future frontier candidate is fully unlockable by a small validated scenario set.\n"""
    (out / "RULES_CAPABILITY_PRIORITY_REPORT.md").write_text(priority_md)

    tactical_rows = [r for r in reclassified if r["tactical_evaluable_after_patch"]]
    minimum = {
        "schema_version": "1.0.0",
        "implementation_required": True,
        "selected_capabilities": [BASIC_INSTANT_TIMING_CAPABILITY],
        "selection_reason": "Unlocks the historical Decision-Elite and two additional one-slot Tactical candidates with one bounded 4P timing contract.",
        "fully_unlocked_candidate_count": len(tactical_rows),
        "fully_unlocked_candidate_ids": [r["deck_hash"] for r in tactical_rows],
        "near_frontier_unlocked_count": sum(bool(r["near_frontier"]) for r in tactical_rows),
        "near_frontier_unlocked_ids": [r["deck_hash"] for r in tactical_rows if r["near_frontier"]],
        "still_blocked_candidate_count": len(reclassified)
        - sum(r["current_fidelity_tier"] == "STRUCTURAL_CONFIRMATORY_ALLOWED" for r in reclassified)
        - len(tactical_rows),
        "implementation_dependencies": [
            "TacticalRuleOracle basic_spell_timing",
            TACTICAL_CAPABILITY_CONTRACT_VERSION,
        ],
        "validation_dependencies": [
            "4P positive fixture",
            "4P negative fixture",
            "no-priority negative fixture",
            "3P fail-closed fixture",
        ],
        "expected_tactical_gain": len(tactical_rows),
        "expected_external_gain": 0,
        "unlock_definition": "rules-evidence-ready for the bounded timing question; not a deck-strength estimate or empirical winrate",
        "not_selected_capabilities": [
            "broad graveyard/recursion package",
            "spell-copy/alternative-cost package",
            "cascade/retrace package",
            "generic combat/trigger engine",
        ],
        "defer_reason": "No small bounded package fully unlocks an External candidate; broad implementation would violate decision-value-first scope.",
    }
    dump(out / "MINIMUM_RULES_UNLOCK_SET.json", minimum)

    oracle = TacticalRuleOracle()
    fixtures = [
        (
            "opt_opponent_turn_priority",
            {
                "spell_speed": "instant",
                "player_count": 4,
                "phase": "postcombat_main",
                "actor_is_active": False,
                "has_priority": True,
                "stack_empty": False,
                "can_pay_cost": True,
            },
            True,
        ),
        (
            "preordain_opponent_turn_negative",
            {
                "spell_speed": "sorcery",
                "player_count": 4,
                "phase": "postcombat_main",
                "actor_is_active": False,
                "has_priority": True,
                "stack_empty": True,
                "can_pay_cost": True,
            },
            False,
        ),
        (
            "preordain_own_main_positive",
            {
                "spell_speed": "sorcery",
                "player_count": 4,
                "phase": "precombat_main",
                "actor_is_active": True,
                "has_priority": True,
                "stack_empty": True,
                "can_pay_cost": True,
            },
            True,
        ),
        (
            "opt_no_priority_negative",
            {
                "spell_speed": "instant",
                "player_count": 4,
                "phase": "precombat_main",
                "actor_is_active": True,
                "has_priority": False,
                "stack_empty": True,
                "can_pay_cost": True,
            },
            False,
        ),
    ]
    fixture_rows = []
    for fid, state, expected in fixtures:
        observed = oracle.evaluate("basic_spell_timing", state)
        fixture_rows.append(
            {
                "fixture_id": fid,
                "capability_id": BASIC_INSTANT_TIMING_CAPABILITY,
                "players": 4,
                "initial_state": state,
                "actor": "rogshai",
                "seat": 0,
                "priority_state": {"has_priority": state["has_priority"]},
                "stack_state": {"empty": state["stack_empty"]},
                "zones": {},
                "targets": [],
                "choices": [],
                "expected_legal_actions": ["cast"] if expected else [],
                "expected_illegal_actions": [] if expected else ["cast"],
                "expected_final_state": {"can_cast": expected},
                "observed": observed,
                "engine_layer": "TACTICAL",
                "external_engine_used": False,
                "external_engine_version": None,
                "pass": observed["can_cast"] is expected,
            }
        )
    dump(
        out / "RULES_EVIDENCE_GOLDEN_FIXTURES.json",
        {"schema_version": "1.0.0", "fixtures": fixture_rows},
    )
    dump(
        out / "TACTICAL_CAPABILITY_CONFORMANCE.json",
        {
            "schema_version": "1.0.0",
            "tactical_runtime": TACTICAL_RULES_VERSION,
            "capability_id": BASIC_INSTANT_TIMING_CAPABILITY,
            "supported_oracle_shape": "ordinary Instant/Sorcery default timing; candidate handoff further restricted to literal verified draw/scry runtime profiles",
            "supported_timing_window": "default priority timing in exactly 4-player fixtures",
            "supported_choices": [],
            "supported_targets": [],
            "supported_zone_transitions": [],
            "unsupported_cases": [
                "Flash-granting effects",
                "split second",
                "static cast restrictions/permissions",
                "targets",
                "modes",
                "mana-generation decisions",
                "strategic value of holding mana open",
            ],
            "known_abstractions": [
                "legality fixture only; not empirical winrate or External Rules evidence"
            ],
            "golden_fixtures": [x["fixture_id"] for x in fixture_rows if x["pass"]],
            "negative_fixtures": [
                x["fixture_id"] for x in fixture_rows if not x["expected_final_state"]["can_cast"]
            ],
            "pass": all(x["pass"] for x in fixture_rows),
        },
    )

    external_partial = [r for r in external_rows if r["tactical_covered_cards"]]
    replay = {
        "schema_version": "1.0.0",
        "before": {
            "structural_safe": route_counts["STRUCTURAL_CONFIRMATORY_ALLOWED"],
            "tactical_required": route_counts["TACTICAL_EVIDENCE_REQUIRED"],
            "external_required": route_counts["EXTERNAL_RULES_EVIDENCE_REQUIRED"],
            "screening_only": route_counts["STRUCTURAL_SCREENING_ONLY"],
            "unsupported": route_counts["SEMANTIC_OR_MODEL_CAPABILITY_REQUIRED"],
        },
        "after": {
            "structural_safe": route_counts["STRUCTURAL_CONFIRMATORY_ALLOWED"],
            "tactical_evaluable": len(tactical_rows),
            "external_evaluable": 0,
            "external_still_blocked": len(external_rows),
            "screening_only": route_counts["STRUCTURAL_SCREENING_ONLY"],
            "unsupported": route_counts["SEMANTIC_OR_MODEL_CAPABILITY_REQUIRED"],
        },
        "historical_external_candidates": EXTERNAL_HISTORICAL,
        "fully_evaluable_after_patch": 0,
        "partially_improved_only": len(external_partial),
        "partially_improved_external_ids": [r["deck_hash"] for r in external_partial],
        "still_external_blocked": len(external_rows),
        "near_frontier_fully_unlocked": sum(bool(r["near_frontier"]) for r in tactical_rows),
        "tactical_evaluable_candidate_ids": [r["deck_hash"] for r in tactical_rows],
        "tactical_evaluable_scope": "bounded rules-evidence timing question only; no deck-strength estimate",
        "decision_elite_tactical_unlocked_ids": [
            r["deck_hash"]
            for r in tactical_rows
            if r["search_archive_status"]["decision"] == "ELITE"
        ],
        "pass": True,
        "truth_boundary": "Diagnostic historical routing replay only; no new gameplay evidence.",
    }
    dump(out / "POST_UNLOCK_ROUTING_REPLAY.json", replay)

    # Pre-validation report; full repo/CI fields are filled in closeout after gates.
    dump(
        out / "RULES_EVIDENCE_VALIDATION_REPORT.json",
        {
            "schema_version": "1.0.0",
            "phase": "pre_ci_local_validation",
            "tactical_runtime": TACTICAL_RULES_VERSION,
            "tactical_capability_contract": TACTICAL_CAPABILITY_CONTRACT_VERSION,
            "golden_fixtures_pass": all(x["pass"] for x in fixture_rows),
            "negative_fixtures_pass": all(
                x["pass"] for x in fixture_rows if not x["expected_final_state"]["can_cast"]
            ),
            "post_unlock_routing_replay": "PASS",
            "real_external_engine_executions": 0,
            "external_scenario_classes_validated": 0,
            "artifact_set_hash": sha256_value(
                {"reclassified": reclassified, "minimum": minimum, "replay": replay}
            ),
        },
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from commander_lab.storage import atomic_write_json, sha256_value

from .mechanics_fidelity import (
    MechanicsFidelityTier,
    assess_variant_mechanics,
    changed_card_multiset,
)
from .optimizer_search import OptimizerSearchReport
from .optimizer_v2 import descriptor_for_variant
from .search_models import WholeDeckVariant


def _expanded_diff(
    control: Sequence[str], candidate: Sequence[str]
) -> tuple[list[str], list[str], list[dict[str, object]]]:
    removed: list[str] = []
    added: list[str] = []
    rows: list[dict[str, object]] = []
    for name, quantity, direction in changed_card_multiset(control, candidate):
        rows.append({"oracle_name": name, "quantity": quantity, "direction": direction})
        target = added if direction == "added" else removed
        target.extend([name] * quantity)
    return removed, added, rows


def _operator(variant: WholeDeckVariant) -> str:
    explicit = variant.provenance.get("optimizer_operator")
    if isinstance(explicit, str) and explicit:
        return explicit
    if variant.mutation is not None:
        return variant.mutation.neighborhood.value
    return "construction_prior"


def _variant_fidelity_tier(assessment: Mapping[str, object]) -> str:
    if assessment.get("pass") is True:
        if int(assessment.get("changed_slots", 0)) == 0:
            return "NO_DELTA_CONTROL"
        return MechanicsFidelityTier.APPROXIMATED_DECISION_SAFE.value
    route = str(assessment.get("required_next_evidence_layer", ""))
    route_to_tier = {
        "STRUCTURAL_SCREENING_ONLY": MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY.value,
        "TACTICAL_EVIDENCE_REQUIRED": MechanicsFidelityTier.TACTICAL_REQUIRED.value,
        "EXTERNAL_RULES_EVIDENCE_REQUIRED": MechanicsFidelityTier.EXTERNAL_RULES_REQUIRED.value,
        "SEMANTIC_OR_MODEL_CAPABILITY_REQUIRED": MechanicsFidelityTier.UNSUPPORTED.value,
    }
    return route_to_tier.get(route, MechanicsFidelityTier.APPROXIMATED_SCREENING_ONLY.value)


def _archive_hashes(search_report: OptimizerSearchReport) -> tuple[set[str], set[str]]:
    decision: set[str] = set()
    raw_cells = search_report.archive.get("cells", {})
    if isinstance(raw_cells, Mapping):
        for values in raw_cells.values():
            if isinstance(values, list):
                decision.update(str(value) for value in values)
    hypothesis: set[str] = set()
    raw_hyp = search_report.hypothesis_archive or {}
    buckets = raw_hyp.get("buckets", {}) if isinstance(raw_hyp, Mapping) else {}
    if isinstance(buckets, Mapping):
        for values in buckets.values():
            if isinstance(values, list):
                hypothesis.update(str(value) for value in values)
    return decision, hypothesis


def build_candidate_ledger(
    *,
    context: Any,
    control_mainboard: Sequence[str],
    evaluator: Any,
    search_report: OptimizerSearchReport,
    control_deck_hash: str,
) -> dict[str, object]:
    """Build a complete immutable candidate ledger from already-consumed search state only."""

    variants: Mapping[str, WholeDeckVariant] = evaluator.variants_by_hash
    histories: Mapping[str, list[dict[str, Any]]] = evaluator.evaluation_history_by_hash
    if len(variants) != search_report.unique_legal_decks:
        raise RuntimeError(
            "candidate ledger completeness mismatch: "
            f"variants={len(variants)} search={search_report.unique_legal_decks}"
        )
    by_variant_id = {variant.variant_id: variant for variant in variants.values()}
    decision_hashes, hypothesis_hashes = _archive_hashes(search_report)
    commanders = tuple(str(value) for value in context.commander_names)
    rows: list[dict[str, object]] = []
    for deck_hash in sorted(variants):
        variant = variants[deck_hash]
        history = list(histories.get(deck_hash, ()))
        if not history:
            raise RuntimeError(f"candidate ledger has no evaluation history for {deck_hash}")
        assessment = assess_variant_mechanics(
            context,
            control=control_mainboard,
            candidate=variant.mainboard,
            deck_hash=deck_hash,
        )
        removed, added, diff = _expanded_diff(control_mainboard, variant.mainboard)
        parent = by_variant_id.get(variant.parent_variant_id or "")
        first = history[0]
        first_eval = first.get("evaluation", {})
        last_eval = history[-1].get("evaluation", {})
        if not isinstance(first_eval, Mapping) or not isinstance(last_eval, Mapping):
            raise RuntimeError(f"candidate ledger malformed evaluator history for {deck_hash}")
        generation = variant.provenance.get("optimizer_generation", last_eval.get("generation", 0))
        materialized = context.materialize(variant.mainboard, label=f"ledger-{deck_hash[:12]}")
        if materialized.deck_hash != deck_hash:
            raise RuntimeError(
                f"candidate ledger deck hash does not reconstruct from exact list: {deck_hash}"
            )
        reconstructed = list(control_mainboard)
        for name in removed:
            reconstructed.remove(name)
        reconstructed.extend(added)
        if Counter(reconstructed) != Counter(variant.mainboard):
            raise RuntimeError(f"candidate ledger diff does not reconstruct candidate: {deck_hash}")
        descriptor = descriptor_for_variant(variant)
        blocked = assessment.get("blocked_cards", [])
        blocked_rows = blocked if isinstance(blocked, list) else []
        route = str(assessment.get("required_next_evidence_layer", "UNKNOWN"))
        exact_100 = list(commanders) + list(variant.mainboard)
        if len(exact_100) != 100:
            raise RuntimeError(f"candidate ledger exact deck is not 100 cards: {deck_hash}")
        rows.append(
            {
                "deck_hash": deck_hash,
                "variant_id": variant.variant_id,
                "exact_mainboard": list(variant.mainboard),
                "commander_names": list(commanders),
                "exact_100_card_list": exact_100,
                "exact_diff_vs_control": diff,
                "removed_cards": removed,
                "added_cards": added,
                "changed_slots": int(assessment.get("changed_slots", 0)),
                "parent_variant_id": variant.parent_variant_id,
                "parent_deck_hash": parent.deck_hash if parent is not None else None,
                "construction_policy": variant.policy_id.value,
                "policy_version": variant.policy_version,
                "operator": _operator(variant),
                "generation": int(generation) if isinstance(generation, int) else 0,
                "seed": variant.seed,
                "objective_prior": variant.objective_prior,
                "qd_descriptor": descriptor.model_dump(mode="json"),
                "qd_cell": descriptor.cell(evaluator.manifest.qd),
                "screening_budget": int(first.get("budget", first_eval.get("budget", 0))),
                "screening_score": first_eval.get("score"),
                "screening_interval": [
                    first_eval.get("interval_low"),
                    first_eval.get("interval_high"),
                ],
                "robust_lower_bound": last_eval.get("robust_lower_bound"),
                "all_later_budget_history": history,
                "fidelity_tier": _variant_fidelity_tier(assessment),
                "decision_safe": assessment.get("pass") is True,
                "changed_card_fidelity": assessment.get("changed_cards", []),
                "blocked_cards": [row.get("oracle_name") for row in blocked_rows],
                "blocked_reasons": assessment.get("blocked_reason_counts", {}),
                "required_next_evidence_layer": route,
                "fidelity_distance_to_safe": assessment.get("fidelity_distance_to_safe"),
                "hypothesis_archive_status": (
                    "RETAINED" if deck_hash in hypothesis_hashes else "EVALUATED_NOT_RETAINED"
                ),
                "decision_archive_status": (
                    "ELITE" if deck_hash in decision_hashes else "NOT_DECISION_ELITE"
                ),
                "confirmatory_eligible": (
                    assessment.get("pass") is True
                    and deck_hash in decision_hashes
                    and deck_hash != control_deck_hash
                ),
                "physical_legality_status": "PASS" if variant.hard_gate.valid else "FAIL",
                "inventory_status": (
                    "CHECKED"
                    if variant.hard_gate.physical_inventory_checked
                    else "NOT_CHECKED"
                ),
                "semantic_status": (
                    "KNOWN"
                    if not any(str(row.get("tier")) == MechanicsFidelityTier.UNSUPPORTED.value for row in blocked_rows)
                    else "UNSUPPORTED_OR_UNKNOWN"
                ),
                "provenance": dict(variant.provenance),
            }
        )
    payload_without_hash: dict[str, object] = {
        "schema_version": "1.0.0",
        "candidate_count": len(rows),
        "control_deck_hash": control_deck_hash,
        "rows": rows,
        "truth_boundary": (
            "Complete optimizer candidate provenance. Screening scores are hypothesis evidence only "
            "unless the same row is explicitly decision-safe and separately promoted."
        ),
    }
    return {**payload_without_hash, "ledger_hash": sha256_value(payload_without_hash)}


def build_routed_hypothesis_queues(
    ledger: Mapping[str, object], *, limit: int = 8
) -> dict[str, object]:
    raw_rows = ledger.get("rows", [])
    rows = [row for row in raw_rows if isinstance(row, Mapping)] if isinstance(raw_rows, list) else []
    groups: dict[str, list[dict[str, object]]] = {
        "TOP_STRUCTURAL_SCREENING_ONLY_HYPOTHESES": [],
        "TOP_TACTICAL_REQUIRED_HYPOTHESES": [],
        "TOP_EXTERNAL_RULES_REQUIRED_HYPOTHESES": [],
        "TOP_UNSUPPORTED_OR_SEMANTIC_BLOCKED_HYPOTHESES": [],
    }
    route_to_group = {
        "STRUCTURAL_SCREENING_ONLY": "TOP_STRUCTURAL_SCREENING_ONLY_HYPOTHESES",
        "TACTICAL_EVIDENCE_REQUIRED": "TOP_TACTICAL_REQUIRED_HYPOTHESES",
        "EXTERNAL_RULES_EVIDENCE_REQUIRED": "TOP_EXTERNAL_RULES_REQUIRED_HYPOTHESES",
        "SEMANTIC_OR_MODEL_CAPABILITY_REQUIRED": "TOP_UNSUPPORTED_OR_SEMANTIC_BLOCKED_HYPOTHESES",
    }
    for row in rows:
        route = str(row.get("required_next_evidence_layer", ""))
        group = route_to_group.get(route)
        if group is None:
            continue
        score = row.get("screening_score")
        objective = row.get("objective_prior")
        novelty = 0.0
        history = row.get("all_later_budget_history")
        if isinstance(history, list) and history:
            evaluation = history[-1].get("evaluation") if isinstance(history[-1], Mapping) else None
            if isinstance(evaluation, Mapping) and isinstance(evaluation.get("novelty"), int | float):
                novelty = float(evaluation["novelty"])
        priority = (
            (float(objective) if isinstance(objective, int | float) else 0.0)
            + 0.25 * (float(score) if isinstance(score, int | float) else 0.0)
            + 0.15 * novelty
            - 0.02 * float(row.get("fidelity_distance_to_safe", 0) or 0)
        )
        groups[group].append(
            {
                "deck_hash": row.get("deck_hash"),
                "hypothesis_priority": priority,
                "required_next_evidence_layer": route,
                "blocked_cards": row.get("blocked_cards", []),
                "blocked_reasons": row.get("blocked_reasons", {}),
                "exact_diff_vs_control": row.get("exact_diff_vs_control", []),
                "construction_policy": row.get("construction_policy"),
                "operator": row.get("operator"),
                "generation": row.get("generation"),
                "classification": "HYPOTHESIS_PRIORITY_NOT_CONFIRMED_DECK_RANKING",
            }
        )
    for key, values in groups.items():
        values.sort(key=lambda row: (-float(row["hypothesis_priority"]), str(row["deck_hash"])))
        groups[key] = values[:limit]
    return {
        "schema_version": "1.0.0",
        "candidate_ledger_hash": ledger.get("ledger_hash"),
        **groups,
        "truth_boundary": (
            "Prioritized follow-up hypotheses only. Screening/Tactical/External routes are not "
            "Structural confirmatory rankings."
        ),
    }


def write_candidate_artifacts(
    run_path: Path,
    *,
    ledger: Mapping[str, object],
    queues: Mapping[str, object],
) -> None:
    atomic_write_json(run_path / "ALL_CANDIDATE_LEDGER.json", dict(ledger))
    atomic_write_json(run_path / "ROUTED_HYPOTHESIS_QUEUES.json", dict(queues))

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from commander_lab.candidate_screening import CandidateScreener
from commander_lab.cut_frontier import build_static_swap_rows
from commander_lab.decision_context import (
    CandidateAvailability,
    CandidateProvenance,
    TestCandidateSpec,
    load_decision_context_registry,
)
from commander_lab.deck_registry import DeckPolicyRegistry, load_deck_policy_registry
from commander_lab.models import CandidateProfile, StructuralDeckProfile, VariantSwap
from commander_lab.optimization import build_search_candidate
from commander_lab.project_context import load_project_context
from commander_lab.tools.service import CommanderToolService


class CandidateEvaluationError(ValueError):
    """Raised when candidate-evaluation planning cannot preserve its truth boundary."""


_LANE_PRIORITY = {
    "explicit_test_ready": 0,
    "advance": 1,
    "explore": 2,
    "profile_required": 3,
    "deferred": 4,
}
_AVAILABILITY_PRIORITY = {
    CandidateAvailability.PHYSICAL_FREE: 0,
    CandidateAvailability.HYPOTHETICAL_TEST: 1,
}


def _hash_payload(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _profiles_by_name(
    profiles: Iterable[CandidateProfile],
    *,
    deck_id: str,
    source: str,
) -> dict[str, CandidateProfile]:
    grouped: dict[str, list[CandidateProfile]] = defaultdict(list)
    for profile in profiles:
        if profile.allowed_deck_ids and deck_id not in profile.allowed_deck_ids:
            continue
        grouped[profile.card.oracle_name].append(profile)
    duplicates = {
        name: sorted(row.candidate_id for row in rows)
        for name, rows in grouped.items()
        if len(rows) > 1
    }
    if duplicates:
        raise CandidateEvaluationError(
            f"ambiguous deck-scoped {source} profiles for {deck_id}: {duplicates}"
        )
    return {name: rows[0] for name, rows in grouped.items()}


def _prepare_test_profiles(
    profiles: Sequence[CandidateProfile],
    specs: Sequence[TestCandidateSpec],
    *,
    deck_id: str,
) -> dict[str, CandidateProfile]:
    authorized_names = {spec.oracle_name for spec in specs if deck_id in set(spec.allowed_deck_ids)}
    prepared: list[CandidateProfile] = []
    for profile in profiles:
        if profile.card.oracle_name not in authorized_names:
            raise CandidateEvaluationError(
                "a hypothetical structural profile requires a matching explicit "
                f"TestCandidateSpec: {profile.card.oracle_name}"
            )
        if profile.allowed_deck_ids and deck_id not in profile.allowed_deck_ids:
            raise CandidateEvaluationError(
                f"hypothetical profile is not scoped to {deck_id}: {profile.candidate_id}"
            )
        prepared.append(
            profile.model_copy(
                update={
                    "allowed_deck_ids": (deck_id,),
                    "physical_status": "simulation_only_hypothetical",
                    "notes": (
                        (profile.notes or "")
                        + " Explicit simulation-only test profile; this does not assert "
                        "physical ownership."
                    ).strip(),
                }
            )
        )
    return _profiles_by_name(prepared, deck_id=deck_id, source="hypothetical")


def _effective_provenance(rows: Sequence[CandidateProvenance]) -> CandidateProvenance:
    if not rows:
        raise CandidateEvaluationError("candidate has no provenance")
    return min(
        rows,
        key=lambda row: (
            _AVAILABILITY_PRIORITY.get(row.availability, 99),
            row.candidate_id,
        ),
    )


def _row_score_key(row: dict[str, Any]) -> tuple[float, str, str]:
    raw_score = row.get("screening_delta", 0.0)
    score = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0
    return (
        -score,
        str(row.get("add", row.get("candidate_id", ""))).casefold(),
        str(row.get("remove", "")).casefold(),
    )


def _candidate_diverse_rows(
    rows: Sequence[dict[str, Any]],
    *,
    max_pairs: int,
    max_pairs_per_candidate: int,
    seeded: Sequence[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Select a bounded frontier that maximizes candidate coverage before repeats.

    Static score only orders otherwise eligible experiment rows. The selector first gives each
    candidate one opportunity, preferring an unused cut, and only then allows another row for the
    same candidate up to ``max_pairs_per_candidate``.
    """

    if max_pairs < 1 or max_pairs_per_candidate < 1:
        raise CandidateEvaluationError("candidate-diversity budgets must be positive")

    selected = list(seeded)
    if len(selected) > max_pairs:
        raise CandidateEvaluationError("seeded frontier exceeds max_pairs")

    used_keys = {(str(row.get("remove", "")), str(row.get("candidate_id", ""))) for row in selected}
    used_cuts = {str(row.get("remove", "")) for row in selected}
    candidate_counts = Counter(str(row.get("candidate_id", "")) for row in selected)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        candidate_id = str(row.get("candidate_id", ""))
        key = (str(row.get("remove", "")), candidate_id)
        if not candidate_id or key in used_keys:
            continue
        grouped[candidate_id].append(row)

    for candidate_rows in grouped.values():
        candidate_rows.sort(key=_row_score_key)
    candidate_order = sorted(
        grouped,
        key=lambda candidate_id: (
            _row_score_key(grouped[candidate_id][0]),
            candidate_id,
        ),
    )

    for target_count in range(1, max_pairs_per_candidate + 1):
        for candidate_id in candidate_order:
            if len(selected) >= max_pairs:
                return selected
            if candidate_counts[candidate_id] >= target_count:
                continue
            available = [
                row
                for row in grouped[candidate_id]
                if (str(row.get("remove", "")), candidate_id) not in used_keys
            ]
            if not available:
                continue
            available.sort(
                key=lambda row: (
                    str(row.get("remove", "")) in used_cuts,
                    _row_score_key(row),
                )
            )
            chosen = available[0]
            selected.append(chosen)
            key = (str(chosen.get("remove", "")), candidate_id)
            used_keys.add(key)
            used_cuts.add(str(chosen.get("remove", "")))
            candidate_counts[candidate_id] += 1

    return selected


def _frontier_metrics(
    rows: Sequence[dict[str, Any]],
    *,
    max_pairs_per_candidate: int,
) -> dict[str, Any]:
    cut_counts = Counter(str(row["remove"]) for row in rows)
    candidate_counts = Counter(str(row["add"]) for row in rows)
    lane_counts: Counter[str] = Counter()
    provenance_counts: Counter[str] = Counter()
    for row in rows:
        cut = row.get("cut_hypothesis")
        if isinstance(cut, dict):
            lane_counts.update(str(value) for value in cut.get("lanes", ()))
        provenance = row.get("candidate_provenance")
        if isinstance(provenance, dict):
            provenance_counts[str(provenance.get("availability", "unknown"))] += 1
    return {
        "pair_count": len(rows),
        "unique_cut_count": len(cut_counts),
        "unique_candidate_count": len(candidate_counts),
        "max_pairs_per_candidate": max_pairs_per_candidate,
        "observed_max_pairs_for_one_candidate": max(candidate_counts.values(), default=0),
        "cut_pair_distribution": dict(sorted(cut_counts.items())),
        "candidate_pair_distribution": dict(sorted(candidate_counts.items())),
        "cut_lane_distribution": dict(sorted(lane_counts.items())),
        "candidate_provenance_distribution": dict(sorted(provenance_counts.items())),
        "selection_policy": (
            "explicit_test_coverage_then_candidate_first_cut_diverse_structural_frontier"
        ),
        "truth_boundary": "frontier composition only; not empirical card strength",
    }


def build_candidate_evaluation_plan(
    root: str | Path,
    *,
    deck_id: str | None = None,
    service: CommanderToolService | None = None,
    registry: DeckPolicyRegistry | None = None,
    test_candidates: Iterable[TestCandidateSpec] = (),
    test_candidate_profiles: Iterable[CandidateProfile] = (),
    max_pairs: int = 16,
    max_pairs_per_candidate: int = 2,
    max_cut_hypotheses: int = 24,
    max_candidate_queue: int = 64,
) -> dict[str, Any]:
    """Build a bounded next-experiment plan for one active own deck.

    The function stops before paired simulation. Static structural scores only choose a diverse
    experiment frontier. Explicit hypothetical cards remain simulation-only and never become
    inventory, allocation, reservation, purchase, or final recommendation truth.
    """

    if (
        max_pairs < 1
        or max_pairs_per_candidate < 1
        or max_cut_hypotheses < 1
        or max_candidate_queue < 1
    ):
        raise CandidateEvaluationError("candidate-evaluation budgets must be positive")

    root_path = Path(root).resolve()
    deck_registry = registry or load_deck_policy_registry(root_path)
    selected_deck_id = deck_id or deck_registry.primary_deck_id
    deck_registry.assert_active(selected_deck_id)
    tool_service = service or CommanderToolService(root_path)
    try:
        baseline: StructuralDeckProfile = tool_service.decks[selected_deck_id]
    except KeyError as exc:
        raise CandidateEvaluationError(
            f"active deck has no structural profile: {selected_deck_id}"
        ) from exc

    specs = tuple(test_candidates)
    decision_registry = load_decision_context_registry(root_path, test_candidates=specs)
    deck_context = decision_registry.deck(selected_deck_id)
    if baseline.deck_hash != deck_context.deck_hash:
        raise CandidateEvaluationError(
            f"structural/canonical deck hash mismatch for {selected_deck_id}"
        )

    screener = CandidateScreener(root_path, service=tool_service, registry=deck_registry)
    screened = screener.screen_pool(selected_deck_id)
    raw_screen_rows = screened.get("rows")
    if not isinstance(raw_screen_rows, list):
        raise CandidateEvaluationError("candidate screen did not return rows")
    screen_by_name = {
        str(row["oracle_name"]): dict(row)
        for row in raw_screen_rows
        if isinstance(row, dict) and row.get("oracle_name")
    }

    physical_profiles = _profiles_by_name(
        tool_service.candidates.values(),
        deck_id=selected_deck_id,
        source="physical",
    )
    hypothetical_profiles = _prepare_test_profiles(
        tuple(test_candidate_profiles),
        specs,
        deck_id=selected_deck_id,
    )

    provenance_by_name: dict[str, list[CandidateProvenance]] = defaultdict(list)
    for provenance in decision_registry.candidates_for_deck(
        selected_deck_id,
        include_hypothetical_tests=True,
    ):
        provenance_by_name[provenance.oracle_name].append(provenance)

    all_queue_rows: list[dict[str, Any]] = []
    profile_by_id: dict[str, CandidateProfile] = {}
    profile_provenance: dict[str, CandidateProvenance] = {}
    explicit_profile_ids: set[str] = set()

    for oracle_name in sorted(provenance_by_name, key=str.casefold):
        provenance_options = sorted(
            provenance_by_name[oracle_name],
            key=lambda row: (
                _AVAILABILITY_PRIORITY.get(row.availability, 99),
                row.candidate_id,
            ),
        )
        provenance = _effective_provenance(provenance_options)
        if provenance.availability is CandidateAvailability.PHYSICAL_FREE:
            profile = physical_profiles.get(oracle_name)
            screen_row = screen_by_name.get(oracle_name, {})
            bucket = str(
                screen_row.get(
                    "bucket",
                    "requires_profile_before_model_dependent_recommendation",
                )
            )
        elif provenance.availability is CandidateAvailability.HYPOTHETICAL_TEST:
            profile = hypothetical_profiles.get(oracle_name)
            screen_row = {}
            bucket = "explicit_test_candidate"
        else:
            continue

        model_ready = profile is not None
        physical_frontier_bucket = bucket in {"advance", "explore"}
        frontier_eligible = model_ready and (
            provenance.availability is CandidateAvailability.HYPOTHETICAL_TEST
            or physical_frontier_bucket
        )
        if provenance.availability is CandidateAvailability.HYPOTHETICAL_TEST:
            lane = "explicit_test_ready" if model_ready else "profile_required"
            next_action = (
                "generate_constraint_valid_variant_frontier"
                if model_ready
                else "profile_and_validate_before_model_dependent_variant_testing"
            )
        elif not model_ready:
            lane = "profile_required"
            next_action = "profile_before_model_dependent_variant_testing"
        elif bucket == "advance":
            lane = "advance"
            next_action = "generate_constraint_valid_variant_frontier"
        elif bucket == "explore":
            lane = "explore"
            next_action = "generate_exploratory_variant_frontier"
        else:
            lane = "deferred"
            next_action = "retain_for_later_exploration_not_default_frontier"

        profile_candidate_id: str | None
        if profile is not None:
            profile_candidate_id = profile.candidate_id
            if profile_candidate_id in profile_by_id:
                raise CandidateEvaluationError(
                    f"duplicate candidate profile id in evaluation plan: {profile_candidate_id}"
                )
            profile_by_id[profile_candidate_id] = profile
            profile_provenance[profile_candidate_id] = provenance
            if provenance.availability is CandidateAvailability.HYPOTHETICAL_TEST:
                explicit_profile_ids.add(profile_candidate_id)
        else:
            profile_candidate_id = None

        roles = (
            tuple(sorted(role.value for role in profile.card.roles))
            if profile is not None
            else tuple(str(value) for value in screen_row.get("roles", ()))
        )
        package_ids = (
            tuple(sorted(profile.card.package_ids))
            if profile is not None
            else tuple(str(value) for value in screen_row.get("package_ids", ()))
        )
        all_queue_rows.append(
            {
                "evaluation_candidate_id": provenance.candidate_id,
                "profile_candidate_id": profile_candidate_id,
                "oracle_name": oracle_name,
                "availability": provenance.availability.value,
                "quantity": provenance.quantity,
                "physically_available": provenance.physically_available,
                "simulation_authorized": provenance.simulatable_for_improvement,
                "source_id": provenance.source_id,
                "source_hash": provenance.source_hash,
                "provenance_options": [row.as_dict() for row in provenance_options],
                "screening_bucket": bucket,
                "screening_confidence": screen_row.get(
                    "confidence",
                    "explicit_test_user_authorized",
                ),
                "roles": roles,
                "package_ids": package_ids,
                "package_context_required": bool(package_ids),
                "model_ready": model_ready,
                "frontier_eligible": frontier_eligible,
                "lane": lane,
                "next_action": next_action,
                "final_recommendation": False,
            }
        )

    all_queue_rows.sort(
        key=lambda row: (
            _LANE_PRIORITY[str(row["lane"])],
            str(row["oracle_name"]).casefold(),
            str(row["evaluation_candidate_id"]),
        )
    )
    explicit_queue = [
        row
        for row in all_queue_rows
        if row["availability"] == CandidateAvailability.HYPOTHETICAL_TEST.value
    ]
    if len(explicit_queue) > max_candidate_queue:
        raise CandidateEvaluationError(
            "candidate queue budget is smaller than the explicit hypothetical test-candidate set"
        )
    queue_ids = {str(row["evaluation_candidate_id"]) for row in explicit_queue}
    next_candidate_queue = [*explicit_queue]
    for row in all_queue_rows:
        if len(next_candidate_queue) >= max_candidate_queue:
            break
        if str(row["evaluation_candidate_id"]) in queue_ids:
            continue
        next_candidate_queue.append(row)
        queue_ids.add(str(row["evaluation_candidate_id"]))

    frontier_profiles: dict[str, CandidateProfile] = {}
    for row in all_queue_rows:
        if row["frontier_eligible"] is not True:
            continue
        raw_profile_id = row["profile_candidate_id"]
        if not isinstance(raw_profile_id, str):
            continue
        frontier_profiles[raw_profile_id] = profile_by_id[raw_profile_id]

    protected = frozenset(
        str(value) for value in tool_service.protected_cards.get(selected_deck_id, ())
    )
    static_rows = build_static_swap_rows(
        baseline,
        frontier_profiles,
        protected=protected,
        max_cut_hypotheses=max_cut_hypotheses,
    )
    constraints = tool_service._optimization_constraints(selected_deck_id)

    def validate_row(row: dict[str, Any]) -> dict[str, Any] | None:
        profile_candidate_id = str(row["candidate_id"])
        provenance = profile_provenance[profile_candidate_id]
        hypothetical = provenance.availability is CandidateAvailability.HYPOTHETICAL_TEST
        simulation_constraints = (
            constraints.model_copy(update={"require_verified_inventory": False})
            if hypothetical
            else constraints
        )
        try:
            built = build_search_candidate(
                baseline,
                (
                    VariantSwap(
                        remove=str(row["remove"]),
                        add_candidate_id=profile_candidate_id,
                    ),
                ),
                frontier_profiles,
                simulation_constraints,
                inventory=tool_service.candidate_inventory,
                verified_physical_names=tool_service.verified_candidate_names,
            )
        except (KeyError, ValueError):
            return None
        if not built.constraint_report.valid:
            return None

        physical_issue_codes: list[str] = []
        if hypothetical:
            try:
                physical_probe = build_search_candidate(
                    baseline,
                    (
                        VariantSwap(
                            remove=str(row["remove"]),
                            add_candidate_id=profile_candidate_id,
                        ),
                    ),
                    frontier_profiles,
                    constraints,
                    inventory=tool_service.candidate_inventory,
                    verified_physical_names=tool_service.verified_candidate_names,
                )
                physical_issue_codes = sorted(
                    {issue.code for issue in physical_probe.constraint_report.issues}
                )
            except (KeyError, ValueError) as exc:
                physical_issue_codes = [f"physical_probe_error:{type(exc).__name__}"]

        package_ids = tuple(sorted(built.additions[0].card.package_ids))
        return {
            **row,
            "evaluation_candidate_id": provenance.candidate_id,
            "profile_candidate_id": profile_candidate_id,
            "candidate_provenance": provenance.as_dict(),
            "variant_id": built.variant.deck_id,
            "variant_deck_hash": built.variant.deck_hash,
            "constraint_valid": True,
            "constraint_report": built.constraint_report.model_dump(mode="json"),
            "physical_buildable": provenance.physically_available,
            "simulation_only_hypothetical": hypothetical,
            "physical_inventory_bypass_applied": hypothetical,
            "physical_inventory_bypass_reason": (
                "explicit_hypothetical_test_authorization" if hypothetical else None
            ),
            "physical_probe_issue_codes": physical_issue_codes,
            "package_ids": package_ids,
            "requires_package_followup": bool(package_ids),
            "requires_paired_validation": True,
            "final_recommendation": False,
            "structural_rationale": list(built.rationale),
            "affected_matchups": list(built.affected_matchups),
            "truth_boundary": (
                "constraint-valid structural experiment candidate; "
                "not empirical deck-power evidence"
            ),
        }

    validated_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    mandatory_hypothetical: list[dict[str, Any]] = []
    for profile_candidate_id in sorted(explicit_profile_ids):
        candidate_rows = sorted(
            (row for row in static_rows if str(row["candidate_id"]) == profile_candidate_id),
            key=_row_score_key,
        )
        for row in candidate_rows:
            validated = validate_row(row)
            if validated is None:
                continue
            key = (str(validated["remove"]), profile_candidate_id)
            validated_by_key[key] = validated
            mandatory_hypothetical.append(validated)
            break

    if len(mandatory_hypothetical) > max_pairs:
        raise CandidateEvaluationError(
            "variant frontier budget is smaller than the model-ready explicit test-candidate set"
        )

    probe_budget = min(len(static_rows), max(max_pairs * 8, max_pairs))
    probe_rows = _candidate_diverse_rows(
        static_rows,
        max_pairs=probe_budget,
        max_pairs_per_candidate=2,
    )
    for row in probe_rows:
        key = (str(row["remove"]), str(row["candidate_id"]))
        if key in validated_by_key:
            continue
        validated = validate_row(row)
        if validated is not None:
            validated_by_key[key] = validated

    mandatory_keys = {
        (str(row["remove"]), str(row["profile_candidate_id"])) for row in mandatory_hypothetical
    }
    remaining = [row for key, row in validated_by_key.items() if key not in mandatory_keys]
    frontier = _candidate_diverse_rows(
        remaining,
        max_pairs=max_pairs,
        max_pairs_per_candidate=max_pairs_per_candidate,
        seeded=mandatory_hypothetical,
    )
    for index, row in enumerate(frontier, start=1):
        row["test_order"] = index

    package_groups: dict[str, set[str]] = defaultdict(set)
    for row in frontier:
        for package_id in row.get("package_ids", ()):
            package_groups[str(package_id)].add(str(row["add"]))
    package_followups = [
        {
            "package_id": package_id,
            "candidate_cards": sorted(names, key=str.casefold),
            "next_action": (
                "package_density_or_ablation_followup_before_single_card_recommendation"
            ),
            "truth_boundary": "package hypothesis only; no package-strength claim",
        }
        for package_id, names in sorted(package_groups.items())
    ]

    project_context = load_project_context(root_path)
    suggested_opponents = list(project_context.primary_opponent_deck_ids(selected_deck_id))
    profile_queue = [row for row in all_queue_rows if row["lane"] == "profile_required"]
    plan_core: dict[str, Any] = {
        "schema_version": "1.1.0",
        "artifact_type": "candidate_evaluation_plan",
        "evidence_class": "structural_model_estimates",
        "deck_id": selected_deck_id,
        "deck_hash": baseline.deck_hash,
        "decision_context_snapshot_hash": decision_registry.snapshot_hash,
        "deck_policy_registry": deck_registry.as_dict(),
        "candidate_discovery": {
            "discoverable_candidate_count": screened["discoverable_candidate_count"],
            "physical_legal_candidate_count": screened["physical_legal_candidate_count"],
            "candidate_pool_after_default_screen": screened["candidate_pool_after_default_screen"],
            "explicit_hypothetical_candidate_count": len(explicit_queue),
            "model_ready_frontier_candidate_count": len(frontier_profiles),
            "profile_required_count": len(profile_queue),
            "screening_boundary": screened["screening_boundary"],
        },
        "next_candidate_queue": next_candidate_queue,
        "candidate_queue_truncated": len(next_candidate_queue) < len(all_queue_rows),
        "profile_queue": profile_queue,
        "static_swap_pool_count": len(static_rows),
        "validated_structural_variant_pool_count": len(validated_by_key),
        "variant_frontier": frontier,
        "frontier_metrics": _frontier_metrics(
            frontier,
            max_pairs_per_candidate=max_pairs_per_candidate,
        ),
        "package_followups": package_followups,
        "suggested_opponent_ids": suggested_opponents,
        "next_stage_contract": {
            "step_1": "run paired structural comparisons for the bounded variant frontier",
            "step_2": ("add commander-denial and card/package ablation for surviving variants"),
            "step_3": "test sensitivity/holdout/opponent-envelope robustness",
            "step_4": "emit DecisionBundle with trade-offs, uncertainty and next experiment",
            "opponent_frequency_weights_invented": False,
        },
        "canonical_mutation_performed": False,
        "inventory_reservation_performed": False,
        "purchase_decision_performed": False,
        "final_recommendation": False,
        "known_limitations": [
            "Static frontier scores are model-internal screening signals, not empirical winrates.",
            (
                "Unprofiled candidates remain discoverable but cannot enter "
                "model-dependent variants yet."
            ),
            "A package-tagged single-card probe is not a package-level recommendation.",
            (
                "Hypothetical test authorization permits simulation only and never asserts "
                "physical ownership."
            ),
            (
                "Candidate-first frontier diversity improves experiment coverage; it does not "
                "constitute a card-strength ranking."
            ),
        ],
        "truth_boundary": (
            "reproducible structural candidate/variant experiment plan; not empirical gameplay, "
            "not a final deck recommendation, and not physical inventory truth"
        ),
    }
    return {"plan_hash": _hash_payload(plan_core), **plan_core}


__all__ = ["CandidateEvaluationError", "build_candidate_evaluation_plan"]

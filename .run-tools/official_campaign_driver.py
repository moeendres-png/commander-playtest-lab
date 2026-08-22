from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

EXPECTED_PACKAGE_VERSION = "1.23.0"
DEFAULT_DIVERSIFIED_STARTS = 2
DEFAULT_STEPS_PER_START = 8
DEFAULT_FINALISTS_PER_POLICY = 4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def git(root: Path, *args: str) -> str:
    cp = subprocess.run(
        ["git", "-C", str(root), *args], check=True, text=True, capture_output=True
    )
    return cp.stdout.strip()


def verify_runtime_identity(root: Path, expected_commit: str, expected_tree: str) -> dict[str, object]:
    commit = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    tracked = git(root, "status", "--porcelain=v1", "--untracked-files=no")
    if commit != expected_commit:
        raise RuntimeError(f"canonical runtime commit drift: {commit} != {expected_commit}")
    if tree != expected_tree:
        raise RuntimeError(f"canonical runtime tree drift: {tree} != {expected_tree}")
    if tracked:
        raise RuntimeError(f"canonical runtime tracked worktree is dirty: {tracked}")
    return {
        "status": "pass",
        "canonical_main_commit": commit,
        "canonical_main_tree": tree,
        "tracked_clean": True,
    }


def run_cli(*, root: Path, output_dir: Path, label: str, args: Sequence[str]) -> tuple[dict[str, Any] | None, float]:
    started = time.perf_counter()
    cp = subprocess.run(
        ["commander-lab-optimizer", *args], cwd=root, text=True, capture_output=True
    )
    duration = time.perf_counter() - started
    (output_dir / f"{label}.stdout.txt").write_text(cp.stdout, encoding="utf-8")
    (output_dir / f"{label}.stderr.txt").write_text(cp.stderr, encoding="utf-8")
    if cp.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {cp.returncode}; see {label}.stderr.txt")
    payload: dict[str, Any] | None = None
    if cp.stdout.strip():
        try:
            value = json.loads(cp.stdout)
            if isinstance(value, dict):
                payload = value
        except json.JSONDecodeError:
            payload = None
    return payload, duration


def extract_archive_cell_count(archive: object) -> int | str:
    if not isinstance(archive, Mapping):
        return "NOT_MEASURED"
    for key in ("occupied_cells", "cell_count", "occupied_cell_count", "coverage_cells"):
        value = archive.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    cells = archive.get("cells")
    if isinstance(cells, (dict, list, tuple)):
        return len(cells)
    return "NOT_MEASURED"


def stage_integrity(*, output_dir: Path, phase: str, root: Path, expected_commit: str, expected_tree: str, manifest_hash: str, holdout_opened: bool) -> None:
    identity = verify_runtime_identity(root, expected_commit, expected_tree)
    write_json(
        output_dir / f"INTEGRITY_{phase.upper()}.json",
        {
            **identity,
            "phase": phase,
            "timestamp": utc_now(),
            "manifest_hash": manifest_hash,
            "canonical_deck_mutation": False,
            "inventory_mutation": False,
            "allocation_mutation": False,
            "purchase_mutation": False,
            "opponent_truth_mutation": False,
            "kaervek_mutation": False,
            "holdout_opened": holdout_opened,
        },
    )


def non_consuming_readiness(*, root: Path, manifest_path: Path, output_dir: Path, expected_commit: str, expected_tree: str, expected_manifest_hash: str, expected_manifest_file_sha256: str, expected_seed: int) -> dict[str, Any]:
    identity = verify_runtime_identity(root, expected_commit, expected_tree)
    if sha256_file(manifest_path) != expected_manifest_file_sha256:
        raise RuntimeError("manifest file SHA-256 mismatch")

    from commander_lab.whole_deck.lab import WholeDeckDesignLab
    from commander_lab.whole_deck.models import PolicyId
    from commander_lab.whole_deck.optimizer_runtime import DEFAULT_POLICIES, _initial_variants
    from commander_lab.whole_deck.optimizer_v2_decision_runtime import load_decision_manifest, verify_decision_preflight
    from commander_lab.whole_deck.optimizer_v2_release import run_release_search
    from commander_lab.whole_deck.search_context import current_control_mainboard

    manifest = load_decision_manifest(manifest_path)
    if manifest.manifest_hash != expected_manifest_hash:
        raise RuntimeError("manifest content hash mismatch")
    if manifest.search_seed != expected_seed:
        raise RuntimeError("manifest seed mismatch")
    if manifest.software_commit != expected_commit or manifest.software_tree != expected_tree:
        raise RuntimeError("manifest software identity does not bind exact runtime")
    if manifest.package_version != EXPECTED_PACKAGE_VERSION:
        raise RuntimeError("manifest package version mismatch")

    preflight = dict(verify_decision_preflight(root, manifest))
    if preflight.get("status") != "pass":
        raise RuntimeError("decision preflight did not pass")
    if preflight.get("operational_pod_size") != 4:
        raise RuntimeError("operational pod size is not four")
    if preflight.get("candidate_count") != 795:
        raise RuntimeError("candidate count drifted from frozen 795")
    if preflight.get("semantic_unknown_count") != 0:
        raise RuntimeError("semantic unknowns are non-zero")

    lab = WholeDeckDesignLab(root)
    engines, initial = _initial_variants(
        lab,
        manifest,
        policies=DEFAULT_POLICIES,
        diversified_starts=DEFAULT_DIVERSIFIED_STARTS,
        steps_per_start=DEFAULT_STEPS_PER_START,
        finalists_per_policy=DEFAULT_FINALISTS_PER_POLICY,
    )
    control = current_control_mainboard(root)
    anchors = [v for v in initial if v.mainboard == control]
    if not anchors:
        raise RuntimeError("exact current control absent from initial optimizer seeds")
    canonical_anchor = next((v for v in anchors if v.policy_id == PolicyId.CURRENT_CONTROL), None)
    if canonical_anchor is None:
        raise RuntimeError("exact current control is not represented by CURRENT_CONTROL policy")
    if canonical_anchor.mainboard != control:
        raise RuntimeError("current-control anchor mainboard mismatch")
    if set(engines) != set(DEFAULT_POLICIES):
        raise RuntimeError("construction policy coverage does not match DEFAULT_POLICIES")

    source = inspect.getsource(run_release_search)
    calibration_at = source.find("_face_validity_calibration(")
    exploratory_at = source.find("evaluator = CachedPartitionEvaluator(")
    if calibration_at < 0 or exploratory_at < 0 or calibration_at >= exploratory_at:
        raise RuntimeError("calibration-first source-order invariant is not present")
    if "calibration acceptance failed before exploratory evidence consumption" not in source:
        raise RuntimeError("calibration fail-closed invariant is not present")

    report = {
        "status": "PASS_READY_NOT_STARTED",
        "timestamp": utc_now(),
        "RUN_STARTED": False,
        "CURRENT_FREEZE_VALID": True,
        "CURRENT_MANIFEST_EVIDENCE_CONSUMED": False,
        "CURRENT_SEALED_HOLDOUT_OPENED": False,
        "canonical_main_commit": expected_commit,
        "canonical_main_tree": expected_tree,
        "manifest_hash": expected_manifest_hash,
        "manifest_file_sha256": expected_manifest_file_sha256,
        "manifest_seed": expected_seed,
        "operational_pod_size": 4,
        "candidate_count": preflight["candidate_count"],
        "semantic_unknown_count": preflight["semantic_unknown_count"],
        "CURRENT_CONTROL_SEARCH_ANCHOR": "present_exact_current_control",
        "FRESH_REBUILD_CONTROL_BLINDNESS": "preserved_by_separate_current_control_anchor_and_distinct_fresh_rebuild_policy_engines",
        "initial_legal_seed_count": len(initial),
        "construction_policy_count": len(engines),
        "construction_policies": sorted(engines),
        "exact_control_anchor_hash": canonical_anchor.deck_hash,
        "exact_control_anchor_policy": canonical_anchor.policy_id.value,
        "calibration_first_gate": "PASS_SOURCE_ORDER_AND_FAIL_CLOSED",
        "preflight": preflight,
        "runtime_identity": identity,
        "truth_boundary": "non-consuming construction/readiness validation; no gameplay evidence",
    }
    write_json(output_dir / "RUN_READY.json", report)
    write_json(output_dir / "RUN_PREFLIGHT.json", preflight)
    write_json(
        output_dir / "CURRENT_CONTROL_ANCHOR_AUDIT.json",
        {
            "status": "pass",
            "CURRENT_CONTROL_SEARCH_ANCHOR": report["CURRENT_CONTROL_SEARCH_ANCHOR"],
            "FRESH_REBUILD_CONTROL_BLINDNESS": report["FRESH_REBUILD_CONTROL_BLINDNESS"],
            "initial_legal_seed_count": len(initial),
            "exact_control_anchor_hash": canonical_anchor.deck_hash,
            "exact_control_anchor_policy": canonical_anchor.policy_id.value,
            "evidence_consumed": False,
        },
    )
    return report


def freeze_challenger(*, root: Path, output_dir: Path, manifest_hash: str, expected_commit: str, expected_tree: str, confirmatory: Mapping[str, Any]) -> dict[str, Any]:
    from commander_lab.whole_deck.lab import WholeDeckDesignLab
    from commander_lab.whole_deck.search_context import current_control_mainboard
    from commander_lab.whole_deck.search_models import WholeDeckVariant

    deck_hash = confirmatory.get("single_challenger_hash")
    if not isinstance(deck_hash, str) or not deck_hash:
        raise RuntimeError("challenger freeze requires one confirmatory challenger")
    handoff = load_json(output_dir / "frontier-handoff.json")
    elites = handoff.get("elites") if isinstance(handoff, dict) else None
    if not isinstance(elites, list):
        raise RuntimeError("frontier handoff has no elites")
    row = next((x for x in elites if isinstance(x, dict) and x.get("deck_hash") == deck_hash), None)
    if row is None:
        raise RuntimeError("frozen challenger absent from frontier")
    variant = WholeDeckVariant.model_validate(row["variant"])
    lab = WholeDeckDesignLab(root)
    candidate_profile = lab.context.materialize(variant.mainboard, label="frozen-challenger")
    control_mainboard = tuple(current_control_mainboard(root))
    control_profile = lab.context.materialize(control_mainboard, label="frozen-control")
    left, right = Counter(control_mainboard), Counter(variant.mainboard)
    removals: list[str] = []
    additions: list[str] = []
    for name in sorted(set(left) | set(right)):
        delta = right[name] - left[name]
        if delta > 0:
            additions.extend([name] * delta)
        elif delta < 0:
            removals.extend([name] * (-delta))
    challenger_100 = list(candidate_profile.commander_names) + list(variant.mainboard)
    control_100 = list(control_profile.commander_names) + list(control_mainboard)
    if len(challenger_100) != 100 or len(control_100) != 100:
        raise RuntimeError(f"freeze expected exact 100-card lists; got challenger={len(challenger_100)}, control={len(control_100)}")
    freeze = {
        "status": "FROZEN_NO_FURTHER_TUNING",
        "timestamp": utc_now(),
        "manifest_hash": manifest_hash,
        "software_commit": expected_commit,
        "software_tree": expected_tree,
        "challenger_deck_hash": deck_hash,
        "control_deck_hash": control_profile.deck_hash,
        "challenger_variant": variant.model_dump(mode="json"),
        "exact_100_card_list": challenger_100,
        "control_exact_100_card_list": control_100,
        "exact_removals": removals,
        "exact_additions": additions,
        "challenger_selection_rule": confirmatory.get("single_challenger_selection_rule"),
        "confirmatory_pareto_frontier": confirmatory.get("pareto_frontier"),
        "holdout_looks_authorized": 1,
        "holdout_paired_4p_budget": 2048,
        "tuning_after_freeze": False,
        "canonical_deck_mutation": False,
        "PROPOSED_ONLY": True,
        "NOT_CANONICAL": True,
        "NOT_APPLIED": True,
    }
    write_json(output_dir / "FINAL_CHALLENGER_FREEZE.json", freeze)
    return freeze


def closeout(*, output_dir: Path, expected_commit: str, expected_tree: str, manifest_hash: str, manifest_seed: int, durations: Mapping[str, float], terminal_error: str | None) -> None:
    def maybe(name: str) -> dict[str, Any] | None:
        path = output_dir / name
        if not path.is_file():
            return None
        value = load_json(path)
        return value if isinstance(value, dict) else None

    preflight = maybe("RUN_PREFLIGHT.json") or maybe("preflight.json")
    search = maybe("optimizer-search-report.json")
    calibration = maybe("calibration-report.json")
    fidelity = maybe("frontier-fidelity.json")
    confirm = maybe("confirmatory-report.json")
    diagnostics = maybe("critical-diagnostics-report.json")
    freeze = maybe("FINAL_CHALLENGER_FREEZE.json")
    holdout = maybe("holdout-report.json")
    search_audit = maybe("optimizer-execution-audit-search.json")
    confirm_audit = maybe("optimizer-execution-audit-confirmatory.json")
    holdout_audit = maybe("optimizer-execution-audit-holdout.json")
    evidence_consumed = any(value is not None for value in (calibration, search, confirm, diagnostics, holdout))
    holdout_opened = holdout is not None

    entries: list[dict[str, Any]] = [
        {
            "flaw_id": "RFL-20260823-001",
            "timestamp_or_phase": "pre_current_freeze",
            "category": "DECISION_INTEGRITY_RISK",
            "severity": "P0",
            "observed_symptom": "Prepatch calibration followed Exploratory Search.",
            "reproduction": "prepatch run_release_search call order",
            "affected_stage": "prepatch_search",
            "affected_candidates": "none_current_manifest",
            "affected_evidence": "none_current_manifest",
            "root_cause_or_best_hypothesis": "verified call-order defect",
            "confidence": "VERIFIED",
            "decision_materiality": "BLOCKER_BEFORE_PATCH",
            "current_run_validity_impact": "NONE_AFTER_PR113_AND_NEW_FREEZE",
            "recommended_fix": "calibration-first fail-closed gate",
            "recommended_test": "failed calibration cannot instantiate exploratory evaluator",
            "patch_now_or_defer": "PATCHED",
            "status": "RESOLVED_PR113",
        },
        {
            "flaw_id": "RFL-20260823-002",
            "timestamp_or_phase": "execution_vehicle_precheck_before_current_run",
            "category": "WORKFLOW_USABILITY",
            "severity": "P0_FOR_START_ONLY",
            "observed_symptom": "Anchor precheck called _initial_variants without required keyword-only args.",
            "reproduction": "GitHub Actions run 32602460157 step 8",
            "affected_stage": "non_consuming_anchor_precheck",
            "affected_candidates": "none",
            "affected_evidence": "none; zero games consumed",
            "root_cause_or_best_hypothesis": "verified execution-vehicle API mismatch",
            "confidence": "VERIFIED",
            "decision_materiality": "NO_DECK_EVIDENCE_IMPACT",
            "current_run_validity_impact": "NONE_AFTER_READY_VEHICLE_REPLACEMENT",
            "recommended_fix": "call canonical helper with exact runtime defaults; separate readiness from run start",
            "recommended_test": "non-consuming readiness workflow executes exact anchor probe",
            "patch_now_or_defer": "FIXED_IN_EXECUTION_VEHICLE_ONLY",
            "status": "RESOLVED",
        },
    ]
    if terminal_error is not None:
        entries.append(
            {
                "flaw_id": "RFL-20260823-CURRENT-FAILURE",
                "timestamp_or_phase": "current_execution",
                "category": "RUN_BLOCKER",
                "severity": "P0_PENDING_CLASSIFICATION",
                "observed_symptom": terminal_error,
                "reproduction": "current immutable execution artifact",
                "affected_stage": "current_execution",
                "affected_candidates": "SEE_RAW_ARTIFACTS",
                "affected_evidence": "CURRENT_EVIDENCE_CONSUMED_BEFORE_FAILURE" if evidence_consumed else "NONE",
                "root_cause_or_best_hypothesis": "UNKNOWN_PENDING_LOG_REVIEW",
                "confidence": "OBSERVED_FAILURE",
                "decision_materiality": "FAIL_CLOSED",
                "current_run_validity_impact": "REVIEW_REQUIRED",
                "recommended_fix": "classify before any reuse",
                "recommended_test": "reproduce failing stage without crossing evidence boundaries",
                "patch_now_or_defer": "REVIEW_REQUIRED",
                "status": "OPEN",
            }
        )
    write_json(output_dir / "RUN_FLAW_LEDGER.json", {"schema_version": "1.1.0", "manifest_hash": manifest_hash, "entries": entries})

    search_payload = search.get("search") if isinstance(search, dict) else None
    if isinstance(search_payload, dict):
        generations = search_payload.get("generations")
        archive = search_payload.get("archive")
        diversity = {
            "status": "MEASURED_FROM_OPTIMIZER_SEARCH_REPORT",
            "unique_legal_decks_generated": search_payload.get("unique_legal_decks", "NOT_MEASURED"),
            "unique_legal_decks_evaluated": search_payload.get("unique_legal_decks", "NOT_MEASURED"),
            "duplicate_decks_removed": "NOT_EXPLICITLY_EXPOSED",
            "search_generations": len(generations) - 1 if isinstance(generations, list) else "NOT_MEASURED",
            "qd_cells_occupied": extract_archive_cell_count(archive),
            "qd_archive": archive if isinstance(archive, dict) else "NOT_MEASURED",
            "operator_weights": search_payload.get("operator_weights", "NOT_MEASURED"),
            "policy_weights": search_payload.get("policy_weights", "NOT_MEASURED"),
            "screening_only_count": len(search_payload.get("screening_only_hashes", [])) if isinstance(search_payload.get("screening_only_hashes"), list) else "NOT_MEASURED",
            "requested_scenario_pairs": search_payload.get("requested_scenario_pairs", "NOT_MEASURED"),
            "evaluation_calls": search_payload.get("evaluation_calls", "NOT_MEASURED"),
            "candidate_card_exposure": "NOT_MEASURED_BY_CURRENT_REPORT",
            "package_coverage": "NOT_MEASURED_BY_CURRENT_REPORT",
            "mana_curve_diversity": "NOT_MEASURED_BY_CURRENT_REPORT",
            "role_profile_diversity": "NOT_MEASURED_BY_CURRENT_REPORT",
            "finish_axis_diversity": "NOT_MEASURED_BY_CURRENT_REPORT",
        }
    else:
        diversity = {"status": "NOT_RUN", "reason": "search report absent"}
    write_json(output_dir / "SEARCH_DIVERSITY_REPORT.json", diversity)
    write_json(output_dir / "QD_ARCHIVE_REPORT.json", {"status": diversity.get("status"), "qd_cells_occupied": diversity.get("qd_cells_occupied", "NOT_RUN"), "archive": diversity.get("qd_archive", "NOT_RUN")})
    write_json(output_dir / "PAIRING_INTEGRITY_AUDIT.json", {"status": "RAW_RUNTIME_AUDIT_CAPTURED" if search_audit or confirm_audit or holdout_audit else "NOT_RUN", "search_audit": search_audit, "confirmatory_audit": confirm_audit, "holdout_audit": holdout_audit, "truth_boundary": "pairing claims are limited to manifest-bound runtime audit outputs"})
    write_json(output_dir / "RNG_DETERMINISM_AUDIT.json", {"status": "MANIFEST_AND_RUNTIME_BOUND" if evidence_consumed else "NOT_RUN", "manifest_hash": manifest_hash, "canonical_main_commit": expected_commit, "canonical_main_tree": expected_tree, "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED", "UNKNOWN"), "truth_boundary": "no external replication claim"})
    write_json(output_dir / "CACHE_INTEGRITY_AUDIT.json", {"status": "RAW_RUNTIME_AUDIT_CAPTURED" if search_audit or confirm_audit or holdout_audit else "NOT_RUN", "manifest_hash": manifest_hash, "search_audit": search_audit, "confirmatory_audit": confirm_audit, "holdout_audit": holdout_audit})
    write_json(output_dir / "RUNTIME_HEALTH_TIMELINE.json", {"durations_seconds": dict(durations), "terminal_error": terminal_error, "timestamp": utc_now()})
    write_json(output_dir / "PERFORMANCE_PROFILE.json", {"durations_seconds": dict(durations)})

    if fidelity is not None:
        write_json(output_dir / "CANDIDATE_FIDELITY_ROUTING.json", fidelity)
    if confirm is not None:
        write_json(output_dir / "CONFIRMATORY_RESULTS.json", confirm)
    if diagnostics is not None:
        denial = [row for row in diagnostics.get("rows", []) if isinstance(row, dict) and str(row.get("condition", "")).startswith("deny_")]
        ablation = [row for row in diagnostics.get("rows", []) if isinstance(row, dict) and str(row.get("condition", "")).startswith("ablate_")]
        write_json(output_dir / "COMMANDER_DENIAL_RESULTS.json", {"rows": denial, "truth_boundary": diagnostics.get("evidence_boundary")})
        write_json(output_dir / "PACKAGE_ABLATION_RESULTS.json", {"rows": ablation, "truth_boundary": diagnostics.get("evidence_boundary")})
    if holdout is not None:
        write_json(output_dir / "SEALED_HOLDOUT_RESULT.json", holdout)

    for name, scope in (
        ("SEAT_ROBUSTNESS.json", "confirmatory raw evidence if exposed"),
        ("OPPONENT_ROBUSTNESS.json", "confirmatory raw evidence if exposed"),
        ("MANA_CURVE_ROLE_REPORT.json", "exact finalist variants + runtime telemetry"),
        ("T1_TELEMETRY_REPORT.json", "T1 runtime telemetry"),
        ("T2_REBUILD_REPORT.json", "T2 runtime telemetry"),
        ("WORST_CASE_REPORT.json", "runtime lower-tail evidence"),
    ):
        path = output_dir / name
        if not path.exists():
            write_json(path, {"status": "NOT_MEASURED_UNLESS_EXPOSED_IN_RAW_ARTIFACTS", "scope": scope, "not_invented": True})

    patch_recommendations: dict[str, Any] = {"P0": [], "P1": [], "P2": [], "DEFER_NOT_JUSTIFIED": [], "known_resolved": ["PR #113 calibration-first decision-integrity gate", "execution vehicle anchor-call mismatch RFL-20260823-002"], "post_run_audit_required": evidence_consumed}
    if terminal_error is not None:
        patch_recommendations["P0"].append("Classify current failure before any new decision run")
    write_json(output_dir / "PATCH_RECOMMENDATIONS.json", patch_recommendations)
    write_json(output_dir / "RUN_SPEC.json", {"scope": "official_fresh_rogshai_optimizer_v2", "operational_pod_size": 4, "manifest_hash": manifest_hash, "manifest_seed": manifest_seed, "canonical_main_commit": expected_commit, "canonical_main_tree": expected_tree, "holdout_policy": "one frozen challenger; one look; exactly 2048 paired 4P scenarios", "structural_truth_boundary": "structural_model_estimates != empirical_winrates", "tactical_truth_boundary": "Tactical Oracle != external_rules_engine", "canonical_domain_mutation_allowed": False})
    write_json(output_dir / "MANIFEST_REFERENCE.json", {"manifest_hash": manifest_hash, "seed": manifest_seed, "canonical_main_commit": expected_commit, "canonical_main_tree": expected_tree})

    final_bundle = {
        "OFFICIAL_FRESH_RUN_COMPLETE": terminal_error is None and search is not None,
        "RUN_STARTED": evidence_consumed,
        "RUN_VALID": terminal_error is None and evidence_consumed,
        "CANONICAL_MAIN_COMMIT": expected_commit,
        "CANONICAL_MAIN_TREE": expected_tree,
        "MANIFEST_HASH": manifest_hash,
        "MANIFEST_SEED": manifest_seed,
        "4P_ONLY": True,
        "CANDIDATE_POOL_COUNT": preflight.get("candidate_count") if preflight else None,
        "SEMANTIC_UNKNOWN_COUNT": preflight.get("semantic_unknown_count") if preflight else None,
        "UNIQUE_LEGAL_DECKS_GENERATED": diversity.get("unique_legal_decks_generated", "NOT_RUN"),
        "UNIQUE_LEGAL_DECKS_EVALUATED": diversity.get("unique_legal_decks_evaluated", "NOT_RUN"),
        "DUPLICATE_DECKS_REMOVED": diversity.get("duplicate_decks_removed", "NOT_RUN"),
        "QD_CELLS_OCCUPIED": diversity.get("qd_cells_occupied", "NOT_RUN"),
        "SEARCH_GENERATIONS": diversity.get("search_generations", "NOT_RUN"),
        "TOTAL_STRUCTURAL_GAMES": "NOT_MEASURED_AS_SINGLE_FULL_RUN_TOTAL",
        "TOTAL_PAIRED_COMPARISONS": "NOT_MEASURED_AS_SINGLE_FULL_RUN_TOTAL",
        "EXPLORATORY_COMPLETE": search is not None,
        "CONFIRMATORY_COMPLETE": confirm is not None,
        "CONFIRMATORY_CANDIDATES": confirm.get("shortlist_size") if confirm else 0,
        "CRITICAL_DIAGNOSTICS_COMPLETE": diagnostics is not None,
        "HOLDOUT_OPENED": holdout_opened,
        "HOLDOUT_GAMES": 2048 if holdout_opened else 0,
        "OFFICIAL_WINNER_DECLARED": bool(holdout and holdout.get("official_winner_declared") is True),
        "PAIRING_INTEGRITY": "SEE_PAIRING_INTEGRITY_AUDIT",
        "CACHE_INTEGRITY": "SEE_CACHE_INTEGRITY_AUDIT",
        "RNG_INTEGRITY": "SEE_RNG_DETERMINISM_AUDIT",
        "CROSS_PARTITION_INTEGRITY": "PASS_BY_FROZEN_MANIFEST_PREFLIGHT" if preflight else "NOT_RUN",
        "CANONICAL_DECK_CHANGED": False,
        "INVENTORY_CHANGED": False,
        "ALLOCATION_CHANGED": False,
        "PURCHASE_CHANGED": False,
        "OPPONENT_TRUTH_CHANGED": False,
        "FINAL_CHALLENGER_FREEZE": freeze,
        "HOLDOUT_DECISION": holdout.get("decision") if holdout else None,
        "PROPOSED_ONLY": bool(freeze),
        "NOT_CANONICAL": bool(freeze),
        "NOT_APPLIED": bool(freeze),
        "terminal_error": terminal_error,
    }
    write_json(output_dir / "FINAL_DECISION_BUNDLE.json", final_bundle)
    human = [
        "# Official Fresh RogShai Optimizer-v2 Run Closeout",
        "",
        f"- canonical main: `{expected_commit}` / `{expected_tree}`",
        f"- manifest: `{manifest_hash}`",
        "- operational simulations: 4-player Commander only",
        "- Structural results are `structural_model_estimates`, not empirical win rates.",
        f"- run started: `{evidence_consumed}`",
        f"- holdout opened: `{holdout_opened}`",
        f"- official winner declared: `{bool(holdout and holdout.get('official_winner_declared') is True)}`",
        "- canonical deck/inventory/allocation/opponent truth mutated: `False`",
    ]
    if terminal_error:
        human.extend(["", "## Fail-closed error", "", terminal_error])
    if freeze:
        human.extend(["", "## Frozen proposed challenger", "", f"- deck hash: `{freeze.get('challenger_deck_hash')}`", "- status: `PROPOSED_ONLY / NOT_CANONICAL / NOT_APPLIED`"])
    (output_dir / "FINAL_HUMAN_REPORT.md").write_text("\n".join(human) + "\n", encoding="utf-8")

    checksum_lines: list[str] = []
    for path in sorted(p for p in output_dir.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt"):
        checksum_lines.append(f"{sha256_file(path)}  {path.relative_to(output_dir).as_posix()}")
    (output_dir / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def execute_campaign(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    durations: dict[str, float] = {}
    terminal_error: str | None = None
    try:
        started = time.perf_counter()
        non_consuming_readiness(
            root=root,
            manifest_path=manifest_path,
            output_dir=output_dir,
            expected_commit=args.expected_commit,
            expected_tree=args.expected_tree,
            expected_manifest_hash=args.expected_manifest_hash,
            expected_manifest_file_sha256=args.expected_manifest_file_sha256,
            expected_seed=args.expected_seed,
        )
        durations["readiness"] = time.perf_counter() - started
        stage_integrity(output_dir=output_dir, phase="pre_evidence", root=root, expected_commit=args.expected_commit, expected_tree=args.expected_tree, manifest_hash=args.expected_manifest_hash, holdout_opened=False)
        if args.mode == "preflight":
            return 0

        _, durations["search"] = run_cli(
            root=root,
            output_dir=output_dir,
            label="exploratory-cli",
            args=("run", "--manifest", str(manifest_path), "--output-dir", str(output_dir), "--workers", str(args.workers), "--max-turns", str(args.max_turns), "--root", str(root)),
        )
        calibration = load_json(output_dir / "calibration-report.json")
        search = load_json(output_dir / "optimizer-search-report.json")
        if calibration.get("calibration_acceptance_pass") is not True:
            raise RuntimeError("calibration did not pass")
        if search.get("calibration_acceptance_pass") is not True:
            raise RuntimeError("search report does not attest calibration pass")
        if search.get("confirmatory_partition_opened") is not False:
            raise RuntimeError("confirmatory partition opened during search")
        if search.get("sealed_holdout_partition_opened") is not False:
            raise RuntimeError("holdout partition opened during search")
        write_json(output_dir / "CALIBRATION_RESULTS.json", calibration)
        write_json(output_dir / "EXPLORATORY_SEARCH_REPORT.json", search)
        stage_integrity(output_dir=output_dir, phase="post_search", root=root, expected_commit=args.expected_commit, expected_tree=args.expected_tree, manifest_hash=args.expected_manifest_hash, holdout_opened=False)

        fidelity_payload, durations["fidelity"] = run_cli(
            root=root,
            output_dir=output_dir,
            label="fidelity-cli",
            args=("fidelity", "--frontier", str(output_dir / "frontier-handoff.json"), "--root", str(root)),
        )
        if fidelity_payload is None:
            raise RuntimeError("fidelity CLI did not return JSON")
        fidelity = fidelity_payload
        write_json(output_dir / "frontier-fidelity.json", fidelity)
        write_json(output_dir / "CANDIDATE_FIDELITY_ROUTING.json", fidelity)
        if fidelity.get("pass") is not True:
            stage_integrity(output_dir=output_dir, phase="fidelity_no_structural_shortlist", root=root, expected_commit=args.expected_commit, expected_tree=args.expected_tree, manifest_hash=args.expected_manifest_hash, holdout_opened=False)
            return 0

        _, durations["confirmatory"] = run_cli(
            root=root,
            output_dir=output_dir,
            label="confirmatory-cli",
            args=("confirm", "--manifest", str(manifest_path), "--frontier", str(output_dir / "frontier-handoff.json"), "--output-dir", str(output_dir), "--workers", str(args.workers), "--max-turns", str(args.max_turns), "--root", str(root)),
        )
        confirm = load_json(output_dir / "confirmatory-report.json")
        if confirm.get("manifest_hash") != args.expected_manifest_hash:
            raise RuntimeError("confirmatory manifest mismatch")
        if confirm.get("sealed_holdout_partition_opened") is not False:
            raise RuntimeError("holdout opened during confirmatory")
        stage_integrity(output_dir=output_dir, phase="post_confirmatory", root=root, expected_commit=args.expected_commit, expected_tree=args.expected_tree, manifest_hash=args.expected_manifest_hash, holdout_opened=False)
        challenger = confirm.get("single_challenger_hash")
        if not isinstance(challenger, str) or not challenger:
            return 0

        _, durations["critical_diagnostics"] = run_cli(
            root=root,
            output_dir=output_dir,
            label="diagnostics-cli",
            args=("diagnose", "--manifest", str(manifest_path), "--confirmatory", str(output_dir / "confirmatory-report.json"), "--output-dir", str(output_dir), "--workers", str(args.workers), "--max-turns", str(args.max_turns), "--root", str(root)),
        )
        diagnostics = load_json(output_dir / "critical-diagnostics-report.json")
        if diagnostics.get("manifest_hash") != args.expected_manifest_hash:
            raise RuntimeError("critical diagnostics manifest mismatch")
        if diagnostics.get("challenger_hash") != challenger:
            raise RuntimeError("critical diagnostics challenger mismatch")
        stage_integrity(output_dir=output_dir, phase="post_diagnostics", root=root, expected_commit=args.expected_commit, expected_tree=args.expected_tree, manifest_hash=args.expected_manifest_hash, holdout_opened=False)
        if diagnostics.get("critical_diagnostics_pass") is not True:
            return 0

        freeze = freeze_challenger(root=root, output_dir=output_dir, manifest_hash=args.expected_manifest_hash, expected_commit=args.expected_commit, expected_tree=args.expected_tree, confirmatory=confirm)
        if (output_dir / "holdout-report.json").exists():
            raise RuntimeError("holdout report existed before authorized one-look opening")
        if freeze.get("holdout_looks_authorized") != 1:
            raise RuntimeError("challenger freeze does not authorize exactly one holdout look")

        _, durations["sealed_holdout"] = run_cli(
            root=root,
            output_dir=output_dir,
            label="holdout-cli",
            args=("holdout", "--manifest", str(manifest_path), "--confirmatory", str(output_dir / "confirmatory-report.json"), "--diagnostics", str(output_dir / "critical-diagnostics-report.json"), "--output-dir", str(output_dir), "--authorize-holdout", "--workers", str(args.workers), "--max-turns", str(args.max_turns), "--root", str(root)),
        )
        holdout = load_json(output_dir / "holdout-report.json")
        if holdout.get("single_frozen_challenger_hash") != freeze.get("challenger_deck_hash"):
            raise RuntimeError("holdout challenger does not match frozen challenger")
        if holdout.get("paired_4p_budget") != 2048 or holdout.get("planned_looks") != 1:
            raise RuntimeError("holdout violated one-look 2048-pair contract")
        stage_integrity(output_dir=output_dir, phase="post_holdout", root=root, expected_commit=args.expected_commit, expected_tree=args.expected_tree, manifest_hash=args.expected_manifest_hash, holdout_opened=True)
        return 0
    except Exception as exc:
        terminal_error = f"{type(exc).__name__}: {exc}"
        (output_dir / "TERMINAL_ERROR.txt").write_text(terminal_error + "\n", encoding="utf-8")
        return 1
    finally:
        closeout(output_dir=output_dir, expected_commit=args.expected_commit, expected_tree=args.expected_tree, manifest_hash=args.expected_manifest_hash, manifest_seed=args.expected_seed, durations=durations, terminal_error=terminal_error)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("preflight", "execute"), required=True)
    p.add_argument("--root", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--expected-tree", required=True)
    p.add_argument("--expected-manifest-hash", required=True)
    p.add_argument("--expected-manifest-file-sha256", required=True)
    p.add_argument("--expected-seed", type=int, required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--max-turns", type=int, default=35)
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(execute_campaign(parse_args()))

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.project_context import ProjectContextSnapshot, load_project_context
from commander_lab.storage.database import SCHEMA_VERSION

J_P6_MERGED_BASELINE_COMMIT = "5d1b77796c9ae75173855a54f6e531cc3a0c7814"
_OFFICIAL_RUN_RELATIVE_PATH = Path("data/runs/current/OFFICIAL_ROGSHAI_RUN_CURRENT.json")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _is_ancestor(root: Path, ancestor: str) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, "HEAD"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def _json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _string_list(payload: dict[str, Any], key: str) -> list[str]:
    raw = payload.get(key)
    if not isinstance(raw, list):
        return []
    return [str(value) for value in raw]


def _official_run_truth(root: Path, context: ProjectContextSnapshot) -> dict[str, Any]:
    path = root / _OFFICIAL_RUN_RELATIVE_PATH
    if not path.is_file():
        raise ValueError(f"official run truth pointer is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"official run truth pointer is malformed: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("official run truth pointer must be a JSON object")

    if payload.get("schema_version") != "1.0.0":
        raise ValueError("unsupported official run truth schema")
    if payload.get("status") != "completed":
        raise ValueError("current official run truth must identify a completed run")

    completed_at = payload.get("completed_at")
    if not isinstance(completed_at, str):
        raise ValueError("official run truth has no completed_at timestamp")
    try:
        parsed_completed_at = datetime.fromisoformat(completed_at)
    except ValueError as exc:
        raise ValueError("official run truth completed_at is not ISO-8601") from exc
    if parsed_completed_at.tzinfo is None:
        raise ValueError("official run truth completed_at must include a timezone")

    git_commit = payload.get("git_commit")
    if not isinstance(git_commit, str) or _HEX40.fullmatch(git_commit) is None:
        raise ValueError("official run truth has an invalid source git commit")

    deck_id = payload.get("deck_id")
    if not isinstance(deck_id, str) or deck_id not in context.active_own_deck_ids:
        raise ValueError("official run truth does not reference a current active own deck")
    active_hashes = dict(context.active_deck_hashes)
    deck_hash = payload.get("deck_hash")
    if not isinstance(deck_hash, str) or _HEX64.fullmatch(deck_hash) is None:
        raise ValueError("official run truth has an invalid deck hash")
    if active_hashes.get(deck_id) != deck_hash:
        raise ValueError("official run truth deck hash is stale relative to current active deck")

    for key in ("project_context_hash", "seed_set_hash"):
        value = payload.get(key)
        if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
            raise ValueError(f"official run truth has an invalid {key}")

    if payload.get("evidence_class") != "structural_model_estimates":
        raise ValueError("official run truth has an invalid evidence class")
    if payload.get("evidence_boundary") != "structural_model_estimates != empirical_winrates":
        raise ValueError("official run truth lost the structural evidence boundary")
    if payload.get("canonical_mutation") is not False:
        raise ValueError("official run truth may not claim a canonical mutation")
    if payload.get("authorization_required") is not True:
        raise ValueError("official run truth lost the authorization boundary")

    source = payload.get("source")
    if not isinstance(source, dict) or source.get("type") != "official_structural_run":
        raise ValueError("official run truth has no valid provenance source")
    for key in ("artifact_stamp", "identity_artifact", "report_artifact"):
        if not isinstance(source.get(key), str) or not source[key]:
            raise ValueError(f"official run truth source is missing {key}")

    return {**payload, "truth_pointer": _OFFICIAL_RUN_RELATIVE_PATH.as_posix()}


def build_technical_truth(root: str | Path) -> dict[str, Any]:
    """Return one read-only technical status projection derived from current repo inputs."""

    root_path = Path(root).resolve()
    context = load_project_context(root_path)
    official_run = _official_run_truth(root_path, context)
    pod_payload = _json_object(root_path / "data/collections/current/POD_SCENARIOS_CURRENT.json")
    feature_manifest = _json_object(
        root_path / "data/collections/current/rogshai_feature_projection/manifest.json"
    )
    active_scope = _json_object(
        root_path / "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json"
    )
    engine_config = _json_object(root_path / "config/rules_engines.json")

    git_commit = _git(root_path, "rev-parse", "HEAD")
    git_tree = _git(root_path, "rev-parse", "HEAD^{tree}")
    git_branch = _git(root_path, "branch", "--show-current")
    tracked_status = _git(root_path, "status", "--porcelain", "--untracked-files=no")
    tracked_dirty = None if tracked_status is None else bool(tracked_status)

    runtime_loaded = _string_list(active_scope, "runtime_loaded_decks")
    if not runtime_loaded:
        runtime_loaded = list(context.active_own_deck_ids)
    global_active = _string_list(active_scope, "global_active_own_decks")
    if not global_active:
        global_active = _string_list(active_scope, "active_own_decks") or list(
            context.active_own_deck_ids
        )
    optimization_targets = _string_list(active_scope, "optimization_targets")
    if not optimization_targets:
        optimization_targets = [context.primary_deckbuilding_focus]
    unresolved = _string_list(active_scope, "unresolved_operational_baselines")

    provider_status = str(engine_config.get("provider_decision") or "unknown")
    primary_engine = engine_config.get("primary_engine")
    primary_engine_payload = primary_engine if isinstance(primary_engine, dict) else {}
    external_ready = bool(primary_engine_payload.get("production_ready", False)) and (
        provider_status != "NO_PROVIDER_READY"
    )
    blockers: list[str] = []
    documented_limitations: list[str] = []
    if not external_ready:
        documented_limitations.append("external_rules_engine_validation_pending")
    if unresolved:
        documented_limitations.append("unresolved_operational_own_deck_baseline")

    return {
        "technical_truth_version": 3,
        "package_version": __version__,
        "git": {
            "commit": git_commit,
            "tree": git_tree,
            "branch": git_branch,
            "tracked_dirty": tracked_dirty,
        },
        "engine_version": ENGINE_VERSION,
        "schema_versions": {
            "database": SCHEMA_VERSION,
            "pod_scenarios": pod_payload.get("schema_version", "unknown"),
            "feature_projection": feature_manifest.get("schema_version", "unknown"),
            "active_scope": active_scope.get("schema_version", "unknown"),
            "rules_engines": engine_config.get("schema_version", "unknown"),
            "official_run_truth": official_run.get("schema_version", "unknown"),
        },
        "global_active_own_deck_set": global_active,
        "runtime_loaded_deck_set": runtime_loaded,
        "optimization_target_set": optimization_targets,
        "unresolved_operational_baseline_set": unresolved,
        "active_deck_set": runtime_loaded,
        "historical_own_deck_set": list(context.historical_own_deck_ids),
        "primary_deckbuilding_focus": context.primary_deckbuilding_focus,
        "active_deck_hashes": dict(context.active_deck_hashes),
        "policy_config_hashes": dict(context.policy_config_hashes),
        "canonical_context_snapshot": context.snapshot_hash,
        "playstyle_policy": {
            "preference_type": context.playstyle_preference_type,
            "stage": "post_build_review_only",
            "objective_decision_signal": False,
            "preference_hash": context.playstyle_preference_hash,
        },
        "roadmap_mvp_state": {
            "j_p6_merged_baseline_is_ancestor": _is_ancestor(
                root_path, J_P6_MERGED_BASELINE_COMMIT
            ),
            "priority_context_surface_present": (
                root_path / "src/commander_lab/project_context.py"
            ).is_file(),
            "priority_workflow_surface_present": (
                root_path / "src/commander_lab/priority_workflows.py"
            ).is_file(),
            "exact_result_cache_surface_present": (
                root_path / "src/commander_lab/storage/result_cache.py"
            ).is_file(),
            "production_adaptive_scheduler_present": (
                root_path / "src/commander_lab/adaptive_budget.py"
            ).is_file(),
            "model_informativeness_gate_present": (
                root_path / "src/commander_lab/model_informativeness.py"
            ).is_file(),
            "workflow_session_present": (
                root_path / "src/commander_lab/workflow_session.py"
            ).is_file(),
            "public_high_level_workflow_surface_present": (
                root_path / "src/commander_lab/tools/registry.py"
            ).is_file(),
        },
        "external_engine_status": {
            "provider_decision": provider_status,
            "production_provider_ready": external_ready,
            "primary_provider": primary_engine_payload.get("provider"),
            "primary_status": primary_engine_payload.get("status"),
            "primary_real_execution": primary_engine_payload.get("real_execution"),
            "primary_commit": primary_engine_payload.get("commit"),
            "production_bridge": engine_config.get("production_bridge"),
            "decision_source": "config/rules_engines.json",
            "historical_provider_decision_source": "docs/J_P3_PROVIDER_DECISION.json",
            "evidence_boundary": (
                "Current provider capability metadata can describe proven B3 external-engine "
                "execution, but provider readiness remains false until the production action loop "
                "is implemented and separately validated."
            ),
        },
        "first_run_readiness": {
            "preparation_surface_present": (
                root_path / "scripts/prepare_rogshai_first_serious_experiment.py"
            ).is_file(),
            "authorized_runner_surface_present": (
                root_path / "scripts/run_rogshai_first_serious_experiment.py"
            ).is_file(),
            "preliminary_run": {
                "classification": "preliminary_noncanonical_decision_support",
                "official_first_run": False,
                "deck_mutation_authority": False,
            },
            "official_run": official_run,
        },
        "current_blockers": blockers,
        "documented_limitations": documented_limitations,
        "truth_boundary": (
            "This projection reports repository/runtime technical state. GitHub CI conclusions and "
            "Drive freshness must still be read from their live primary systems when required."
        ),
    }


__all__ = ["build_technical_truth"]

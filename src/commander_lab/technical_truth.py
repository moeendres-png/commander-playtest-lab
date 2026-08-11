from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.project_context import load_project_context
from commander_lab.storage.database import SCHEMA_VERSION

J_P6_MERGED_BASELINE_COMMIT = "5d1b77796c9ae75173855a54f6e531cc3a0c7814"


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


def build_technical_truth(root: str | Path) -> dict[str, Any]:
    """Return one read-only technical status projection derived from primary repo inputs."""

    root_path = Path(root).resolve()
    context = load_project_context(root_path)
    pod_payload = _json_object(root_path / "data/collections/current/POD_SCENARIOS_CURRENT.json")
    feature_manifest = _json_object(
        root_path / "data/collections/current/rogshai_feature_projection/manifest.json"
    )
    active_scope = _json_object(root_path / "data/collections/current/J_FINAL_ACTIVE_SCOPE.json")
    provider_decision = _json_object(root_path / "docs/J_P3_PROVIDER_DECISION.json")

    git_commit = _git(root_path, "rev-parse", "HEAD")
    git_tree = _git(root_path, "rev-parse", "HEAD^{tree}")
    git_branch = _git(root_path, "branch", "--show-current")
    tracked_status = _git(root_path, "status", "--porcelain", "--untracked-files=no")
    tracked_dirty = None if tracked_status is None else bool(tracked_status)

    provider_status = provider_decision.get("decision") or "unknown"
    external_ready = provider_status not in {"NO_PROVIDER_READY", "unknown"}
    blockers: list[str] = []
    if not external_ready:
        blockers.append("external_rules_engine_validation_pending")

    return {
        "technical_truth_version": 1,
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
        },
        "active_deck_set": list(context.active_own_deck_ids),
        "historical_own_deck_set": list(context.historical_own_deck_ids),
        "primary_deckbuilding_focus": context.primary_deckbuilding_focus,
        "canonical_context_snapshot": context.snapshot_hash,
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
        },
        "external_engine_status": {
            "provider_decision": provider_status,
            "production_provider_ready": external_ready,
            "decision_source": "docs/J_P3_PROVIDER_DECISION.json",
            "evidence_boundary": (
                "Provider readiness metadata is technical project status, not evidence that an "
                "external rules engine executed any current deck experiment."
            ),
        },
        "current_blockers": blockers,
        "truth_boundary": (
            "This projection reports repository/runtime technical state. GitHub CI conclusions and "
            "Drive freshness must still be read from their live primary systems when required."
        ),
    }


__all__ = ["build_technical_truth"]

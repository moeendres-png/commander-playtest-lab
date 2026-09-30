from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.project_context import load_project_context
from commander_lab.storage.database import SCHEMA_VERSION
from commander_lab.technical_truth import _official_run_truth, build_technical_truth

ROOT = Path(__file__).resolve().parents[2]


def test_technical_truth_derives_current_versions_scope_and_engine_boundary() -> None:
    truth = build_technical_truth(ROOT)
    assert truth["technical_truth_version"] == 3
    assert truth["package_version"] == __version__
    assert truth["engine_version"] == ENGINE_VERSION
    assert truth["schema_versions"]["database"] == SCHEMA_VERSION
    assert truth["schema_versions"]["official_run_truth"] == "1.0.0"
    assert truth["global_active_own_deck_set"] == ["rogshai/current"]
    assert truth["runtime_loaded_deck_set"] == ["rogshai/current"]
    assert truth["optimization_target_set"] == ["rogshai/current"]
    assert truth["unresolved_operational_baseline_set"] == []
    assert truth["active_deck_set"] == ["rogshai/current"]
    assert truth["historical_own_deck_set"] == []
    assert truth["primary_deckbuilding_focus"] == "rogshai/current"
    assert truth["active_deck_hashes"] == {
        "rogshai/current": "1704b6f1574e4d3152f08cf9936c389683f0ae6efa98a8a277a64daa37f583e3"
    }
    assert truth["playstyle_policy"]["stage"] == "post_build_review_only"
    assert truth["playstyle_policy"]["objective_decision_signal"] is False
    assert len(truth["canonical_context_snapshot"]) == 64
    # Full history (CI checks out with fetch-depth 0) proves ancestry; a shallow clone
    # cannot, and must report UNKNOWN rather than a false "not an ancestor".
    shallow = (
        subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--is-shallow-repository"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        == "true"
    )
    assert truth["roadmap_mvp_state"]["j_p6_merged_baseline_is_ancestor"] is (
        None if shallow else True
    )
    assert truth["roadmap_mvp_state"]["priority_context_surface_present"] is True
    assert truth["roadmap_mvp_state"]["priority_workflow_surface_present"] is True
    assert truth["roadmap_mvp_state"]["exact_result_cache_surface_present"] is True
    assert truth["roadmap_mvp_state"]["production_adaptive_scheduler_present"] is True
    assert truth["roadmap_mvp_state"]["model_informativeness_gate_present"] is True
    assert truth["roadmap_mvp_state"]["workflow_session_present"] is True
    assert truth["roadmap_mvp_state"]["public_high_level_workflow_surface_present"] is True
    external = truth["external_engine_status"]
    assert external["provider_decision"] == "NO_PROVIDER_READY"
    assert external["production_provider_ready"] is False
    assert external["primary_provider"] == "xmage"
    assert external["primary_status"] == "B4D_EVENT_LOG_LIFECYCLE_VALIDATED_DEGRADED"
    assert external["primary_real_execution"] is True
    assert external["decision_source"] == "config/rules_engines.json"
    assert external["historical_provider_decision_source"] == "docs/J_P3_PROVIDER_DECISION.json"
    assert truth["current_blockers"] == []
    assert "external_rules_engine_validation_pending" in truth["documented_limitations"]
    assert "unresolved_operational_own_deck_baseline" not in truth["documented_limitations"]
    readiness = truth["first_run_readiness"]
    assert readiness["preparation_surface_present"] is True
    assert readiness["authorized_runner_surface_present"] is True
    assert readiness["preliminary_run"]["official_first_run"] is False
    official = readiness["official_run"]
    assert official["status"] == "completed"
    assert official["deck_id"] == "rogshai/current"
    assert official["deck_hash"] == (
        "1704b6f1574e4d3152f08cf9936c389683f0ae6efa98a8a277a64daa37f583e3"
    )
    assert official["git_commit"] == "12a0b35e1bf8ee54b6ccc39db57682d35c3a1dc7"
    assert official["project_context_hash"] == (
        "c600722324fb62157d450a50a1907eea9d80c60453d5b6007c746b34f16477d9"
    )
    assert official["seed_set_hash"] == (
        "4131880dd7b3998afb7d74c5e288fb9aaeb52b0913c68c2c9490ac910c8a9ba6"
    )
    assert official["evidence_class"] == "structural_model_estimates"
    assert official["evidence_boundary"] == "structural_model_estimates != empirical_winrates"
    assert official["canonical_mutation"] is False
    assert official["truth_pointer"] == "data/runs/current/OFFICIAL_ROGSHAI_RUN_CURRENT.json"
    assert truth["git"]["commit"]
    assert truth["git"]["tree"]


def _write_pointer(root: Path, payload: str) -> None:
    path = root / "data/runs/current/OFFICIAL_ROGSHAI_RUN_CURRENT.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def test_official_run_truth_fails_closed_on_malformed_pointer(tmp_path: Path) -> None:
    context = load_project_context(ROOT)
    _write_pointer(tmp_path, "{malformed")
    with pytest.raises(ValueError, match="malformed"):
        _official_run_truth(tmp_path, context)


def test_official_run_truth_fails_closed_on_stale_deck_hash(tmp_path: Path) -> None:
    context = load_project_context(ROOT)
    source = ROOT / "data/runs/current/OFFICIAL_ROGSHAI_RUN_CURRENT.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["deck_hash"] = "0" * 64
    _write_pointer(tmp_path, json.dumps(payload))
    with pytest.raises(ValueError, match="stale"):
        _official_run_truth(tmp_path, context)


def test_is_ancestor_reports_unknown_only_when_history_is_shallow(tmp_path: Path) -> None:
    from commander_lab.technical_truth import _is_ancestor

    env = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(tmp_path),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "PATH": "/usr/bin:/bin",
    }

    def git(*args: str, cwd: Path) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
        ).stdout.strip()

    full = tmp_path / "full"
    full.mkdir()
    git("init", "-q", "-b", "main", cwd=full)
    git("commit", "-q", "--allow-empty", "-m", "base", cwd=full)
    base = git("rev-parse", "HEAD", cwd=full)
    for n in range(3):
        git("commit", "-q", "--allow-empty", "-m", f"c{n}", cwd=full)
    git("checkout", "-q", "--orphan", "side", cwd=full)
    git("commit", "-q", "--allow-empty", "-m", "unrelated", cwd=full)
    unrelated = git("rev-parse", "HEAD", cwd=full)
    git("checkout", "-q", "main", cwd=full)

    assert _is_ancestor(full, base) is True
    assert _is_ancestor(full, unrelated) is False, "full history proves 'not an ancestor'"

    shallow = tmp_path / "shallow"
    git(
        "clone",
        "-q",
        "--depth",
        "1",
        "--no-single-branch",
        f"file://{full}",
        str(shallow),
        cwd=tmp_path,
    )
    git("fetch", "-q", "--depth", "1", "origin", base, cwd=shallow)
    assert _is_ancestor(shallow, base) is None, "a shallow clone cannot prove either way"

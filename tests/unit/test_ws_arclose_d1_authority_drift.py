"""WS-ARCLOSE-D1 current-authority drift-closure regression tests.

Structural only (no Docker, no network, no engine builds). Each test locks
the remediated current-authority wording so the six audit findings cannot
silently regress, while historical evidence stays preserved verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

CANONICAL_XMAGE_PIN = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
CANONICAL_FORGE_PIN = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
STALE_XMAGE_PIN = "06d166b098ad36b277edef01116472203d5a047e"
STALE_FORGE_PIN = "852066bf4f761b302ed17cb011999d8a8fe08ad6"


def _flat(text: str) -> str:
    """Collapse all whitespace so line-wrapped Markdown still matches."""
    return " ".join(text.split())


def _manifest(repo_root: Path) -> dict:
    return json.loads((repo_root / "config/rules_engines.json").read_text(encoding="utf-8"))


def test_manifest_pins_protocol_capabilities_untouched(repo_root: Path) -> None:
    manifest = _manifest(repo_root)
    assert manifest["primary_engine"]["commit"] == CANONICAL_XMAGE_PIN
    assert manifest["secondary_engine"]["commit"] == CANONICAL_FORGE_PIN
    assert manifest["protocol_version"] == "2.0.0"
    assert manifest["provider_decision"] == "NO_PROVIDER_READY"
    assert manifest["current_runtime"]["provider_selected"] is False
    assert manifest["current_runtime"]["production_provider"] is None


def test_manifest_no_longer_claims_dockerfile_stale_defaults(repo_root: Path) -> None:
    note = _manifest(repo_root)["authority_note"]["known_stale_pointers"]
    assert "NO LONGER carry stale default pins" in note
    assert "REQUIRED build args" in note
    assert "phase85.py" in note  # historical template provenance preserved
    assert "PIN_DIVERGENCE_DOCKERFILES" in note  # gate reference preserved
    # The pre-WS-A1D clause ("Dockerfiles ... carry older pins") must be gone.
    assert "carry older pins" not in note


def test_dockerfiles_carry_no_stale_default_pins(repo_root: Path) -> None:
    for rel in ("docker/xmage/Dockerfile", "docker/forge/Dockerfile"):
        text = _flat((repo_root / rel).read_text(encoding="utf-8"))
        assert STALE_XMAGE_PIN not in text, rel
        assert STALE_FORGE_PIN not in text, rel
        assert "ARG ENGINE_COMMIT" in text, rel
        assert "intentionally no" in text and "defaults" in text, rel


def test_retention_appendix_g_preserves_history_and_records_h4_successor(
    repo_root: Path,
) -> None:
    text = (repo_root / "docs/RETENTION_AND_LIFECYCLE_POLICY.md").read_text(encoding="utf-8")
    # Original WS-A1R/WS-A1D record untouched.
    assert "docker/forge/Dockerfile` defaults to `852066bf`" in text
    assert "NOT_RUN on the WS-A1D execution host: no Docker client there" in text
    # Dated addendum records successor truth without rewriting history.
    assert "WS-ARCLOSE-D1 addendum (2026-09-13" in text
    assert "h4-docker-materialization.yml" in text
    assert "H4 PARTIAL" in text
    assert "H4B-Forge" in text and "UNKNOWN/NOT_RUN" in text


def test_root_state_owned_by_this_workstream_and_valid(repo_root: Path) -> None:
    import sys

    sys.path.insert(0, str(repo_root / "tools"))
    from foundry import state as state_mod

    data = yaml.safe_load(
        (repo_root / ".foundry/WORKSTREAM_STATE.yaml").read_text(encoding="utf-8")
    )
    assert state_mod.validate(data) == []
    assert data["branch"] == "ws-arclose/d1-current-authority-drift-20260913"
    assert data["worktree"] == "/home/moeen/code/ws-arclose-d1"
    assert data["ownership"] == "WS-ARCLOSE-D1"
    assert data["status"] == "ACTIVE"
    assert data["validated_head"] is None  # honest null: nothing validated on this branch yet
    assert "ARCHITECTURE_FREEZE = NOT CLAIMED" in data["hard_gates"]
    assert "PRODUCTION_PROVIDER = NOT SELECTED" in data["hard_gates"]
    # WS-A1D-H4 provenance preserved, not falsified.
    decisions = " ".join(
        d.get("decision", "") + " " + d.get("evidence", "")
        for d in data.get("technical_decisions", [])
        if isinstance(d, dict)
    )
    assert "1aab0121" in decisions
    assert "H4 PARTIAL" in decisions


def test_mage_profile_keys_intact_and_notes_date_scoped(repo_root: Path) -> None:
    profile = json.loads(
        (repo_root / ".foundry/repo-profiles/mage.json").read_text(encoding="utf-8")
    )
    for key in (
        "profile",
        "repo_slug",
        "default_branch",
        "canonical_policy",
        "stale_markers",
        "forbidden_mutation",
        "safe_external_dirs",
    ):
        assert key in profile, key
    assert profile["canonical_policy"] is False
    assert profile["default_branch"] == "master"
    assert "WS33_COMPLETE" in profile["stale_markers"]  # fail-closed gate untouched
    notes = profile["notes"]
    assert "HISTORICAL observation 2026-09-10" in notes
    assert "UNKNOWN" in notes  # current fork-root state not claimed
    assert "Never create project files" in notes


def test_remote_gates_scope_and_workflow_truth(repo_root: Path) -> None:
    text = _flat(
        (repo_root / "docs/foundry-execution/GITHUB_REMOTE_GATES.md").read_text(encoding="utf-8")
    )
    # Observed-state record preserved.
    assert "Observed state (2026-09-12, DIRECTLY_VERIFIED read-only)" in text
    # OpenCode lane must not be recommended as a required PR check.
    assert "Do NOT mark the comment-triggered OpenCode lane" in text
    assert "and the OpenCode lane (`.github/workflows/opencode.yml`)" not in text
    # Mirror-safe governance.
    assert "fast-forward" in text
    assert "Do NOT impose" in text and "PR-only semantics" in text
    assert "Never land project-only files" in text
    # Workflow truth: comment triggers only, no pull_request trigger.
    workflow = (repo_root / ".github/workflows/opencode.yml").read_text(encoding="utf-8")
    assert "issue_comment" in workflow
    assert "\n  pull_request:" not in workflow and "\n pull_request:" not in workflow


def test_fork_pointer_spec_preserves_design_and_records_supersession(
    repo_root: Path,
) -> None:
    text = (repo_root / "docs/FORK_AGENT_POINTER_SPEC.md").read_text(encoding="utf-8")
    # Original WS-A1R design record untouched.
    assert "WS-A1R-F1 (mage pointer)" in text
    assert "WS-A1R-F2 (forge pointer)" in text
    assert "NOT executed by WS-A1R" in text
    # Dated disposition appended.
    assert "## 5. Disposition (WS-ARCLOSE-D1, 2026-09-13" in text
    assert "SUPERSEDED" in text
    assert "never executed" in text
    assert "drift_check.py" in text

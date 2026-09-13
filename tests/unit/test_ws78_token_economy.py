"""WS78 Foundry token-economy guardrails (hermetic: no network, no OpenCode binary).

Locks the WS78 implementation surface:

* compact capsule happy path + fail-closed behavior + determinism + no leakage;
* ``/work`` command structure and prompt minimality;
* conservative ``tool_output`` config plus ``compaction.prune`` default;
* permission/instruction/policy non-regression (dedup audit keeps layers);
* launcher bundle ``tool_output`` passthrough.

Capsule Git tests use throwaway local ``git init`` repositories only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

CAPSULE_REL = "tools/foundry/context_capsule.py"
COMMAND_REL = ".opencode/commands/work.md"


def _run_git(args: list[str], cwd: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr[:200]}"
    return proc.stdout.strip()


@pytest.fixture()
def scratch_repo(tmp_path: Path) -> dict:
    """A throwaway local git repo with one commit (no network, no identity leak)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(["init"], str(repo))
    _run_git(["config", "user.email", "ws78-test@example.invalid"], str(repo))
    _run_git(["config", "user.name", "ws78-test"], str(repo))
    (repo / "note.txt").write_text("ws78 capsule fixture\n", encoding="utf-8")
    _run_git(["add", "note.txt"], str(repo))
    _run_git(["commit", "-m", "ws78 fixture"], str(repo))
    return {
        "dir": str(repo),
        "head": _run_git(["rev-parse", "HEAD"], str(repo)),
        "branch": _run_git(["rev-parse", "--abbrev-ref", "HEAD"], str(repo)),
    }


def _write_state(path: Path, branch: str, audit_base: str, **overrides: object) -> Path:
    doc: dict = {
        "schema_version": "2.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "worktree": "/tmp/ws78-test-worktree",
        "branch": branch,
        "audit_base_sha": audit_base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": audit_base,
        "validated_head": None,
        "objective": "WS78 test objective",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "WS78-TEST",
        "status": "ACTIVE",
        "hard_gates": ["QUALITY_NON_REGRESSION: stay at least as strong"],
        "authority_gates": [],
        "exact_next_action": "Run the WS78 test battery.",
    }
    doc.update(overrides)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def _capsule(
    repo_root: Path, *args: str, env_extra: dict | None = None
) -> subprocess.CompletedProcess:
    # Explicit --state wins over FOUNDRY_STATE_PATH inside the helper, so the
    # ambient launcher variable is harmless; monkeypatched values flow through.
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(repo_root / CAPSULE_REL), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


# --- capsule happy path -----------------------------------------------------


def test_capsule_happy_path_text(repo_root: Path, scratch_repo: dict, tmp_path: Path):
    state = _write_state(tmp_path / "state.yaml", scratch_repo["branch"], scratch_repo["head"])
    proc = _capsule(repo_root, "--state", str(state), "--workdir", scratch_repo["dir"])
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "DERIVED/INDEX" in out
    assert "not Source Authority" in out
    assert "moeendres-png/commander-playtest-lab" in out
    assert f"branch: {scratch_repo['branch']}" in out
    assert f"live_HEAD: {scratch_repo['head']}" in out
    assert f"audit_base_sha: {scratch_repo['head']}" in out
    assert "tree_clean: yes" in out
    assert "validated_head: null" in out
    assert "objective: WS78 test objective" in out
    assert "exact_next_action: Run the WS78 test battery." in out
    assert "QUALITY_NON_REGRESSION" in out
    assert "authority_gates:\n  (none)" in out
    assert "full_state:" in out


def test_capsule_deterministic(repo_root: Path, scratch_repo: dict, tmp_path: Path):
    state = _write_state(tmp_path / "state.yaml", scratch_repo["branch"], scratch_repo["head"])
    first = _capsule(repo_root, "--state", str(state), "--workdir", scratch_repo["dir"])
    second = _capsule(repo_root, "--state", str(state), "--workdir", scratch_repo["dir"])
    assert first.returncode == 0 and second.returncode == 0
    assert first.stdout == second.stdout


def test_capsule_json_format(repo_root: Path, scratch_repo: dict, tmp_path: Path):
    state = _write_state(tmp_path / "state.yaml", scratch_repo["branch"], scratch_repo["head"])
    proc = _capsule(
        repo_root,
        "--state",
        str(state),
        "--workdir",
        scratch_repo["dir"],
        "--format",
        "json",
    )
    assert proc.returncode == 0, proc.stderr
    doc = json.loads(proc.stdout)
    assert doc["_kind"].startswith("DERIVED")
    assert doc["live_HEAD"] == scratch_repo["head"]
    assert doc["tree_clean"] is True
    assert doc["validated_head"] is None
    assert list(doc) == sorted(doc), "JSON capsule must use sorted keys"


def test_capsule_full_opt_in(repo_root: Path, scratch_repo: dict, tmp_path: Path):
    state = _write_state(tmp_path / "state.yaml", scratch_repo["branch"], scratch_repo["head"])
    proc = _capsule(repo_root, "--state", str(state), "--workdir", scratch_repo["dir"], "--full")
    assert proc.returncode == 0, proc.stderr
    assert "schema_version" in proc.stdout
    assert "Run the WS78 test battery." in proc.stdout


def test_capsule_state_path_env_default(
    repo_root: Path, scratch_repo: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    state = _write_state(tmp_path / "state.yaml", scratch_repo["branch"], scratch_repo["head"])
    monkeypatch.setenv("FOUNDRY_STATE_PATH", str(state))
    proc = _capsule(repo_root, "--workdir", scratch_repo["dir"])
    assert proc.returncode == 0, proc.stderr
    assert f"live_HEAD: {scratch_repo['head']}" in proc.stdout


def test_capsule_emits_no_environment_values(
    repo_root: Path, scratch_repo: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    state = _write_state(tmp_path / "state.yaml", scratch_repo["branch"], scratch_repo["head"])
    monkeypatch.setenv("WS78_TEST_SENTINEL", "sentinel-value-9f8c2b")
    proc = _capsule(repo_root, "--state", str(state), "--workdir", scratch_repo["dir"])
    assert proc.returncode == 0, proc.stderr
    assert "sentinel-value-9f8c2b" not in proc.stdout
    assert "WS78_TEST_SENTINEL" not in proc.stdout


# --- capsule fail-closed ----------------------------------------------------


def test_capsule_rejects_missing_state(repo_root: Path, scratch_repo: dict, tmp_path: Path):
    proc = _capsule(
        repo_root,
        "--state",
        str(tmp_path / "absent.yaml"),
        "--workdir",
        scratch_repo["dir"],
    )
    assert proc.returncode == 2
    assert "CAPSULE_REJECT" in proc.stderr
    assert proc.stdout == ""


def test_capsule_rejects_malformed_yaml(repo_root: Path, scratch_repo: dict, tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: [valid, yaml: : :\n", encoding="utf-8")
    proc = _capsule(repo_root, "--state", str(bad), "--workdir", scratch_repo["dir"])
    assert proc.returncode == 2
    assert "CAPSULE_REJECT" in proc.stderr


def test_capsule_rejects_schema_invalid(repo_root: Path, scratch_repo: dict, tmp_path: Path):
    bad = tmp_path / "invalid.yaml"
    bad.write_text(yaml.safe_dump({"schema_version": "2.0"}), encoding="utf-8")
    proc = _capsule(repo_root, "--state", str(bad), "--workdir", scratch_repo["dir"])
    assert proc.returncode == 2
    assert "CAPSULE_REJECT" in proc.stderr


def test_capsule_rejects_branch_mismatch(repo_root: Path, scratch_repo: dict, tmp_path: Path):
    state = _write_state(tmp_path / "state.yaml", "other-branch", scratch_repo["head"])
    proc = _capsule(repo_root, "--state", str(state), "--workdir", scratch_repo["dir"])
    assert proc.returncode == 2
    assert "branch mismatch" in proc.stderr


def test_capsule_rejects_source_lock_contradiction(
    repo_root: Path, scratch_repo: dict, tmp_path: Path
):
    state = _write_state(tmp_path / "state.yaml", scratch_repo["branch"], "0" * 40)
    proc = _capsule(repo_root, "--state", str(state), "--workdir", scratch_repo["dir"])
    assert proc.returncode == 2
    assert "SOURCE_LOCK_CONTRADICTION" in proc.stderr


def test_capsule_rejects_broken_validation_ancestry(
    repo_root: Path, scratch_repo: dict, tmp_path: Path
):
    state = _write_state(
        tmp_path / "state.yaml",
        scratch_repo["branch"],
        scratch_repo["head"],
        validated_head="f" * 40,
    )
    proc = _capsule(repo_root, "--state", str(state), "--workdir", scratch_repo["dir"])
    assert proc.returncode == 2
    assert "VALIDATED_" in proc.stderr


def test_capsule_rejects_non_string_gates(repo_root: Path, scratch_repo: dict, tmp_path: Path):
    state = _write_state(
        tmp_path / "state.yaml",
        scratch_repo["branch"],
        scratch_repo["head"],
        hard_gates=[{"NOT_A_STRING": "gate"}],
    )
    proc = _capsule(repo_root, "--state", str(state), "--workdir", scratch_repo["dir"])
    assert proc.returncode == 2
    assert "CAPSULE_REJECT" in proc.stderr


# --- /work command ----------------------------------------------------------


def _command_text(repo_root: Path) -> str:
    return (repo_root / COMMAND_REL).read_text(encoding="utf-8")


def test_work_command_selects_implementer_and_injects_capsule(repo_root: Path):
    text = _command_text(repo_root)
    assert "agent: foundry-implementer" in text
    assert "context_capsule.py" in text
    assert "`!" in text or "!" in text
    assert "Semantic Completion" in text
    assert "full state" in text


def test_work_command_stays_minimal(repo_root: Path):
    text = _command_text(repo_root)
    assert len(text.encode("utf-8")) < 2048, "PROMPT_MINIMALITY: /work stays tiny"
    for forbidden in (
        "TECHNICAL_DECISION_AUTHORITY",
        "doom_loop",
        "QUALITY_NON_REGRESSION",
        "audit_base_sha: 90f95",
        "x-opencode-session",
    ):
        assert forbidden not in text, f"/work must not embed {forbidden!r}"


# --- config: tool_output / compaction / permissions -------------------------


def _config(repo_root: Path) -> dict:
    return json.loads((repo_root / "opencode.json").read_text(encoding="utf-8"))


def test_tool_output_conservative_defaults(repo_root: Path):
    tool_output = _config(repo_root).get("tool_output", {})
    assert tool_output.get("max_lines") == 2000, "pinned CLI default, kept (C)"
    assert tool_output.get("max_bytes") == 51200, "pinned CLI default, kept (C)"
    assert tool_output["max_lines"] > 0 and tool_output["max_bytes"] > 0


def test_compaction_prune_stays_default(repo_root: Path):
    compaction = _config(repo_root).get("compaction", {})
    assert compaction.get("prune", False) is False, (
        "D: prune enabled only with exact-pin proof; default false is the safe lock"
    )
    for key in ("reserved", "tail_turns", "preserve_recent_tokens"):
        assert key not in compaction, f"no aggressive {key} tuning without evidence"


def test_safety_permissions_intact(repo_root: Path):
    permission = _config(repo_root)["permission"]
    assert permission["bash"]["*"] == "ask"
    assert permission["bash"]["git push*"] == "deny"
    assert permission["doom_loop"] == "deny"
    assert permission["edit"]["*.env"] == "deny"


def test_model_provider_instructions_intact(repo_root: Path):
    config = _config(repo_root)
    assert config["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert config["enabled_providers"] == ["opencode-go"]
    assert config["default_agent"] == "foundry-implementer"
    assert "docs/foundry-execution/ROUTING_AND_EFFORT.md" in config["instructions"]


# --- instruction-dedup non-regression ---------------------------------------


def test_policy_layers_kept(repo_root: Path):
    agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    assert "Rules Core" in agents
    routing = (repo_root / "docs/foundry-execution/ROUTING_AND_EFFORT.md").read_text(
        encoding="utf-8"
    )
    assert "muse-spark-1.3-contributor" in routing
    implementer = (repo_root / ".opencode/agents/foundry-implementer.md").read_text(
        encoding="utf-8"
    )
    assert "Do not push" in implementer
    assert "saved full output" in implementer, (
        "C: agent must prefer reading saved full output over rerunning commands"
    )


# --- launcher bundle passthrough --------------------------------------------


def test_launcher_bundle_passes_tool_output(repo_root: Path):
    sys.path.insert(0, str(repo_root / "tools" / "foundry"))
    try:
        import launcher as launcher_mod
    finally:
        sys.path.remove(str(repo_root / "tools" / "foundry"))
    bundle = launcher_mod.build_content_bundle(str(repo_root), [])
    assert bundle["tool_output"] == {"max_lines": 2000, "max_bytes": 51200}
    assert bundle["model"] == "opencode-go/muse-spark-1.3-contributor"


def test_launcher_bundle_rejects_malformed_tool_output(repo_root: Path, tmp_path: Path):
    sys.path.insert(0, str(repo_root / "tools" / "foundry"))
    try:
        import launcher as launcher_mod
    finally:
        sys.path.remove(str(repo_root / "tools" / "foundry"))
    config = {
        "model": "opencode-go/muse-spark-1.3-contributor",
        "share": "disabled",
        "enabled_providers": ["opencode-go"],
        "provider": {
            "opencode-go": {
                "models": {
                    "muse-spark-1.3-contributor": {
                        "variants": {
                            "none": {"disabled": True},
                            "off": {"disabled": True},
                            "minimal": {"disabled": True},
                            "low": {"disabled": True},
                            "medium": {"disabled": True},
                            "high": {},
                            "xhigh": {},
                        }
                    }
                }
            }
        },
        "permission": {},
        "tool_output": {"max_lines": -5, "max_bytes": 51200},
    }
    (tmp_path / "opencode.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError):
        launcher_mod.build_content_bundle(str(tmp_path), [])

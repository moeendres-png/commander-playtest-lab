"""Tests for the Foundry deterministic helpers (tools/foundry/).

Covers: source-lock success, source mismatch failure, dirty-tree handling,
clustering identity preservation, no fabricated evidence, UNKNOWN
preservation, artifact hashing, state schema validation, and state round-trip
for continuation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools" / "foundry"

sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import (  # noqa: E402
    cluster_failures,
    evidence,
    metrics,
    permission_battery,
    worktree_inventory,
)
from foundry import source_lock as lock_mod  # noqa: E402
from foundry import state as state_mod  # noqa: E402


def _git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(["init", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    _git(
        [
            "config",
            "remote.origin.url",
            "https://github.com/moeendres-png/commander-playtest-lab.git",
        ],
        tmp_path,
    )
    (tmp_path / "file.txt").write_text("hello\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-m", "init"], tmp_path)
    return tmp_path


def test_source_lock_success(repo: Path) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    reasons = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert reasons == []


def test_source_lock_branch_mismatch_fails(repo: Path) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    reasons = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="other-branch",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert any("branch mismatch" in r for r in reasons)


def test_source_lock_repo_mismatch_fails(repo: Path) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    reasons = lock_mod.verify(
        repo="someone-else/other-repo",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert any("repository mismatch" in r or "WRONG_LOCAL_REPOSITORY" in r for r in reasons)


def test_source_lock_wrong_base_fails(repo: Path) -> None:
    reasons = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="main",
        audit_base_sha="0" * 40,
        workdir=str(repo),
    )
    assert any("audit base" in r for r in reasons)


def test_source_lock_dirty_tree_fails_closed(repo: Path) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    (repo / "file.txt").write_text("modified\n", encoding="utf-8")
    reasons = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert any("dirty worktree" in r for r in reasons)
    allowed = lock_mod.verify(
        repo="commander-playtest-lab",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
        allow_dirty=True,
    )
    assert allowed == []


def test_cluster_preserves_record_identity(tmp_path: Path) -> None:
    records = [
        {
            "id": "R1",
            "message": "boom at /a/b.py:12 commit abc1234",
            "evidence": "log1",
            "verdict": "FAIL",
        },
        {
            "id": "R2",
            "message": "boom at /x/y.py:99 commit def5678",
            "evidence": "log2",
            "verdict": "FAIL",
        },
        {"id": "R3", "message": "totally different harness timeout", "evidence": "log3"},
    ]
    clusters = cluster_failures.cluster(records)
    assert len(clusters) == 2
    big = next(c for c in clusters if c["count"] == 2)
    assert {m["id"] for m in big["members"]} == {"R1", "R2"}
    assert all(m["evidence"] in ("log1", "log2") for m in big["members"])


def test_evidence_report_never_fabricates() -> None:
    skeleton = evidence.handoff_skeleton("WS-X", {"sha": "abc"})
    assert skeleton["exact_next_action"] == "UNKNOWN"
    assert skeleton["tests_evidence"] == []
    skeleton2 = evidence.handoff_skeleton(
        "WS-X", {"sha": "abc"}, [{"name": "t", "verdict": "BOGUS"}]
    )
    assert skeleton2["tests_evidence"][0]["verdict"] == "UNKNOWN"


def test_artifact_index_hashes(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("deterministic\n", encoding="utf-8")
    manifest = evidence.artifact_index([str(tmp_path)], run="RUN1", source_sha="S" * 40)
    assert len(manifest["artifacts"]) == 1
    entry = manifest["artifacts"][0]
    assert entry["name"] == "out.txt"
    assert entry["size"] == target.stat().st_size
    assert entry["run"] == "RUN1"
    import hashlib

    assert entry["sha256"] == hashlib.sha256(b"deterministic\n").hexdigest()


def _valid_state() -> dict:
    sha = "a" * 40
    return {
        "schema_version": "2.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "worktree": "/tmp/wt",
        "branch": "project/x",
        "audit_base_sha": sha,
        "audit_base_tree": sha,
        "state_written_against_head": sha,
        "validated_head": None,
        "objective": "do the thing",
        "in_scope": ["a"],
        "out_of_scope": ["b"],
        "ownership": "tester",
        "status": "ACTIVE",
        "exact_next_action": "next",
    }


def _legacy_v1_state() -> dict:
    sha = "a" * 40
    return {
        "schema_version": "1.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "worktree": "/tmp/wt",
        "branch": "project/x",
        "audit_base_sha": sha,
        "audit_base_tree": sha,
        "current_head": sha,
        "objective": "do the thing",
        "in_scope": ["a"],
        "out_of_scope": ["b"],
        "ownership": "tester",
        "status": "ACTIVE",
        "exact_next_action": "next",
    }


def test_state_schema_v1_remains_parseable_and_migrates() -> None:
    legacy = _legacy_v1_state()
    assert state_mod.validate(legacy) == []
    migrated = state_mod.migrate(legacy)
    assert migrated["schema_version"] == "2.0"
    assert migrated["state_written_against_head"] == "a" * 40
    assert migrated["validated_head"] is None
    assert "current_head" not in migrated
    assert state_mod.validate(migrated) == []


def test_state_schema_accepts_valid() -> None:
    assert state_mod.validate(_valid_state()) == []


def test_state_schema_rejects_bad_status_and_sha() -> None:
    bad = _valid_state()
    bad["status"] = "DONE"
    bad["state_written_against_head"] = "xyz"
    errors = state_mod.validate(bad)
    assert any("status" in e for e in errors)
    assert any("state_written_against_head" in e for e in errors)


def test_state_schema_rejects_missing_and_bad_class() -> None:
    bad = _valid_state()
    del bad["objective"]
    bad["failure_class"] = "MAYBE_ENGINE"
    errors = state_mod.validate(bad)
    assert any("objective" in e for e in errors)
    assert any("failure_class" in e for e in errors)


def test_state_round_trip_for_continuation(tmp_path: Path) -> None:
    path = tmp_path / "WORKSTREAM_STATE.yaml"
    path.write_text(yaml.safe_dump(_valid_state()), encoding="utf-8")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert state_mod.validate(data) == []
    assert data["exact_next_action"] == "next"


def test_metrics_record_appends_jsonl_without_invention(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    entry = metrics.record(str(metrics_path), task_id="T1", reasoning_effort="high", completed=True)
    assert "token_usage" not in entry
    assert "tool_calls" not in entry
    lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["task_id"] == "T1"


def test_repo_state_file_validates() -> None:
    state_path = REPO_ROOT / ".foundry" / "WORKSTREAM_STATE.yaml"
    data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    assert state_mod.validate(data) == []


def test_opencode_config_schema_conformance() -> None:
    config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    assert config["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert config["share"] == "disabled"
    variants = config["provider"]["opencode-go"]["models"]["muse-spark-1.3-contributor"]["variants"]
    for effort in ("none", "off", "minimal", "low", "medium"):
        assert variants[effort] == {"disabled": True}
    assert set(variants) == {"none", "off", "minimal", "low", "medium", "high", "xhigh"}
    assert "permissions" not in config
    assert isinstance(config["permission"], dict)


def _agent_frontmatter(name: str) -> dict:
    text = (REPO_ROOT / ".opencode" / "agents" / name).read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---")[1])


def test_high_default_retained() -> None:
    config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    provider_model = config["provider"]["opencode-go"]["models"]["muse-spark-1.3-contributor"]
    assert provider_model["options"] == {"reasoningEffort": "high"}
    assert config["agent"]["build"] == {"variant": "high"}
    implementer = _agent_frontmatter("foundry-implementer.md")
    assert implementer["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert implementer["variant"] == "high"


def test_adjudicator_exists_and_configured() -> None:
    adjudicator = _agent_frontmatter("foundry-adjudicator.md")
    assert adjudicator["mode"] == "subagent"
    assert adjudicator["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert adjudicator["variant"] == "xhigh"
    assert adjudicator["permission"]["edit"] == "deny"
    bash = adjudicator["permission"]["bash"]
    assert bash["*"] == "ask"
    for allowed in ("git diff*", "git log*", "mypy*"):
        assert bash[allowed] == "allow"
    for gated in ("pytest*", "python*", "python3*", "ruff*", "gh api*"):
        assert bash[gated] == "ask"
    for denied in ("git push*", "git rebase*", "rm -rf*", "gh auth token*"):
        assert bash[denied] == "deny"
    config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    assert config["permission"]["task"]["foundry-adjudicator"] == "allow"


def test_adjudicator_narrower_than_implementer() -> None:
    adjudicator = _agent_frontmatter("foundry-adjudicator.md")
    implementer = _agent_frontmatter("foundry-implementer.md")
    assert "permission" not in implementer
    assert adjudicator["permission"]["edit"] == "deny"
    assert isinstance(adjudicator["permission"]["bash"], dict)


def test_state_accepts_adjudication_extension_fields() -> None:
    state = _valid_state()
    state.update(
        {
            "technical_decision_authority": "AUTONOMOUS_WITHIN_CONTRACT",
            "current_reasoning_tier": "xhigh",
            "hypotheses_rejected": ["harness-only cause"],
            "technical_decisions": [{"decision": "root cause is adapter", "evidence": "log1"}],
            "authority_gates": [],
            "first_failing_boundary": "adapter translation",
            "root_cause_class": "EVIDENCE_PIPELINE_DEFECT",
            "next_action": "repair adapter",
        }
    )
    assert state_mod.validate(state) == []


def test_state_rejects_bad_tier_and_root_cause() -> None:
    state = _valid_state()
    state["current_reasoning_tier"] = "medium"
    state["root_cause_class"] = "MAYBE_ENGINE"
    errors = state_mod.validate(state)
    assert any("current_reasoning_tier" in e for e in errors)
    assert any("root_cause_class" in e for e in errors)


def test_agents_md_encodes_technical_autonomy() -> None:
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    flat = " ".join(text.lower().split())
    assert "technical_decision_authority = autonomous_within_contract" in flat
    assert "do not stop or ask the coordinator for routine technical decisions" in flat
    assert "muse xhigh" in flat
    assert "authority_gate" in flat


def test_reviewer_remains_high_and_read_only() -> None:
    reviewer = _agent_frontmatter("foundry-reviewer.md")
    assert reviewer["mode"] == "subagent"
    assert reviewer["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert reviewer["variant"] == "high"
    assert reviewer["permission"]["edit"] == "deny"


def _root_permission() -> dict:
    return json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))["permission"]


def test_implementer_has_no_broad_agent_override() -> None:
    implementer = _agent_frontmatter("foundry-implementer.md")
    permission = implementer.get("permission", {})
    assert permission.get("edit") != "allow"
    bash = permission.get("bash", {})
    if isinstance(bash, dict):
        assert bash.get("*") != "allow"
    else:
        assert bash != "allow"


def test_env_deny_rules_win_by_order() -> None:
    permission = _root_permission()
    for tool in ("read", "glob", "grep", "list", "edit"):
        rules = permission[tool]
        assert isinstance(rules, dict)
        keys = list(rules)
        assert keys[0] == "*"
        assert rules["*"] == "allow"
        for pattern in ("*.env", "*.env.*", "**/*.env", "**/*.env.*"):
            assert rules[pattern] == "deny"
            assert keys.index(pattern) > keys.index("*")
        assert rules["*.env.example"] == "allow"
        assert keys.index("*.env.example") > keys.index("*.env.*")


def test_generic_gh_api_is_not_allow() -> None:
    permission = _root_permission()
    assert permission["bash"]["gh api*"] != "allow"
    adjudicator = _agent_frontmatter("foundry-adjudicator.md")
    assert adjudicator["permission"]["bash"]["gh api*"] != "allow"


def test_adjudicator_has_no_silent_write_interpreter() -> None:
    bash = _agent_frontmatter("foundry-adjudicator.md")["permission"]["bash"]
    for pattern in ("python*", "python3*", "pytest*", "ruff*"):
        assert bash.get(pattern) != "allow"
    assert bash["git add*"] == "deny"
    assert bash["git commit*"] == "deny"


def test_reviewer_bash_default_deny() -> None:
    bash = _agent_frontmatter("foundry-reviewer.md")["permission"]["bash"]
    assert bash["*"] == "deny"
    assert _agent_frontmatter("foundry-reviewer.md")["permission"]["task"] == "deny"


def test_provider_lock_and_sharing() -> None:
    config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    assert config["enabled_providers"] == ["opencode-go"]
    assert config["share"] == "disabled"
    assert config["default_agent"] == "foundry-implementer"


def test_battery_last_match_wins() -> None:
    rules = [
        {"permission": "bash", "pattern": "*", "action": "ask"},
        {"permission": "bash", "pattern": "git status*", "action": "allow"},
        {"permission": "bash", "pattern": "git push*", "action": "ask"},
    ]
    assert permission_battery.evaluate_rule(rules, "bash", "git status") == (
        "ENFORCED_ALLOW",
        "git status*",
    )
    assert permission_battery.evaluate_rule(rules, "bash", "git push origin x") == (
        "ASK_GATED",
        "git push*",
    )
    assert permission_battery.evaluate_rule(rules, "bash", "rm -rf /tmp/y") == ("ASK_GATED", "*")
    assert permission_battery.evaluate_rule(rules, "bash", "git status")[0] == "ENFORCED_ALLOW"


def test_battery_env_deny_beats_allow_all() -> None:
    rules = [
        {"permission": "read", "pattern": "*", "action": "allow"},
        {"permission": "read", "pattern": "*.env", "action": "deny"},
        {"permission": "read", "pattern": "**/*.env", "action": "deny"},
    ]
    assert permission_battery.evaluate_rule(rules, "read", "/proj/.env") == ("DENIED", "**/*.env")
    assert permission_battery.evaluate_rule(rules, "read", "/proj/src/a.py") == (
        "ENFORCED_ALLOW",
        "*",
    )


def test_battery_unknown_without_match() -> None:
    assert permission_battery.evaluate_rule([], "bash", "anything") == (
        "UNKNOWN",
        "no matching rule",
    )


def test_battery_full_probe_set_runs() -> None:
    rules = [{"permission": "bash", "pattern": "*", "action": "ask"}]
    resolved = {
        "foundry-implementer": rules,
        "foundry-adjudicator": rules,
        "foundry-reviewer": rules,
    }
    rows = permission_battery.run_battery(resolved)
    assert len(rows) == len(permission_battery.PROBES)
    assert {r["verdict"] for r in rows} <= {
        "ENFORCED_ALLOW",
        "ASK_GATED",
        "DENIED",
        "INSTRUCTION_ONLY",
        "BYPASSABLE",
        "UNKNOWN",
    }


def test_inventory_marks_clean_true_and_strips_refs(repo: Path) -> None:
    entries = worktree_inventory.inventory(str(repo))
    assert len(entries) == 1
    entry = entries[0]
    assert entry["clean"] is True
    assert entry["branch"] == "main"
    assert entry["head"] == _git(["rev-parse", "HEAD"], repo)


def test_inventory_marks_dirty_false(repo: Path) -> None:
    (repo / "file.txt").write_text("dirty\n", encoding="utf-8")
    entries = worktree_inventory.inventory(str(repo))
    assert entries[0]["clean"] is False


def test_source_lock_full_slug_wrong_owner_is_wrong_local_repository(
    repo: Path,
) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    _git(
        [
            "config",
            "remote.origin.url",
            "https://github.com/someone-else/commander-playtest-lab.git",
        ],
        repo,
    )
    reasons = lock_mod.verify(
        repo="moeendres-png/commander-playtest-lab",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert any("WRONG_LOCAL_REPOSITORY" in r for r in reasons)


def test_source_lock_full_slug_canonical_passes_identity(repo: Path) -> None:
    head = _git(["rev-parse", "HEAD"], repo)
    reasons = lock_mod.verify(
        repo="moeendres-png/commander-playtest-lab",
        branch="main",
        audit_base_sha=head,
        workdir=str(repo),
    )
    assert reasons == []


def test_is_canonical_remote_requires_full_slug() -> None:
    assert lock_mod.is_canonical_remote(
        "https://github.com/moeendres-png/commander-playtest-lab.git"
    )
    assert not lock_mod.is_canonical_remote(
        "https://github.com/someone-else/commander-playtest-lab.git"
    )
    assert not lock_mod.is_canonical_remote("https://github.com/moeendres-png/other.git")


def test_worktree_inventory_duplicate_writer_detected() -> None:
    entries = [
        {"path": "/tmp/wt-a", "branch": "project/x", "head": "a" * 40},
        {"path": "/tmp/wt-b", "branch": "project/x", "head": "a" * 40},
        {"path": "/tmp/wt-c", "branch": "project/y", "head": "b" * 40},
    ]
    conflicts = worktree_inventory.find_duplicate_writers(entries)  # type: ignore[arg-type]
    assert len(conflicts) == 1
    assert "project/x" in conflicts[0]
    assert worktree_inventory.find_duplicate_writers(entries[:1]) == []


def test_state_head_mismatch_warns(repo: Path, tmp_path: Path) -> None:
    import yaml as _yaml

    head = _git(["rev-parse", "HEAD"], repo)
    state = _valid_state()
    state["state_written_against_head"] = head
    state_path = tmp_path / "STATE.yaml"
    state_path.write_text(_yaml.safe_dump(state), encoding="utf-8")
    assert state_mod.check_head_mismatch(str(state_path), str(repo)) == []
    bad = dict(state)
    bad["state_written_against_head"] = "0" * 40
    state_path.write_text(_yaml.safe_dump(bad), encoding="utf-8")
    warnings = state_mod.check_head_mismatch(str(state_path), str(repo))
    assert any("HEAD_MISMATCH" in w for w in warnings)


def test_battery_cli_wildcard_exact_semantics() -> None:
    assert permission_battery.matches("gh api*", "gh api repos/x/y")
    assert permission_battery.matches("gh api*", "gh api -X PATCH repos/x/y")
    assert not permission_battery.matches("gh api*", "gh run view 1")
    assert permission_battery.matches("*.env", "/proj/.env")
    assert permission_battery.matches("*.env.*", "/proj/.env.local")
    assert permission_battery.matches("git push*", "git push origin test")
    assert not permission_battery.matches("git push*", "git status")


def test_bootstrap_skill_has_identity_gate() -> None:
    text = (REPO_ROOT / ".opencode" / "skills" / "workstream-bootstrap" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "moeendres-png/commander-playtest-lab",
        "WRONG_LOCAL_REPOSITORY",
        "REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE",
        "tools/foundry/source_lock.py",
        "tools/foundry/worktree_inventory.py",
        "no duplicate writer",
        "Do not use one governance checkout to write across independent worktrees",
    ):
        assert required.lower() in text.lower()


def test_governance_propagation_contract_exists() -> None:
    text = (REPO_ROOT / "docs" / "foundry-execution" / "GOVERNANCE_PROPAGATION.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "RETAINED_EVIDENCE_IMPACT = NO_SEMANTIC_IMPACT",
        "only expected governance/tooling paths",
        "do not rerun qualification for reassurance",
        "Do not use one governance checkout to write across independent worktrees",
    ):
        assert required.lower() in text.lower()

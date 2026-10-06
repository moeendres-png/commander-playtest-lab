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


def test_repo_root_state_absent_schema_kept() -> None:
    """ROOT_STATE_SEMANTICS: no implicit active repository-root state file."""
    assert not (REPO_ROOT / ".foundry" / "WORKSTREAM_STATE.yaml").exists()
    assert (REPO_ROOT / ".foundry" / "WORKSTREAM_STATE.schema.json").is_file()


def test_opencode_config_schema_conformance() -> None:
    """Exactly two authorized executors, each pinned to one native variant.

    Operator authority (2026-09-29): only DeepSeek MAX and Space Bunny MAX are
    reachable. This pins the shape and the pinning, not just the presence of a
    model field, so a retired effort level cannot quietly reopen.
    """
    config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    assert config["model"] == "opencode-go/deepseek-v4.1-flash"
    assert config["small_model"] == "opencode-go/deepseek-v4.1-flash"
    assert config["share"] == "disabled"
    assert config["enabled_providers"] == ["opencode-go"]
    provider = config["provider"]["opencode-go"]
    # No silent fallback: primary first, documented secondary still selectable.
    assert provider["whitelist"] == ["deepseek-v4.1-flash", "space-bunny-free"]
    authorized = {
        "deepseek-v4.1-flash": ("max", {"reasoningEffort": "max"}),
        "space-bunny-free": ("max", {"reasoningEffort": "max"}),
    }
    assert set(provider["models"]) == set(authorized)
    for short, (variant, options) in authorized.items():
        entry = provider["models"][short]
        assert entry["options"] == options, short
        enabled = sorted(n for n, s in entry["variants"].items() if s != {"disabled": True})
        assert enabled == [variant], f"{short}: {enabled}"
        for retired in ("none", "off", "minimal", "low", "medium", "high", "xhigh"):
            assert entry["variants"][retired] == {"disabled": True}, f"{short}:{retired}"
    # DeepSeek is the primary executor, so the build agent defaults to its level.
    assert config["agent"]["build"] == {"variant": "max"}
    assert "permissions" not in config
    assert isinstance(config["permission"], dict)


def test_only_authorized_executors_present_in_canonical_config() -> None:
    """The canonical config exposes exactly the two currently authorized models."""
    config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    provider = config["provider"]["opencode-go"]
    assert provider["whitelist"] == ["deepseek-v4.1-flash", "space-bunny-free"]
    assert set(provider["models"]) == {"deepseek-v4.1-flash", "space-bunny-free"}


def _agent_frontmatter(name: str) -> dict:
    text = (REPO_ROOT / ".opencode" / "agents" / name).read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---")[1])


def test_high_default_retained() -> None:
    """The default agent surface runs at an authorized native level only.

    Retained intent, renamed subject: with only DeepSeek MAX and Space Bunny MAX
    permitted, every other level is retired and must not appear on any reachable
    agent definition. No agent may sit on a retired level.
    """
    config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    models = config["provider"]["opencode-go"]["models"]
    assert models["deepseek-v4.1-flash"]["options"] == {"reasoningEffort": "max"}
    assert models["space-bunny-free"]["options"] == {"reasoningEffort": "max"}
    # The on-disk agent snapshot is the DeepSeek primary; the launcher pins the
    # explicitly selected profile inline for every run.
    expected = {
        "foundry-implementer.md": ("opencode-go/deepseek-v4.1-flash", "max"),
        "foundry-adjudicator.md": ("opencode-go/deepseek-v4.1-flash", "max"),
        "foundry-reviewer.md": ("opencode-go/deepseek-v4.1-flash", "max"),
    }
    for name, (model, variant) in expected.items():
        front = _agent_frontmatter(name)
        assert front["model"] == model, name
        assert front["variant"] == variant, name


def test_adjudicator_exists_and_configured() -> None:
    adjudicator = _agent_frontmatter("foundry-adjudicator.md")
    assert adjudicator["mode"] == "subagent"
    assert adjudicator["model"] == "opencode-go/deepseek-v4.1-flash"
    assert adjudicator["variant"] == "max"
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
    assert "deepseek max" in flat
    assert "space bunny max" in flat
    assert "no other opencode execution profile is authorized" in flat
    assert "autonomous tool use" in flat
    assert "authority_gate" in flat
    assert "claude_opus_coordinator_authority = delegated_by_owner" in flat
    assert "owner-only decisions" in flat


def test_reviewer_remains_high_and_read_only() -> None:
    """Reviewer runs at an authorized level and stays structurally read-only."""
    reviewer = _agent_frontmatter("foundry-reviewer.md")
    assert reviewer["mode"] == "subagent"
    assert reviewer["model"] == "opencode-go/deepseek-v4.1-flash"
    assert reviewer["variant"] == "max"
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
    """GitHub API access is authorized for the executor, not for adjudication.

    The delegated integration authority grants normal GitHub mutations to the
    implementing executor. It deliberately does NOT extend to the read-only
    adjudication subagents: an adjudicator that can mutate the repository it is
    judging is not an independent check. This keeps that real invariant alive
    after the root policy widened.
    """
    permission = _root_permission()
    assert permission["bash"].get("gh api*", "allow") == "allow"
    for pattern in (
        "gh api -X POST*",
        "gh api -X PUT*",
        "gh api -X PATCH*",
        "gh api -X DELETE*",
    ):
        # Removed from the deny list rather than re-pinned: the default is now
        # allow, so an explicit allow is what documents the grant.
        assert permission["bash"].get(pattern, "allow") == "allow", pattern
    adjudicator = _agent_frontmatter("foundry-adjudicator.md")
    assert adjudicator["permission"]["bash"]["gh api*"] != "allow"
    assert adjudicator["permission"]["bash"]["git add*"] == "deny"
    assert adjudicator["permission"]["bash"]["git commit*"] == "deny"
    reviewer = _agent_frontmatter("foundry-reviewer.md")
    assert reviewer["permission"]["bash"]["*"] == "deny"
    assert reviewer["permission"]["edit"] == "deny"
    assert reviewer["permission"]["task"] == "deny"


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


def _live_bash_rules() -> list[dict]:
    perm = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))["permission"]
    return [
        {"permission": "bash", "pattern": pattern, "action": action}
        for pattern, action in perm["bash"].items()
    ]


def test_delegated_git_allow_with_specific_denies() -> None:
    """Live opencode.json resolution: owned-branch Git allowed, destructive denied."""
    rules = _live_bash_rules()
    for cmd in (
        "git fetch origin",
        "git push origin foundry/feature-20260927",
        "git push",
        "git merge origin/main",
        "git pull --ff-only",
        "git cherry-pick abc123",
        "git checkout -b foundry/feature-20260927",
        "git switch -c foundry/feature-20260927",
        "git worktree add /tmp/wt -b foundry/feature-20260927",
        "gh pr create --title x",
        "gh pr merge 266",
    ):
        verdict, matched = permission_battery.evaluate_rule(rules, "bash", cmd)
        assert verdict == "ENFORCED_ALLOW", (cmd, matched)
    for cmd in (
        "git push --force origin foundry/feature-20260927",
        "git push origin foundry/feature-20260927 --force",
        "git push -f origin foundry/feature-20260927",
        "git push --force-with-lease origin foundry/feature-20260927",
        "git push origin foundry/feature-20260927 --delete",
        "git push origin main",
        "git push origin master",
        "git push upstream main",
        "git checkout -B foundry/feature-20260927",
        "git switch -C foundry/feature-20260927",
        "git rebase origin/main",
        "git reset --hard HEAD",
        "git clean -fd",
        "git branch -D foundry/feature-20260927",
        "git worktree remove /tmp/wt",
        "git worktree remove --force /tmp/wt",
    ):
        verdict, matched = permission_battery.evaluate_rule(rules, "bash", cmd)
        assert verdict == "DENIED", (cmd, matched)


def test_pr_merge_vs_raw_main_push_distinction() -> None:
    """Guarded PR merge path is allowed; raw main push is denied."""
    rules = _live_bash_rules()
    verdict, _ = permission_battery.evaluate_rule(rules, "bash", "gh pr merge 266")
    assert verdict == "ENFORCED_ALLOW"
    verdict, matched = permission_battery.evaluate_rule(rules, "bash", "git push origin main")
    assert verdict == "DENIED", matched


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


def test_safe_auto_deny_set_pinned() -> None:
    """Destructive shapes must stay deny in opencode.json; owned-branch Git is allow.

    Delegated integration authority (AGENTS.md): normal push/merge/branch/worktree
    creation on the owned feature branch is ENFORCED_ALLOW, while force, main/master
    and destructive shapes stay DENIED via later last-match-wins rules.
    Guards against silent ask-downgrades. Live resolution is proven separately
    by the adversarial battery against `opencode debug agent` output.
    """
    config = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    bash = config["permission"]["bash"]
    for pattern in (
        "git push --force*",
        "git push * --force*",
        "git push -f*",
        "git push * -f *",
        "git push * -f",
        "git push --force-with-lease*",
        "git push * --force-with-lease*",
        "git push --delete*",
        "git push * --delete*",
        "git push * :*",
        "git push origin main*",
        "git push origin master*",
        "git push upstream main*",
        "git push upstream master*",
        "git rebase*",
        "git reset --hard*",
        "git clean*",
        "git branch -D*",
        "git branch -d*",
        "git worktree remove*",
        "git worktree move*",
        "git worktree remove --force*",
        "git checkout main",
        "git checkout master",
        "git checkout -B*",
        "git switch main",
        "git switch master",
        "git switch -C*",
        "git update-ref*",
        "git symbolic-ref*",
        "git filter-branch*",
        "git filter-repo*",
        "git tag -d*",
        "git tag -f*",
        "git stash drop*",
        "git stash clear*",
        "sudo*",
        "su *",
        "env",
        "env *",
        "printenv*",
        "rm -rf*",
        "rm -fr*",
        "gh auth*",
        "gh repo create*",
        "gh repo delete*",
        "gh repo fork*",
        "*| sh",
        "*| sh *",
        "*|sh",
        "*|sh *",
        "*| bash",
        "*| bash *",
        "*|bash",
        "*|bash *",
    ):
        assert bash.get(pattern) == "deny", pattern
    # Delegated owned-branch Git authority must stay allow.
    for pattern in (
        "git push*",
        "git merge*",
        "git pull --ff-only*",
        "git cherry-pick*",
        "git checkout -b*",
        "git switch -c*",
        "git worktree add*",
        "gh pr create*",
        "gh pr merge*",
    ):
        assert bash.get(pattern) == "allow", pattern
    # Routine engineering must still proceed unattended. These are reached
    # through the authorized default rather than an explicit allowlist, so an
    # explicit ask/deny here would silently re-create a blocker.
    for pattern in (
        "git status*",
        "git diff*",
        "git log*",
        "pytest*",
        "python*",
        "ruff*",
        "git add*",
        "git commit*",
        "git -C*",
        "mvn*",
        "gradle*",
    ):
        assert bash.get(pattern, "allow") == "allow", pattern
    # The default is authorized, but only because the deny list above is intact.
    # Without this, a later `*` change would silently erase every boundary.
    assert bash["*"] == "allow"
    # Secret-bearing files stay closed to every read-shaped tool.
    for tool in ("read", "glob", "grep", "list", "edit"):
        rules = config["permission"][tool]
        for pattern in ("*.env", "*.env.*", "**/*.env", "**/*.env.*"):
            assert rules.get(pattern) == "deny", f"{tool}:{pattern}"
        assert rules.get("*.env.example") == "allow", tool
    assert config["share"] == "disabled"
    assert config["permission"]["doom_loop"] == "deny"
    assert config["permission"]["task"]["*"] == "ask"
    # The whole Commander-Lab workspace tree is in campaign scope. Ownership is
    # enforced by tools/foundry/workspace_access.py binding repository identity
    # plus exact HEAD/tree under a multi-lock, which is stronger evidence than
    # the folder-name denies it replaces, so those denies are gone by design.
    ext = config["permission"]["external_directory"]
    assert ext["*"] == "allow"
    assert ext["/home/moeen/code/*"] == "allow"
    assert ext["/tmp/*"] == "allow"
    for folder in (
        "/home/moeen/code/ws50-forge-decision-sequence-slice*",
        "/home/moeen/code/q6-capability-curation-20260910*",
    ):
        assert folder not in ext, folder


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


def _ownership_state(ownership: str) -> dict:
    state = _valid_state()
    state["ownership"] = ownership
    return state


def test_inventory_reports_mapped_explicit_state_ownership(repo: Path, tmp_path: Path) -> None:
    """Explicit map authority: dedicated state location yields its ownership."""
    custom = tmp_path / "dedicated" / "WS-MAPPED.yaml"
    custom.parent.mkdir(parents=True)
    custom.write_text(yaml.safe_dump(_ownership_state("WS-MAPPED")), encoding="utf-8")
    entries = worktree_inventory.inventory(str(repo), {str(repo): str(custom)})
    assert len(entries) == 1
    assert entries[0]["ownership"] == "WS-MAPPED"


def test_inventory_unknown_without_ownership_authority(repo: Path) -> None:
    """No map and no legacy root file: ownership is UNKNOWN, never fabricated."""
    assert not (repo / ".foundry" / "WORKSTREAM_STATE.yaml").exists()
    entries = worktree_inventory.inventory(str(repo))
    assert entries[0]["ownership"] == "UNKNOWN"
    entries = worktree_inventory.inventory(str(repo), {})
    assert entries[0]["ownership"] == "UNKNOWN"


def test_inventory_missing_mapped_file_stays_unknown(repo: Path, tmp_path: Path) -> None:
    """A mapped path that cannot be read degrades to UNKNOWN (never invented)."""
    entries = worktree_inventory.inventory(
        str(repo), {str(repo): str(tmp_path / "absent" / "STATE.yaml")}
    )
    assert entries[0]["ownership"] == "UNKNOWN"


def test_inventory_ignores_conventional_root_file(repo: Path, tmp_path: Path) -> None:
    """ROOT_STATE_SEMANTICS: a conventional root file alone grants no authority."""
    legacy = repo / ".foundry" / "WORKSTREAM_STATE.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(yaml.safe_dump(_ownership_state("STALE-WS")), encoding="utf-8")
    assert worktree_inventory.inventory(str(repo))[0]["ownership"] == "UNKNOWN"
    assert (
        worktree_inventory.inventory(
            str(repo), {str(tmp_path / "elsewhere"): str(tmp_path / "nope.yaml")}
        )[0]["ownership"]
        == "UNKNOWN"
    )


def _inventory_cli(args: list[str]) -> tuple[int, dict, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = worktree_inventory.main(args)
    listing = out.getvalue()
    payload = json.loads(listing) if listing.strip() else {}
    return rc, payload, err.getvalue()


def test_inventory_cli_reports_mapped_owner(repo: Path, tmp_path: Path) -> None:
    custom = tmp_path / "dedicated" / "WS-CLI.yaml"
    custom.parent.mkdir(parents=True)
    custom.write_text(yaml.safe_dump(_ownership_state("WS-CLI")), encoding="utf-8")
    rc, payload, _ = _inventory_cli(
        ["--workdir", str(repo), "--worktree-state", f"{repo}={custom}"]
    )
    assert rc == 0
    assert payload["worktrees"][0]["ownership"] == "WS-CLI"


def test_inventory_cli_without_map_reports_unknown(repo: Path, tmp_path: Path) -> None:
    rc, payload, _ = _inventory_cli(["--workdir", str(repo)])
    assert rc == 0
    assert payload["worktrees"][0]["ownership"] == "UNKNOWN"


def test_inventory_cli_rejects_malformed_mapping(repo: Path, tmp_path: Path) -> None:
    rc, _, err = _inventory_cli(["--workdir", str(repo), "--worktree-state", "malformed"])
    assert rc == 1
    assert "INVENTORY_FAIL" in err


def test_inventory_cli_rejects_conflicting_mapping(repo: Path, tmp_path: Path) -> None:
    first = tmp_path / "A.yaml"
    second = tmp_path / "B.yaml"
    first.write_text(yaml.safe_dump(_ownership_state("WS-A")), encoding="utf-8")
    second.write_text(yaml.safe_dump(_ownership_state("WS-B")), encoding="utf-8")
    rc, _, err = _inventory_cli(
        [
            "--workdir",
            str(repo),
            "--worktree-state",
            f"{repo}={first}",
            "--worktree-state",
            f"{repo}={second}",
        ]
    )
    assert rc == 1
    assert "conflicting" in err


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


def test_skill_library_conformance() -> None:
    skills = REPO_ROOT / ".opencode" / "skills"
    names = sorted(p.name for p in skills.iterdir() if p.is_dir())
    assert names == [
        "component-change-review",
        "continuation",
        "evidence-seal",
        "failure-classification",
        "lab-ops",
        "rules-authority-escalation",
        "test-impact",
        "workstream-bootstrap",
    ]
    for name in names:
        text = (skills / name / "SKILL.md").read_text(encoding="utf-8")
        front = yaml.safe_load(text.split("---")[1])
        assert front["name"] == name
        assert front["description"].strip()
    escalation = (skills / "rules-authority-escalation" / "SKILL.md").read_text(encoding="utf-8")
    for required in ("AUTHORITY_GATE", "UNKNOWN", "Sol High"):
        assert required in escalation
    assert "second hidden rules engine" not in escalation.lower()


def test_dual_executor_current_authority_is_canonical() -> None:
    authority = REPO_ROOT / "docs" / "CURRENT_EXECUTION_AUTHORITY.md"
    assert authority.is_file()
    flat = " ".join(authority.read_text(encoding="utf-8").lower().split())
    for required in (
        "deepseek v4.1 flash max",
        "opencode-go/deepseek-v4.1-flash",
        "space bunny max",
        "opencode-go/space-bunny-free",
        "no other opencode model/profile is currently authorized",
        "no automatic fallback",
        "production provider",
        "architecture freeze",
    ):
        assert required.lower() in flat


def test_cpl_profile_points_to_current_dual_executor_authority() -> None:
    profile = json.loads((REPO_ROOT / ".foundry" / "repo-profiles" / "cpl.json").read_text())
    canonical = profile["canonical_files"]
    assert "AGENTS.md" in canonical
    assert "CLAUDE.md" in canonical
    assert "docs/CURRENT_EXECUTION_AUTHORITY.md" in canonical
    assert "docs/foundry-execution/EXECUTION_PROVIDER_OVERRIDE.md" in canonical
    assert "docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md" not in canonical
    notes = profile["notes"].lower()
    assert "two-executor" in notes
    assert "space bunny max" in notes
    assert "historical model references are provenance only" in notes


def test_claude_entrypoint_delegates_to_canonical_policy() -> None:
    entrypoint = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    flat = " ".join(entrypoint.lower().split())
    assert "agents.md" in flat
    assert "canonical durable agent policy" in flat
    assert "not an independent policy source" in flat
    assert "claude opus 5.5" in flat
    assert "when the owner delegation applies" in flat
    assert "docs/current_execution_authority.md" in flat
    assert "claude_opus_coordinator_authority = delegated_by_owner" not in flat
    assert "owner-only reservations" in flat


def test_current_routing_is_executor_neutral_and_bunny_preferred() -> None:
    routing = (REPO_ROOT / "docs" / "foundry-execution" / "ROUTING_AND_EFFORT.md").read_text(
        encoding="utf-8"
    )
    flat = " ".join(routing.lower().split())
    assert "default and preferred executor" in flat
    assert "space-bunny" in flat
    assert "native `max`" in flat
    assert "no other opencode executor is selectable" in flat
    assert (
        "neither supported opencode foundry executor nor an available authorized claude campaign "
        "can perform it" in flat
    )
    assert "docs/current_execution_authority.md" in flat
    assert "coordinator tier's decision authority" in flat
    assert "owner-only reservations" in flat

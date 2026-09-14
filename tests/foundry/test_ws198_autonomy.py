"""WS198 Foundry autonomous-workstream orchestration (hermetic).

Covers the 21 required areas: autonomy defaults in implementer context,
Semantic Completion in TUI/headless, non-stop and local-decision directives,
bounded XHIGH, early-success hardening order, bounded continuation, engine
fail-closed, machine-checkable successor planning, Coordinator-gated
execution, no implicit branch/worktree/remote/provider transitions,
resumable rotation, no fabricated telemetry, compact capsule values,
legacy compatibility, WS196 routing, safe-push gates, Go/Zen identity,
TUI/headless parity, and the WS92/WS93 TUI exit-0 false-success regression.

All tests hermetic: throwaway git repos, fake canonical roots, stub OpenCode
binaries. No network, no ambient binary, no paid calls.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import autonomy as autonomy_mod  # noqa: E402
from foundry import launcher as launcher_mod  # noqa: E402
from foundry import state as state_mod  # noqa: E402

CPL_SLUG = "moeendres-png/commander-playtest-lab"


# --------------------------------------------------------------------------
# Fixtures and helpers.
# --------------------------------------------------------------------------

def _git(args: list[str], cwd: Path, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False, env=env
    )
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


def _env() -> dict:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "T",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    return env


def _doc(**over: object) -> dict:
    doc: dict = {
        "schema_version": "2.0",
        "repository": CPL_SLUG,
        "worktree": "/tmp/wt",
        "branch": "project/x",
        "audit_base_sha": "a" * 40,
        "audit_base_tree": "b" * 40,
        "state_written_against_head": "a" * 40,
        "validated_head": None,
        "objective": "x",
        "in_scope": ["implement autonomy checks"],
        "out_of_scope": ["automatic branch creation"],
        "ownership": "tester",
        "status": "ACTIVE",
        "exact_next_action": "implement autonomy checks",
        "remaining_scope": [],
    }
    doc.update(over)
    return doc


def _facts(head: str = "a" * 40) -> dict:
    return {"branch": "project/x", "head": head, "tree": "b" * 40, "dirty_entries": 0}


def _successor_spec(**over: object) -> dict:
    spec: dict = {
        "objective": "follow-up hardening",
        "repository": CPL_SLUG,
        "proposed_branch": "ws199/example",
        "proposed_worktree": "/home/op/wt199",
        "source_lock_basis": "WS198 terminal seal commit (read at planning time)",
        "inputs": ["WS198 seal"],
        "ownership_surface": "WS199",
        "dependencies": [],
        "in_scope": ["telemetry export capture"],
        "out_of_scope": ["provider selection"],
        "hard_gates": ["no scope expansion"],
        "forbidden_shortcuts": ["no silent fallback"],
        "evidence_requirements": ["hermetic tests"],
        "recommended_lane": "high",
        "stop_conditions": ["COMPLETE with readiness"],
        "rationale": "pays down telemetry UNKNOWN",
        "initial_prompt": "Execute the telemetry successor",
        "executability": "DEPENDENCY_BLOCKED",
    }
    spec.update(over)
    return spec


@pytest.fixture()
def canon(tmp_path: Path) -> Path:
    root = tmp_path / "canon"
    (root / ".opencode" / "agents").mkdir(parents=True)
    (root / ".opencode" / "skills").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    (root / ".opencode" / "agents" / "foundry-implementer.md").write_text(
        "---\nvariant: high\n---\n", encoding="utf-8"
    )
    real = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    (root / "opencode.json").write_text(
        json.dumps(
            {
                "model": real["model"],
                "share": real["share"],
                "enabled_providers": real["enabled_providers"],
                "provider": real["provider"],
                "permission": real["permission"],
            }
        ),
        encoding="utf-8",
    )
    tools_dir = root / "tools" / "foundry"
    tools_dir.mkdir(parents=True)
    (tools_dir / "safe_push.py").write_text("# canonical safe-push stub\n", encoding="utf-8")
    return root


@pytest.fixture()
def target(tmp_path: Path) -> dict:
    locks = tmp_path / "locks"
    locks.mkdir()
    wt = tmp_path / "wt"
    wt.mkdir()
    env = _env()
    _git(["init", "-b", "main"], wt, env)
    _git(["config", "remote.origin.url", f"https://github.com/{CPL_SLUG}.git"], wt, env)
    (wt / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    (wt / "code.txt").write_text("x\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "init"], wt, env)
    base = _git(["rev-parse", "HEAD"], wt, env)
    _git(["checkout", "-b", "project/test"], wt, env)
    state = _doc(
        worktree=str(wt),
        branch="project/test",
        audit_base_sha=base,
        state_written_against_head=base,
        ownership="TEST-WS",
    )
    state_path = wt / ".foundry" / "WORKSTREAM_STATE.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    return {"wt": wt, "locks": locks, "env": env, "state": state_path, "base": base}


def _version_stub(tmp_path: Path, exit_code: int = 0) -> Path:
    stub = tmp_path / "fake-opencode-bin"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('1.18.30')\n"
        "    sys.exit(0)\n"
        "record = os.environ.get('STUB_ARGV_FILE')\n"
        "if record:\n"
        "    open(record, 'a').write(' '.join(sys.argv) + chr(10))\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def _cli_shape_stub(tmp_path: Path) -> Path:
    """Mimic pinned-CLI TUI shape: bare positional -> directory error, exit 0."""
    stub = tmp_path / "cli-shape-bin"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "argv = sys.argv[1:]\n"
        "if argv == ['--version']:\n"
        "    print('1.18.30')\n"
        "    sys.exit(0)\n"
        "record = os.environ.get('STUB_ARGV_FILE')\n"
        "if record:\n"
        "    open(record, 'a').write(' '.join(sys.argv) + chr(10))\n"
        "# TUI form has no 'run' subcommand; a bare positional is [project].\n"
        "if argv[:2] == ['--auto', '--prompt'] or (argv[:1] == ['--auto'] and '--prompt' in argv):\n"
        "    sys.exit(7)\n"
        "if len(argv) >= 2 and argv[0] == '--auto' and not argv[1].startswith('-'):\n"
        "    sys.stderr.write(\n"
        "        'Error: Failed to change directory to /home/moeen/' + argv[1] + '\\n'\n"
        "    )\n"
        "    sys.exit(0)\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def _plan(target: dict, canon: Path, **over: object) -> dict:
    kwargs: dict = {
        "profile": "cpl",
        "worktree": str(target["wt"]),
        "workstream": "TEST-WS",
        "branch": "project/test",
        "audit_base_sha": target["base"],
        "effort": "high",
        "mode": "writer",
        "session": "ses-t",
        "state_path": str(target["state"]),
        "canonical_root": str(canon),
        "allow_same_cwd_pids": False,
        "allow_suppressed_routing": False,
        "install_pre_push_hook": False,
        "run_dir": str(target["wt"].parent / "rundir"),
    }
    kwargs.update(over)
    return launcher_mod.init(**kwargs)


# --------------------------------------------------------------------------
# Areas 1-5: authority default, Semantic Completion, non-stop, local
# decisions, bounded XHIGH reach the implementer context.
# --------------------------------------------------------------------------

def _implementer_text() -> str:
    return (REPO_ROOT / ".opencode" / "agents" / "foundry-implementer.md").read_text(
        encoding="utf-8"
    )


def test_area01_authority_default_in_implementer_context() -> None:
    text = _implementer_text()
    assert "TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT" in text
    doc = _doc()
    doc.pop("technical_decision_authority", None)
    resolved = autonomy_mod.autonomy_defaults(doc)
    assert resolved["technical_decision_authority"] == "AUTONOMOUS_WITHIN_CONTRACT"


def test_area01_authority_value_in_capsule() -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools" / "foundry"))
    try:
        import context_capsule as capsule_mod
    finally:
        sys.path.pop(0)
    text = capsule_mod.build_capsule(_doc(), _facts(), "/tmp/S.yaml")
    assert "technical_decision_authority: AUTONOMOUS_WITHIN_CONTRACT" in text
    payload = json.loads(capsule_mod.build_capsule_json(_doc(), _facts(), "/tmp/S.yaml"))
    assert payload["technical_decision_authority"] == "AUTONOMOUS_WITHIN_CONTRACT"


def test_area02_semantic_completion_tui_and_headless() -> None:
    work = (REPO_ROOT / ".opencode" / "commands" / "work.md").read_text(encoding="utf-8")
    assert "Semantic Completion" in work
    assert "Semantic Completion" in _implementer_text()
    assert autonomy_mod.WORK_DIRECTIVE in autonomy_mod.HEADLESS_EXTRAS
    assert "Semantic Completion" in autonomy_mod.HEADLESS_EXTRAS


def test_area03_no_stop_at_first_remediable_failure() -> None:
    text = _implementer_text()
    assert "A first failing test is diagnostic evidence, not a stop condition" in text
    assert "Execute through Semantic Completion" in text


def test_area04_ordinary_decisions_without_coordinator() -> None:
    text = _implementer_text()
    assert "Never relay routine" in text
    assert "technical choices to the Coordinator" in text


def test_area05_xhigh_bounded_technical_adjudication() -> None:
    assert "XHIGH remains bounded" in _implementer_text()
    adjudicator = (REPO_ROOT / ".opencode" / "agents" / "foundry-adjudicator.md").read_text(
        encoding="utf-8"
    )
    assert "bounded technical adjudication only" in adjudicator


# --------------------------------------------------------------------------
# Area 6: early primary success does not authorize unrelated work.
# --------------------------------------------------------------------------

def test_area06_early_success_hardening_order_locked() -> None:
    assert "Never invent unrelated work" in _implementer_text()
    assert autonomy_mod.EARLY_COMPLETION_HARDENING_ORDER[0] == "impacted validation"
    assert autonomy_mod.EARLY_COMPLETION_HARDENING_ORDER[-1] == "successor planning"
    doc = _doc(
        continuation_policy="BOUNDED_IN_SCOPE",
        remaining_scope=["implement autonomy checks"],
    )
    verdict, _ = autonomy_mod.continuation_decision(doc, "rewrite the Rules Core")
    assert verdict == "SCOPE_REFUSED"


# --------------------------------------------------------------------------
# Area 7: conditional continuation cannot exceed declared scope.
# --------------------------------------------------------------------------

def test_area07_continuation_default_exact_action_only() -> None:
    doc = _doc()
    verdict, reason = autonomy_mod.continuation_decision(doc, "anything else")
    assert verdict == "EXACT_ACTION_ONLY"
    assert "EXACT_NEXT_ACTION_ONLY" in reason
    verdict, _ = autonomy_mod.continuation_decision(doc, doc["exact_next_action"])
    assert verdict == "PROCEED"


def test_area07_bounded_scope_refusals() -> None:
    doc = _doc(
        continuation_policy="BOUNDED_IN_SCOPE",
        remaining_scope=["implement autonomy checks", "automatic branch creation"],
        authority_gates=["freeze question"],
    )
    verdict, _ = autonomy_mod.continuation_decision(doc, "implement autonomy checks")
    assert verdict == "PROCEED"
    verdict, _ = autonomy_mod.continuation_decision(doc, "automatic branch creation")
    assert verdict == "SCOPE_REFUSED"
    verdict, reason = autonomy_mod.continuation_decision(doc, "unlisted idea")
    assert verdict == "SCOPE_REFUSED"
    assert "remaining_scope" in reason
    verdict, _ = autonomy_mod.continuation_decision(doc, "freeze question")
    assert verdict in ("SCOPE_REFUSED", "AUTHORITY_GATE_STOP")
    verdict, reason = autonomy_mod.continuation_decision(doc, "git worktree add ../x")
    assert verdict == "SCOPE_REFUSED"
    assert "BRANCH_WORKTREE_CREATION_REFUSED" in reason


def test_area07_malformed_policy_fails_closed() -> None:
    doc = _doc(continuation_policy="WHATEVER")
    assert any("continuation_policy" in e for e in state_mod.validate(doc))


# --------------------------------------------------------------------------
# Area 8: engine/Rules semantic failure cannot become harness remediation.
# --------------------------------------------------------------------------

def test_area08_engine_fail_closed_in_policy_layers() -> None:
    assert "fails closed at the engine boundary" in _implementer_text()
    adjudicator = (REPO_ROOT / ".opencode" / "agents" / "foundry-adjudicator.md").read_text(
        encoding="utf-8"
    )
    assert "fail closed at the engine boundary" in adjudicator
    # Ambiguous causality stays UNKNOWN: unknown classes rejected, UNKNOWN kept.
    doc = _doc(failure_class="HARNESS_DEFECT")
    assert state_mod.validate(doc) == []
    doc = _doc(failure_class="MAYBE_ENGINE")
    assert any("failure_class" in e for e in state_mod.validate(doc))


# --------------------------------------------------------------------------
# Areas 9-10: machine-checkable successor planning, Coordinator-gated exec.
# --------------------------------------------------------------------------

def test_area09_successor_spec_machine_checkable() -> None:
    assert autonomy_mod.validate_successor_spec(_successor_spec()) == []
    bad = _successor_spec()
    del bad["initial_prompt"]
    assert any("initial_prompt" in e for e in autonomy_mod.validate_successor_spec(bad))
    assert any(
        "recommended_lane" in e
        for e in autonomy_mod.validate_successor_spec(_successor_spec(recommended_lane="low"))
    )
    many = [_successor_spec(objective=f"s{i}") for i in range(4)]
    assert any("maximum default: 3" in e for e in autonomy_mod.validate_successor_set(many))
    assert autonomy_mod.validate_successor_set([_successor_spec()]) == []


def test_area09_successor_pointer_checks() -> None:
    status, errors = autonomy_mod.check_successor(_doc())
    assert (status, errors) == ("NONE", [])
    status, errors = autonomy_mod.check_successor(
        _doc(successor_plan={"status": "PROPOSED"}), None
    )
    assert status == "PROPOSED" and errors
    status, errors = autonomy_mod.check_successor(
        _doc(successor_plan={"status": "PROPOSED"}), _successor_spec()
    )
    assert (status, errors) == ("PROPOSED", [])
    doc = _doc(
        successor_plan={"status": "AUTHORIZED", "preauthorized": True,
                        "spec_path": "p", "spec_sha256": "s"}
    )
    _, errors = autonomy_mod.check_successor(doc, _successor_spec())
    assert any("SUCCESSOR_NOT_AUTHORIZED" in e for e in errors)
    spec = _successor_spec(authorization="Coordinator: proceed with WS199")
    _, errors = autonomy_mod.check_successor(doc, spec)
    assert errors == []
    # No fabricated future SHAs without provenance.
    spec = _successor_spec(source_lock_basis="continue from " + "d" * 40)
    assert any("sha_provenance" in e for e in autonomy_mod.validate_successor_spec(spec))
    spec["sha_provenance"] = "WS198 terminal seal commit dddd.. (read at planning)"
    assert autonomy_mod.validate_successor_spec(spec) == []


def test_area10_successor_execution_coordinator_gated() -> None:
    tools = REPO_ROOT / "tools" / "foundry"
    # autonomy.py is pure logic: no process execution capability at all.
    tree = ast.parse((tools / "autonomy.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "re", "typing", "collections.abc", "collections"}, imported
    # No successor-related line anywhere in launcher/state/capsule carries an
    # execution shape (branch/worktree creation, remote mutation, provider
    # switch): planning stays plan-only, execution needs a fresh launch.
    for name in ("launcher.py", "state.py", "context_capsule.py", "autonomy.py"):
        for line in (tools / name).read_text(encoding="utf-8").splitlines():
            if "successor" in line.lower():
                assert autonomy_mod.scan_forbidden_plan_shapes(line) == [], (name, line)
    # check_successor returns (status, errors) only — never an action.
    status, errors = autonomy_mod.check_successor(
        _doc(successor_plan={"status": "AUTHORIZED", "preauthorized": True,
                             "spec_path": "p", "spec_sha256": "s"}),
        _successor_spec(authorization="Coordinator: proceed"),
    )
    assert status == "AUTHORIZED" and errors == []
    # Malformed preauthorization never coerces to authorized.
    doc = _doc(successor_plan={"status": "AUTHORIZED"})
    errors = state_mod.validate(doc)
    assert any("spec_path" in e or "preauthorized" in e for e in errors)


# --------------------------------------------------------------------------
# Areas 11-12: no implicit branch/worktree creation or remote mutation.
# --------------------------------------------------------------------------

def test_area11_no_implicit_branch_worktree() -> None:
    assert autonomy_mod.scan_forbidden_plan_shapes("git worktree add ../x") == [
        "BRANCH_WORKTREE_CREATION_REFUSED"
    ]
    assert autonomy_mod.scan_forbidden_plan_shapes("checkout -b feature") == [
        "BRANCH_WORKTREE_CREATION_REFUSED"
    ]
    assert autonomy_mod.scan_forbidden_plan_shapes("write the capsule") == []
    policy = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    ext = policy["permission"]["external_directory"]
    # No broad external allow: sibling checkouts are at most ask-gated, and
    # declared sibling worktrees gain explicit denies at launch (sibling_denies
    # injected into the bundle; denied paths stay boundaries, not puzzles).
    assert ext.get("/tmp/*") == "allow"
    assert ext.get("/home/moeen/code/*") in ("ask", "deny")
    assert ext.get("*") != "allow"
    bash = policy["permission"]["bash"]
    for pattern in ("git worktree add*", "git checkout -b*", "git switch -c*"):
        assert bash.get(pattern) == "deny", pattern


def test_area12_no_implicit_remote_mutation() -> None:
    assert autonomy_mod.scan_forbidden_plan_shapes("git push origin x") == [
        "REMOTE_MUTATION_REFUSED"
    ]
    policy = json.loads((REPO_ROOT / "opencode.json").read_text(encoding="utf-8"))
    assert policy["permission"]["bash"].get("git push*") == "deny"
    assert "only authorized remote-write path" in _implementer_text()


# --------------------------------------------------------------------------
# Area 13: rotation preserves exact resumable state.
# --------------------------------------------------------------------------

def test_area13_rotation_preserves_resumable_state() -> None:
    doc = _doc(
        rotation_guidance={"recommendation": "ROTATE_TO_FRESH_CONTINUATION",
                           "reason": "latency stall", "export_verified": False},
        remaining_scope=["implement autonomy checks"],
    )
    before = yaml.safe_dump(doc)
    rendered = autonomy_mod.rotation_render(doc)
    assert "ROTATE_TO_FRESH_CONTINUATION" in rendered
    assert "export-missing" in rendered
    assert yaml.safe_dump(doc) == before  # advisory render is pure
    assert doc["remaining_scope"] == ["implement autonomy checks"]
    assert doc["exact_next_action"] == "implement autonomy checks"
    assert doc["validated_head"] is None
    verified = _doc(rotation_guidance={"recommendation": "REVIEW_PROMPT",
                                       "reason": "r", "export_verified": True})
    assert "export-verified" in autonomy_mod.rotation_render(verified)
    assert state_mod.validate(doc) == []


# --------------------------------------------------------------------------
# Area 14: missing telemetry never becomes fabricated evidence.
# --------------------------------------------------------------------------

def test_area14_no_fabricated_telemetry() -> None:
    assert autonomy_mod.scan_telemetry_fabrication(
        "saved 1200 tokens via cache hits"
    ) == ["TELEMETRY_FABRICATION_RISK: numeric token/cache/cost claim without export provenance"]
    assert autonomy_mod.scan_telemetry_fabrication("TOKEN_ECONOMY_BENCHMARK = NOT_RUN") == []
    assert autonomy_mod.scan_telemetry_fabrication("cache evidence UNKNOWN") == []
    assert "SESSION_ROTATION_THRESHOLD" not in (
        REPO_ROOT / "tools" / "foundry" / "autonomy.py"
    ).read_text(encoding="utf-8")
    economy = (REPO_ROOT / "docs" / "foundry-execution" / "TOKEN_ECONOMY.md").read_text(
        encoding="utf-8"
    )
    assert "TOKEN_ECONOMY_BENCHMARK = NOT_RUN" in economy


# --------------------------------------------------------------------------
# Areas 15-16: capsule continuation content, no static duplication.
# --------------------------------------------------------------------------

def test_area15_capsule_carries_continuation_values() -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools" / "foundry"))
    try:
        import context_capsule as capsule_mod
    finally:
        sys.path.pop(0)
    doc = _doc(
        continuation_policy="BOUNDED_IN_SCOPE",
        remaining_scope=["a", "b"],
        do_not_rerun=["r1"],
        successor_plan={"status": "PROPOSED"},
        rotation_guidance={"recommendation": "REVIEW_PROMPT", "reason": "r"},
    )
    text = capsule_mod.build_capsule(doc, _facts(), "/tmp/S.yaml")
    for needle in (
        "continuation_policy: BOUNDED_IN_SCOPE",
        "remaining_scope: 2 item(s)",
        "do_not_rerun: 1 entr(ies)",
        "completion_ready:",
        "successor_plan: PROPOSED",
        "rotation: REVIEW_PROMPT",
    ):
        assert needle in text, needle
    payload = json.loads(capsule_mod.build_capsule_json(doc, _facts(), "/tmp/S.yaml"))
    assert payload["remaining_scope_count"] == 2
    assert payload["successor_status"] == "PROPOSED"


def test_area16_no_static_text_duplication() -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools" / "foundry"))
    try:
        import context_capsule as capsule_mod
    finally:
        sys.path.pop(0)
    text = capsule_mod.build_capsule(_doc(), _facts(), "/tmp/S.yaml")
    assert "inspect → hypothesize" not in text
    assert autonomy_mod.WORK_DIRECTIVE not in text
    assert len(text.encode("utf-8")) <= autonomy_mod.CAPSULE_BUDGET_BYTES
    work = (REPO_ROOT / ".opencode" / "commands" / "work.md").read_text(encoding="utf-8")
    assert len(work.encode("utf-8")) <= 2048


# --------------------------------------------------------------------------
# Area 17: legacy state compatibility.
# --------------------------------------------------------------------------

def test_area17_legacy_states_keep_working() -> None:
    assert state_mod.validate(_doc()) == []
    resolved = autonomy_mod.autonomy_defaults(_doc())
    assert resolved["continuation_policy"] == "EXACT_NEXT_ACTION_ONLY"
    assert resolved["successor_status"] == "NONE"
    assert resolved["rotation_recommendation"] == "NO_ROTATION"
    legacy = _doc()
    legacy["schema_version"] = "1.0"
    legacy["current_head"] = legacy.pop("state_written_against_head")
    legacy.pop("validated_head", None)
    out = state_mod.migrate(legacy)
    assert "continuation_policy" not in out
    assert "successor_plan" not in out
    assert "rotation_guidance" not in out
    assert state_mod.validate(out) == []
    ready, _ = autonomy_mod.check_completion_readiness(_doc(status="COMPLETE"))
    assert ready is False


# --------------------------------------------------------------------------
# Area 18: WS196 canonical routing regressions.
# --------------------------------------------------------------------------

def test_area18_ws196_routing_intact() -> None:
    assert launcher_mod.build_argv("opencode", "headless", ["x"])[1] == "run"
    assert "run" not in launcher_mod.build_argv("opencode", "tui", ["x"])
    assert launcher_mod.CANONICAL_SAFE_PUSH_REL == ("tools", "foundry", "safe_push.py")
    with pytest.raises(ValueError):
        launcher_mod.resolve_canonical_tools("")


# --------------------------------------------------------------------------
# Area 19: safe-push gates unchanged (plus completion boundary).
# --------------------------------------------------------------------------

def test_area19_safe_push_gates_preserved() -> None:
    from foundry import safe_push as safe_push_mod

    assert hasattr(safe_push_mod, "main")
    # Early COMPLETE (null credit, open scope) is not completion-ready, so it
    # can never become pushed validation credit through safe_push.
    ready, reasons = autonomy_mod.check_completion_readiness(
        _doc(status="COMPLETE", remaining_scope=["open"])
    )
    assert ready is False
    assert any("remaining_scope" in r for r in reasons)


# --------------------------------------------------------------------------
# Area 20: Go default / explicit Zen override unchanged.
# --------------------------------------------------------------------------

def test_area20_provider_identity_unchanged() -> None:
    ident = launcher_mod.execution_identity(None, "high")
    assert ident["provider"] == "opencode-go"
    assert ident["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert ident["override"] == "canonical"
    zen = launcher_mod.execution_identity("zen", "xhigh")
    assert zen["provider"] == "opencode"
    assert zen["override"] == "zen"
    with pytest.raises(ValueError):
        launcher_mod.execution_identity(None, "medium")
    with pytest.raises(ValueError):
        launcher_mod.execution_identity("other", "high")
    with pytest.raises(ValueError):
        launcher_mod.validate_child_options(["--model", "x"])
    with pytest.raises(ValueError):
        launcher_mod.validate_child_options(["-c"])


# --------------------------------------------------------------------------
# Area 21 + WS92/WS93 regression: TUI/headless parity, exit-0 false success.
# --------------------------------------------------------------------------

def test_area21_tui_headless_parity_and_prompt_forms() -> None:
    assert autonomy_mod.TUI_PROMPT_CHILD_FORM == '--prompt "<task>"'
    assert autonomy_mod.TUI_PROMPT_LAUNCHER_FORM == '-- --prompt "<task>"'
    autonomy_doc = (
        REPO_ROOT / "docs" / "foundry-execution" / "AUTONOMY.md"
    ).read_text(encoding="utf-8")
    assert "opencode run --auto <bare message>" in autonomy_doc
    assert '--prompt "<task>"' in autonomy_doc


def test_tui_bare_positional_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="--prompt"):
        launcher_mod.canonicalize_tui_extras(["do the thing"])
    with pytest.raises(ValueError, match="--prompt"):
        launcher_mod.canonicalize_tui_extras(["--", "do the thing"])
    assert launcher_mod.canonicalize_tui_extras(["--prompt", "do the thing"]) == [
        "--prompt",
        "do the thing",
    ]
    assert launcher_mod.canonicalize_tui_extras(["--", "--prompt", "do the thing"]) == [
        "--prompt",
        "do the thing",
    ]
    assert launcher_mod.canonicalize_tui_extras([]) == []


def test_ws92_ws93_failure_shape_refused_before_exec(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exact WS92/WS93 shape: TUI bare prompt -> directory error, exit 0.

    The launcher must refuse the shape (LAUNCH_REFUSED, nonzero) before any
    child exec, so the exit-0 false success can never reach LAUNCH_END.
    """
    record = tmp_path / "argv.log"
    monkeypatch.setenv("STUB_ARGV_FILE", str(record))
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    stub = _cli_shape_stub(tmp_path)
    plan = _plan(target, canon, ui_mode="tui", opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    rc = launcher_mod.launch(
        plan, ["do the thing"], str(target["wt"]), "TEST-WS", "high"
    )
    assert rc == 1
    assert not record.exists()  # refused before exec: no false success possible


def test_tui_prompt_flag_reaches_child(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "argv-tui.log"
    monkeypatch.setenv("STUB_ARGV_FILE", str(record))
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    stub = _cli_shape_stub(tmp_path)
    plan = _plan(target, canon, ui_mode="tui", opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    rc = launcher_mod.launch(
        plan, ["--", "--prompt", "do the thing"], str(target["wt"]), "TEST-WS", "high"
    )
    assert rc == 7  # stub exit for the accepted --prompt shape
    parts = record.read_text(encoding="utf-8").strip().split(" ")
    assert parts[1] == "--auto"
    assert parts[2:] == ["--prompt", "do", "the", "thing"]
    assert "run" not in parts[1:]


def test_headless_bare_message_unchanged(
    target: dict, canon: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "argv-headless.log"
    monkeypatch.setenv("STUB_ARGV_FILE", str(record))
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    stub = _version_stub(tmp_path, exit_code=7)
    plan = _plan(target, canon, ui_mode="headless", opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    rc = launcher_mod.launch(plan, ["do the thing"], str(target["wt"]), "TEST-WS", "high")
    assert rc == 7
    parts = record.read_text(encoding="utf-8").strip().split(" ")
    assert parts[1:3] == ["run", "--auto"]
    assert parts[3:] == ["do", "the", "thing"]


def test_launch_context_carries_autonomy_values(target: dict, canon: Path, tmp_path: Path) -> None:
    stub = _version_stub(tmp_path)
    plan = _plan(target, canon, opencode_bin=str(stub))
    assert plan["verdict"] == "LAUNCH_READY", plan
    context = json.loads(Path(plan["context_path"]).read_text(encoding="utf-8"))
    assert context["technical_decision_authority"] == "AUTONOMOUS_WITHIN_CONTRACT"
    assert context["continuation_policy"] == "EXACT_NEXT_ACTION_ONLY"
    assert context["successor_status"] == "NONE"
    assert context["rotation_recommendation"] == "NO_ROTATION"
    assert context["completion_ready"] is True


def test_metrics_record_ui_mode(tmp_path: Path) -> None:
    from foundry import metrics as metrics_mod

    path = tmp_path / "m.jsonl"
    entry = metrics_mod.record(
        str(path), _provenance={"ui_mode": "AUTOCAPTURED"}, task_id="T", ui_mode="tui"
    )
    assert entry["ui_mode"] == "tui"

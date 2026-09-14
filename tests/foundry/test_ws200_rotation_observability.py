"""WS200 Foundry session-rotation observability (hermetic).

Threshold-free advisory rotation signals from state/Git milestone facts
only, surfaced in the capsule and launch context, with optional WS199
AUTOCAPTURED telemetry enrichment that never drives the recommendation.

All tests hermetic: synthetic state/Git facts, throwaway git repos, stub
binaries, synthetic telemetry-status/metrics fixtures. No network, no live
OpenCode sessions, no invented token figures.
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

sys.path.insert(0, str(REPO_ROOT / "tools" / "foundry"))

import context_capsule as capsule_mod  # noqa: E402

CPL_SLUG = "moeendres-png/commander-playtest-lab"

HEAD_A = "a" * 40
HEAD_B = "b" * 40


# --------------------------------------------------------------------------
# Fixtures and helpers.
# --------------------------------------------------------------------------

def _doc(**over: object) -> dict:
    doc: dict = {
        "schema_version": "2.0",
        "repository": CPL_SLUG,
        "worktree": "/tmp/wt",
        "branch": "project/x",
        "audit_base_sha": HEAD_A,
        "audit_base_tree": HEAD_B,
        "state_written_against_head": HEAD_A,
        "validated_head": None,
        "objective": "x",
        "in_scope": ["work"],
        "out_of_scope": ["provider selection"],
        "ownership": "tester",
        "status": "ACTIVE",
        "exact_next_action": "do the next thing",
        "remaining_scope": [],
    }
    doc.update(over)
    return doc


def _facts(head: str = HEAD_A, dirty: int = 0) -> dict:
    return {"branch": "project/x", "head": head, "tree": HEAD_B, "dirty_entries": dirty}


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


_TELEMETRY_RUN_SEQ = 0


def _telemetry_run(
    tmp_path: Path,
    *,
    status: str = "CAPTURED",
    session_id: str = "ses_exact1",
    values: dict | None = None,
    provenance_override: dict | None = None,
    record_session_id: str | None = None,
    write_metrics: bool = True,
) -> Path:
    """Synthetic WS199 run dir: telemetry-status.json + metrics.jsonl."""
    global _TELEMETRY_RUN_SEQ
    _TELEMETRY_RUN_SEQ += 1
    run_dir = tmp_path / f"run-{_TELEMETRY_RUN_SEQ}-{status}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "telemetry-status.json").write_text(
        json.dumps(
            {
                "status": status,
                "reason": "OK" if status == "CAPTURED" else "EXACT_SESSION_ID_UNAVAILABLE",
                "session_id": session_id,
                "metrics_path": str(run_dir / "metrics.jsonl"),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if write_metrics and status == "CAPTURED":
        vals = dict(values or {})
        record: dict = {"task_class": "session-telemetry", "session_id": record_session_id or session_id}
        record.update(vals)
        prov = {field: "AUTOCAPTURED" for field in vals}
        if provenance_override:
            prov.update(provenance_override)
        record["provenance"] = prov
        (run_dir / "metrics.jsonl").write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    return run_dir


FULL_TELEMETRY_VALUES = {
    "model_turns": 12,
    "tool_calls": 34,
    "tool_errors": 1,
    "tokens_input": 1000,
    "tokens_output": 200,
    "tokens_reasoning": 50,
    "tokens_cache_read": 7,
    "tokens_cache_write": 0,
    "cost_usd": 0.13,
    "elapsed_seconds": 60.0,
}

ZERO_TELEMETRY_VALUES = {key: 0 for key in FULL_TELEMETRY_VALUES}

HUGE_TELEMETRY_VALUES = {
    "model_turns": 10**9,
    "tool_calls": 10**9,
    "tool_errors": 10**9,
    "tokens_input": 10**12,
    "tokens_output": 10**12,
    "tokens_reasoning": 10**12,
    "tokens_cache_read": 10**12,
    "tokens_cache_write": 10**12,
    "cost_usd": 10**9,
    "elapsed_seconds": 10**9,
}


def _rotation_line(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("rotation:"):
            return line
    raise AssertionError("no rotation line in capsule")


# --------------------------------------------------------------------------
# 1. Pure rotation observation / recommendation.
# --------------------------------------------------------------------------

def test_pure_defaults_no_rotation() -> None:
    rec, reasons = autonomy_mod.recommend_rotation(_doc(), _facts())
    assert rec == "NO_ROTATION"
    assert reasons == []
    obs = autonomy_mod.observe_rotation(_doc(), _facts())
    assert obs["recommendation"] == "NO_ROTATION"
    assert obs["provenance"] == "state-derived+git-derived"
    assert obs["persisted_recommendation"] == "NO_ROTATION"
    assert obs["remaining_scope_present"] is False
    assert obs["head_drift"] is False
    assert obs["tree_clean"] is True


def test_pure_persisted_guidance_preserved() -> None:
    doc = _doc(rotation_guidance={"recommendation": "REVIEW_PROMPT", "reason": "r"})
    rec, reasons = autonomy_mod.recommend_rotation(doc, _facts())
    assert rec == "REVIEW_PROMPT"
    assert reasons[0]["code"] == "PERSISTED_ROTATION_REVIEW_REQUEST"
    assert reasons[0]["source"] == "state-derived"
    doc = _doc(rotation_guidance={"recommendation": "ROTATE_TO_FRESH_CONTINUATION", "reason": "r"})
    rec, reasons = autonomy_mod.recommend_rotation(doc, _facts())
    assert rec == "ROTATE_TO_FRESH_CONTINUATION"
    assert reasons[0]["code"] == "PERSISTED_ROTATE_REQUEST"


def test_pure_malformed_persisted_falls_back_conservative() -> None:
    doc = _doc(rotation_guidance={"recommendation": "ROTATE_WHEN_LARGE"})
    rec, reasons = autonomy_mod.recommend_rotation(doc, _facts())
    assert rec == "NO_ROTATION"
    assert reasons == []


def test_pure_explicit_stall_requires_status_and_failure() -> None:
    stalled = _doc(status="BLOCKED", failure_class="HARNESS_DEFECT", current_failure="x")
    rec, reasons = autonomy_mod.recommend_rotation(stalled, _facts())
    assert rec == "REVIEW_PROMPT"
    assert reasons[0]["code"] == "EXPLICIT_STALL_STATE"
    stalled = _doc(status="STALE", current_failure="waiting on upstream")
    rec, _ = autonomy_mod.recommend_rotation(stalled, _facts())
    assert rec == "REVIEW_PROMPT"
    # ACTIVE with the same failure is ordinary debugging, not a stall.
    active = _doc(status="ACTIVE", failure_class="HARNESS_DEFECT", current_failure="x")
    assert autonomy_mod.recommend_rotation(active, _facts())[0] == "NO_ROTATION"
    # BLOCKED/STALE without any failure identity is not a stall.
    assert autonomy_mod.recommend_rotation(_doc(status="BLOCKED"), _facts())[0] == "NO_ROTATION"
    assert autonomy_mod.recommend_rotation(_doc(status="STALE"), _facts())[0] == "NO_ROTATION"
    assert autonomy_mod.recommend_rotation(_doc(status="WAITING"), _facts())[0] == "NO_ROTATION"


def test_pure_repeated_checkpoint_signals_review_once() -> None:
    doc = _doc()
    facts = _facts()
    fingerprint = autonomy_mod.checkpoint_fingerprint(doc, facts)
    assert len(fingerprint) == 16
    rec, reasons = autonomy_mod.recommend_rotation(doc, facts, {"fingerprint": fingerprint})
    assert rec == "REVIEW_PROMPT"
    assert reasons[0]["code"] == "REPEATED_CHECKPOINT_WITHOUT_MATERIAL_PROGRESS"
    assert reasons[0]["source"] == "state-derived+git-derived"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d, f: (d, _facts(head=HEAD_B)),
        lambda d, f: (_doc(exact_next_action="a different next step"), f),
        lambda d, f: (_doc(validated_head=HEAD_A), f),
        lambda d, f: (_doc(remaining_scope=["one more item"]), f),
        lambda d, f: (_doc(failure_class="HARNESS_DEFECT", current_failure="x"), f),
        lambda d, f: (_doc(state_written_against_head=HEAD_B), f),
    ],
)
def test_pure_material_progress_breaks_repeat(mutate) -> None:
    doc = _doc()
    facts = _facts()
    fingerprint = autonomy_mod.checkpoint_fingerprint(doc, facts)
    doc2, facts2 = mutate(doc, facts)
    rec, _ = autonomy_mod.recommend_rotation(doc2, facts2, {"fingerprint": fingerprint})
    assert rec == "NO_ROTATION"


def test_pure_fingerprint_ignores_descriptive_noise() -> None:
    doc = _doc()
    assert autonomy_mod.checkpoint_fingerprint(doc, _facts(dirty=0)) == autonomy_mod.checkpoint_fingerprint(
        doc, _facts(dirty=9)
    )
    noisy = dict(_facts())
    noisy["commits_since_base"] = 41
    assert autonomy_mod.checkpoint_fingerprint(doc, noisy) == autonomy_mod.checkpoint_fingerprint(doc, _facts())
    assert autonomy_mod.checkpoint_fingerprint(doc, _facts()) == autonomy_mod.checkpoint_fingerprint(
        dict(doc), dict(_facts())
    )


@pytest.mark.parametrize(
    "doc_over,facts_over",
    [
        ({"validated_head": HEAD_A}, {}),  # clean validated checkpoint
        ({}, {"head": HEAD_B}),  # live HEAD ahead of validated/described HEAD
        ({"state_written_against_head": HEAD_B}, {}),  # state-written HEAD drift
        ({"remaining_scope": ["a", "b"]}, {}),  # remaining scope present
        ({"failure_class": "HARNESS_DEFECT", "current_failure": "x"}, {}),  # active failure
        ({"status": "COMPLETE", "validated_head": HEAD_A}, {}),  # completion-ready terminal
        ({}, {"dirty": 5}),  # dirty worktree
        ({"remaining_scope": []}, {}),  # remaining scope empty
    ],
)
def test_pure_ordinary_engineering_never_noises_review(doc_over: dict, facts_over: dict) -> None:
    doc = _doc(**doc_over)
    dirty = facts_over.pop("dirty", 0)
    facts = _facts(dirty=dirty, **facts_over)
    if doc_over.get("status") == "COMPLETE":
        doc = _doc(**{**doc_over, "remaining_scope": [], "failed_gates": []})
    rec, _ = autonomy_mod.recommend_rotation(doc, facts)
    assert rec == "NO_ROTATION"


def test_pure_reason_codes_are_structural_only() -> None:
    assert set(autonomy_mod.ROTATION_REASON_CODES) == {
        "PERSISTED_ROTATION_REVIEW_REQUEST",
        "PERSISTED_ROTATE_REQUEST",
        "EXPLICIT_STALL_STATE",
        "REPEATED_CHECKPOINT_WITHOUT_MATERIAL_PROGRESS",
    }
    for forbidden in ("SESSION_FEELS_LONG", "CONTEXT_PROBABLY_FULL", "MODEL_SEEMS_STUCK"):
        assert forbidden not in autonomy_mod.ROTATION_REASON_CODES
    assert "SESSION_FEELS_LONG" not in autonomy_mod.ROTATION_REVIEW_GUIDANCE


# --------------------------------------------------------------------------
# 2. autonomy.py backward compatibility.
# --------------------------------------------------------------------------

def test_backward_compat_rotation_render_legacy() -> None:
    assert autonomy_mod.rotation_render(_doc()) == "rotation: NO_ROTATION"
    text = autonomy_mod.rotation_render(
        _doc(rotation_guidance={"recommendation": "REVIEW_PROMPT", "reason": "r"})
    )
    assert "rotation: REVIEW_PROMPT" in text
    assert "export-missing" in text
    text = autonomy_mod.rotation_render(
        _doc(
            rotation_guidance={
                "recommendation": "REVIEW_PROMPT",
                "reason": "r",
                "export_verified": True,
            }
        )
    )
    assert "export-verified" in text
    assert autonomy_mod.autonomy_defaults({})["rotation_recommendation"] == "NO_ROTATION"
    assert state_mod.validate(_doc()) == []


def test_backward_compat_autonomy_imports_stay_pure() -> None:
    tree = ast.parse((REPO_ROOT / "tools" / "foundry" / "autonomy.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "re", "typing", "collections.abc", "collections"}, imported


# --------------------------------------------------------------------------
# 3-6. Capsule text/JSON, budget, telemetry-absent disclaimer.
# --------------------------------------------------------------------------

def test_capsule_text_absent_telemetry_path() -> None:
    text = capsule_mod.build_capsule(_doc(), _facts(), "/tmp/S.yaml")
    assert "rotation: NO_ROTATION" in text
    assert "telemetry: absent [export-missing" in text
    assert "no token/cache figures exist" in text
    payload = json.loads(capsule_mod.build_capsule_json(_doc(), _facts(), "/tmp/S.yaml"))
    assert payload["rotation_recommendation"] == "NO_ROTATION"
    assert payload["telemetry_available"] is False
    assert payload["rotation_fingerprint"] == autonomy_mod.checkpoint_fingerprint(_doc(), _facts())
    assert "rotation: NO_ROTATION" in payload["rotation"]


def test_capsule_text_review_prompt_guidance() -> None:
    doc = _doc(rotation_guidance={"recommendation": "REVIEW_PROMPT", "reason": "r"})
    text = capsule_mod.build_capsule(doc, _facts(), "/tmp/S.yaml")
    assert "rotation: REVIEW_PROMPT (PERSISTED_ROTATION_REVIEW_REQUEST" in text
    assert "review_guidance:" in text
    assert "same\nworkstream/branch/state" in text or "same workstream/branch/state" in text
    assert "never\nchanges model/provider" in text or "never changes model/provider" in text
    payload = json.loads(capsule_mod.build_capsule_json(doc, _facts(), "/tmp/S.yaml"))
    assert payload["rotation_recommendation"] == "REVIEW_PROMPT"
    assert payload["rotation_reasons"][0]["code"] == "PERSISTED_ROTATION_REVIEW_REQUEST"


def test_capsule_budget_regression() -> None:
    doc = _doc(
        hard_gates=[f"gate {i} with some descriptive text" for i in range(12)],
        authority_gates=["gate a"],
        remaining_scope=["a", "b"],
        rotation_guidance={"recommendation": "REVIEW_PROMPT", "reason": "repeated checkpoint"},
    )
    text = capsule_mod.build_capsule(doc, _facts(), "/tmp/S.yaml")
    assert len(text.encode("utf-8")) <= autonomy_mod.CAPSULE_BUDGET_BYTES


def test_capsule_derive_telemetry_absent_tui_style(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _env()
    wt = tmp_path / "wt"
    wt.mkdir()
    _git(["init", "-b", "main"], wt, env)
    _git(["config", "user.email", "t@example.com"], wt, env)
    _git(["config", "user.name", "T"], wt, env)
    (wt / "f.txt").write_text("x\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "init"], wt, env)
    base = _git(["rev-parse", "HEAD"], wt, env)
    _git(["checkout", "-b", "project/x"], wt, env)
    state = _doc(worktree=str(wt), branch="project/x", audit_base_sha=base, state_written_against_head=base)
    state_path = wt / "S.yaml"
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    # TUI-style: no exact session ID, no telemetry-status capture, no run dir.
    monkeypatch.delenv("FOUNDRY_RUN_DIR", raising=False)
    text = capsule_mod.derive(str(state_path), str(wt), "text", False, None, None)
    assert "rotation: NO_ROTATION" in text
    assert "telemetry: absent [export-missing" in text
    assert "token/cache" not in text.replace("no token/cache figures exist", "")
    payload = json.loads(capsule_mod.derive(str(state_path), str(wt), "json", False, None, None))
    assert payload["telemetry_available"] is False


# --------------------------------------------------------------------------
# 7-9. Telemetry present enrichment, invariance, negative controls.
# --------------------------------------------------------------------------

def test_capsule_telemetry_captured_enrichment(tmp_path: Path) -> None:
    run_dir = _telemetry_run(tmp_path, values=dict(FULL_TELEMETRY_VALUES))
    text = capsule_mod.build_capsule(
        _doc(), _facts(), "/tmp/S.yaml", capsule_mod._load_telemetry(str(run_dir)), None
    )
    assert "rotation: NO_ROTATION" in text
    assert "telemetry: CAPTURED session ses_exact1 (AUTOCAPTURED)" in text
    assert "tokens_input=1000" in text
    assert "cost_usd=0.13" in text
    payload = json.loads(
        capsule_mod.build_capsule_json(
            _doc(), _facts(), "/tmp/S.yaml", capsule_mod._load_telemetry(str(run_dir)), None
        )
    )
    assert payload["telemetry_available"] is True
    assert payload["telemetry_provenance"] == "AUTOCAPTURED"
    assert payload["rotation_recommendation"] == "NO_ROTATION"


@pytest.mark.parametrize("values", [ZERO_TELEMETRY_VALUES, FULL_TELEMETRY_VALUES, HUGE_TELEMETRY_VALUES])
def test_telemetry_values_never_change_recommendation(tmp_path: Path, values: dict) -> None:
    doc = _doc()
    facts = _facts()
    expected = autonomy_mod.recommend_rotation(doc, facts)[0]
    run_dir = _telemetry_run(tmp_path, values=dict(values))
    telemetry = capsule_mod._load_telemetry(str(run_dir))
    assert telemetry is not None and telemetry["available"] is True
    # Pure recommendation takes no telemetry input: identical facts -> identical verdict.
    assert autonomy_mod.recommend_rotation(doc, facts)[0] == expected
    text = capsule_mod.build_capsule(doc, facts, "/tmp/S.yaml", telemetry, None)
    assert _rotation_line(text).startswith(f"rotation: {expected}")


@pytest.mark.parametrize("values", [ZERO_TELEMETRY_VALUES, FULL_TELEMETRY_VALUES, HUGE_TELEMETRY_VALUES])
def test_telemetry_values_never_change_review_prompt(tmp_path: Path, values: dict) -> None:
    doc = _doc(status="BLOCKED", failure_class="HARNESS_DEFECT", current_failure="x")
    facts = _facts()
    assert autonomy_mod.recommend_rotation(doc, facts)[0] == "REVIEW_PROMPT"
    run_dir = _telemetry_run(tmp_path, values=dict(values))
    text = capsule_mod.build_capsule(doc, facts, "/tmp/S.yaml", capsule_mod._load_telemetry(str(run_dir)), None)
    assert _rotation_line(text).startswith("rotation: REVIEW_PROMPT")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "PENDING"},
        {"status": "FAILED"},
        {"session_id": ""},
        {"record_session_id": "ses_other_session"},
        {"write_metrics": False},
        {"values": {"tokens_input": 5}, "provenance_override": {"tokens_input": "UNKNOWN"}},
    ],
)
def test_malformed_untrusted_telemetry_stays_disclaimer(tmp_path: Path, kwargs: dict) -> None:
    run_dir = _telemetry_run(tmp_path, **kwargs)  # type: ignore[arg-type]
    telemetry = capsule_mod._load_telemetry(str(run_dir))
    assert telemetry is None
    text = capsule_mod.build_capsule(_doc(), _facts(), "/tmp/S.yaml", telemetry, None)
    assert "telemetry: absent [export-missing" in text
    assert "rotation: NO_ROTATION" in text
    assert "tokens_input=" not in text


def test_telemetry_never_estimated_when_absent() -> None:
    assert capsule_mod._load_telemetry(None) is None
    assert capsule_mod._load_telemetry("/tmp/definitely-not-a-ws200-run-dir") is None
    assert "UNKNOWN" not in autonomy_mod.render_telemetry_info(None).replace("not telemetry", "")
    line = autonomy_mod.render_telemetry_info({"available": True, "provenance": "UNKNOWN", "values": {}})
    assert line.startswith("telemetry: absent")


# --------------------------------------------------------------------------
# 10-12. Launch context rendering, LAUNCH_READY, TUI/headless parity.
# --------------------------------------------------------------------------

def _canon(tmp_path: Path) -> Path:
    root = tmp_path / "canon"
    (root / ".opencode" / "agents").mkdir(parents=True)
    (root / ".opencode" / "skills").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    (root / ".opencode" / "agents" / "foundry-implementer.md").write_text("---\nvariant: high\n---\n", encoding="utf-8")
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
    (tools_dir / "safe_push.py").write_text("# stub\n", encoding="utf-8")
    return root


def _target(tmp_path: Path, state_over: dict | None = None) -> dict:
    env = _env()
    wt = tmp_path / "wt"
    wt.mkdir()
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
        **(state_over or {}),
    )
    state_path = wt / ".foundry" / "WORKSTREAM_STATE.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    return {"wt": wt, "env": env, "state": state_path, "base": base}


def _version_stub(tmp_path: Path) -> Path:
    stub = tmp_path / "fake-opencode-bin"
    stub.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        "if sys.argv[1:] == ['--version']:\n    print('1.18.30')\n    sys.exit(0)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def _plan(target: dict, canon: Path, stub: Path, **over: object) -> dict:
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
    return launcher_mod.init(opencode_bin=str(stub), **kwargs)


def test_launch_context_carries_advisory_without_gating(tmp_path: Path) -> None:
    target = _target(tmp_path)
    plan = _plan(target, _canon(tmp_path), _version_stub(tmp_path))
    assert plan["verdict"] == "LAUNCH_READY", plan
    context = json.loads(Path(plan["context_path"]).read_text(encoding="utf-8"))
    assert context["rotation_recommendation"] == "NO_ROTATION"
    assert context["rotation_advisory"]["recommendation"] == "NO_ROTATION"
    assert context["rotation_advisory"]["provenance"] == "state-derived+git-derived"
    assert context["rotation_telemetry_available"] is False
    assert len(context["rotation_advisory"]["fingerprint"]) == 16


def test_launch_ready_unaffected_by_review_prompt(tmp_path: Path) -> None:
    target = _target(
        tmp_path,
        {"status": "BLOCKED", "failure_class": "HARNESS_DEFECT", "current_failure": "x"},
    )
    plan = _plan(target, _canon(tmp_path), _version_stub(tmp_path))
    assert plan["verdict"] == "LAUNCH_READY", plan
    context = json.loads(Path(plan["context_path"]).read_text(encoding="utf-8"))
    assert context["rotation_advisory"]["recommendation"] == "REVIEW_PROMPT"
    assert context["rotation_advisory"]["reasons"][0]["code"] == "EXPLICIT_STALL_STATE"


def test_launcher_tui_headless_and_provider_identity_intact() -> None:
    assert launcher_mod.build_argv("opencode", "headless", ["x"])[1] == "run"
    assert "run" not in launcher_mod.build_argv("opencode", "tui", ["x"])
    ident = launcher_mod.execution_identity(None, "high")
    assert ident["provider"] == "opencode-go"
    assert ident["model"] == "opencode-go/muse-spark-1.3-contributor"
    zen = launcher_mod.execution_identity("zen", "xhigh")
    assert zen["provider"] == "opencode" and zen["override"] == "zen"
    with pytest.raises(ValueError):
        launcher_mod.execution_identity(None, "medium")


# --------------------------------------------------------------------------
# No automatic process control; no model/provider switching.
# --------------------------------------------------------------------------

def test_no_automatic_process_control_in_diff() -> None:
    for name in ("autonomy.py", "context_capsule.py", "launcher.py"):
        text = (REPO_ROOT / "tools" / "foundry" / name).read_text(encoding="utf-8")
        assert "os.kill" not in text, name
        assert "SIGTERM" not in text, name
        assert "SIGKILL" not in text, name
    autonomy_text = (REPO_ROOT / "tools" / "foundry" / "autonomy.py").read_text(encoding="utf-8")
    assert "process.terminate" not in autonomy_text
    assert "process.kill" not in autonomy_text
    assert "automatic `/compact`" not in autonomy_text


def test_rotation_logic_never_touches_model_provider() -> None:
    for func in (
        autonomy_mod.recommend_rotation,
        autonomy_mod.observe_rotation,
        autonomy_mod.checkpoint_fingerprint,
        autonomy_mod.format_observation,
        autonomy_mod.render_telemetry_info,
    ):
        source = ast.dump(ast.parse(__import__("inspect").getsource(func)))
        assert "execution_provider" not in source
    obs = autonomy_mod.observe_rotation(_doc(), _facts())
    assert "model" not in obs or obs.get("model") is None
    assert "provider" not in obs
    assert "variant" not in obs


# --------------------------------------------------------------------------
# WS199 / WS78 regression anchors.
# --------------------------------------------------------------------------

def test_ws199_exact_session_attribution_preserved() -> None:
    from foundry import session_capture as capture_mod

    assert capture_mod.read_exact_session_id("/tmp/definitely-not-a-ws200-run-dir", None) is None
    with pytest.raises(ValueError):
        capture_mod.validate_session_id("")


def test_ws78_token_economy_benchmark_still_not_run() -> None:
    economy = (REPO_ROOT / "docs" / "foundry-execution" / "TOKEN_ECONOMY.md").read_text(encoding="utf-8")
    assert "TOKEN_ECONOMY_BENCHMARK = NOT_RUN" in economy

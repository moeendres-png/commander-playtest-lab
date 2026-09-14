"""WS199 exact-session telemetry capture (hermetic).

Proves parallel-safe exact attribution, LOCAL_ONLY raw hygiene,
aggregate-only AUTOCAPTURED metrics, fail-open launcher integration, and
session_stats hardening. All OpenCode binaries are temporary stubs; no
network, no ambient sessions. Fixtures are synthetic export shapes only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(ROOT / "tools"))

from foundry import launcher as launcher_mod  # noqa: E402
from foundry import metrics as metrics_mod  # noqa: E402
from foundry import opencode_cli_version as version_mod  # noqa: E402
from foundry import session_capture as capture_mod  # noqa: E402
from foundry import session_stats as stats_mod  # noqa: E402


def _export(
    sid: str = "ses_abc123",
    tokens: dict | None = None,
    cost: float | None = 0.13,
    model: dict | None = None,
    extra_parts: list | None = None,
    secret_text: str | None = None,
) -> dict:
    if tokens is None:
        tokens = {"input": 100, "output": 20, "reasoning": 5, "cache": {"read": 7, "write": 0}}
    if model is None:
        model = {"providerID": "opencode-go", "id": "muse-spark-1.3-contributor", "variant": "high"}
    parts = [
        {"type": "step-start", "id": "s1"},
        {"type": "tool", "tool": "bash", "state": {"status": "completed"}},
        {"type": "tool", "tool": "edit", "state": {"status": "error"}},
        {"type": "patch", "files": ["a.py"], "hash": "x"},
    ]
    if extra_parts:
        parts.extend(extra_parts)
    if secret_text is not None:
        parts.append(
            {
                "type": "tool",
                "tool": "bash",
                "state": {"status": "completed", "input": secret_text, "output": secret_text},
            }
        )
        parts.append({"type": "text", "text": secret_text})
        parts.append({"type": "reasoning", "text": secret_text})
    return {
        "info": {
            "id": sid,
            "agent": "foundry-implementer",
            "model": model,
            "version": "1.18.30",
            "cost": cost,
            "tokens": tokens,
            "time": {"created": 1789049441000, "updated": 1789049501000},
        },
        "messages": [{"info": {}, "parts": parts}],
    }


def _stub(
    tmp_path: Path,
    exports: dict[str, dict],
    *,
    advertise_sanitize: bool = True,
    fail_export_rc: int | None = None,
    malformed_sids: set[str] | None = None,
    record_argv: Path | None = None,
) -> Path:
    """Stub ``opencode``: --version, export --help, export <sid> only.

    Never implements ``session list`` auto-selection: any ``list`` invocation
    exits nonzero so tests prove capture never depends on it.
    """
    stub = tmp_path / f"stub-{len(exports)}-{advertise_sanitize}"
    payload = {
        "exports": exports,
        "sanitize": advertise_sanitize,
        "fail_rc": fail_export_rc,
        "malformed": sorted(malformed_sids or set()),
    }
    blob = json.dumps(payload)
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"CONF = json.loads({blob!r})\n"
        "argv = sys.argv[1:]\n"
        "if argv == ['--version']:\n"
        f"    print({version_mod.QUALIFIED_OPENCODE_VERSION!r})\n"
        "    sys.exit(0)\n"
        "if argv[:2] == ['export', '--help'] or argv == ['export', '--help']:\n"
        "    print('opencode export [sessionID]')\n"
        "    print('      --sanitize    redact sensitive transcript and file data'\n"
        "          if CONF['sanitize'] else '      --pure        run without external plugins')\n"
        "    sys.exit(0)\n"
        "if argv and argv[0] == 'session':\n"
        "    sys.stderr.write('STUB: session list is never authoritative\\n')\n"
        "    sys.exit(3)\n"
        "if argv[:1] == ['export']:\n"
        "    rest = argv[1:]\n"
        "    rest = [a for a in rest if a == '--sanitize' or not a.startswith('-')]\n"
        "    sid = rest[-1] if rest else ''\n"
        "    import os\n"
        "    rec = os.environ.get('STUB_ARGV_FILE')\n"
        "    rec2 = os.environ.get('STUB_EXPORT_SID_FILE')\n"
        "    _extra = " + repr(str(record_argv) if record_argv else "") + "\n"
        "    targ = rec or (_extra or None)\n"
        "    if targ:\n"
        "        open(targ, 'a').write(' '.join(sys.argv) + chr(10))\n"
        "    if rec2:\n"
        "        open(rec2, 'a').write(sid + chr(10))\n"
        "    if CONF['fail_rc'] is not None:\n"
        "        sys.stderr.write('STUB: export failed\\n')\n"
        "        sys.exit(CONF['fail_rc'])\n"
        "    if sid in CONF['malformed']:\n"
        "        sys.stdout.write('{not json')\n"
        "        sys.exit(0)\n"
        "    if sid not in CONF['exports']:\n"
        "        sys.stderr.write(f'session not found: {sid}\\n')\n"
        "        sys.exit(1)\n"
        "    sys.stdout.write(json.dumps(CONF['exports'][sid]))\n"
        "    sys.exit(0)\n"
        "sys.stderr.write('STUB: unexpected argv\\n')\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


# --- session_stats hardening ------------------------------------------------


def test_stats_complete_export(tmp_path: Path) -> None:
    path = tmp_path / "e.json"
    path.write_text(json.dumps(_export()), encoding="utf-8")
    summary = stats_mod.summarize(str(path))
    assert summary["session_id"] == "ses_abc123"
    assert summary["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert summary["provider"] == "opencode-go"
    assert summary["variant"] == "high"
    assert summary["model_turns"] == 1
    assert summary["tool_calls"] == 2
    assert summary["tool_errors"] == 1
    assert summary["tokens_cache_write"] == 0  # legitimate zero preserved
    assert summary["compaction_count"] is None


def test_stats_missing_token_block(tmp_path: Path) -> None:
    export = _export()
    del export["info"]["tokens"]
    path = tmp_path / "e.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    summary = stats_mod.summarize(str(path))
    assert "tokens_input" not in summary
    assert "tokens_cache_read" not in summary
    assert "cost_usd" in summary  # cost independent of token block


def test_stats_partial_token_block(tmp_path: Path) -> None:
    export = _export(tokens={"input": 5})
    path = tmp_path / "e.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    summary = stats_mod.summarize(str(path))
    assert summary["tokens_input"] == 5
    assert "tokens_output" not in summary
    assert "tokens_cache_read" not in summary


def test_stats_zero_tokens_preserved_not_sentinel(tmp_path: Path) -> None:
    export = _export(tokens={"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}}, cost=0.0)
    path = tmp_path / "e.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    summary = stats_mod.summarize(str(path))
    assert summary["tokens_input"] == 0
    assert summary["tokens_cache_write"] == 0
    assert summary["cost_usd"] == 0.0


def test_stats_bool_tokens_rejected(tmp_path: Path) -> None:
    export = _export(tokens={"input": True, "output": False, "cache": {"read": True, "write": False}})
    path = tmp_path / "e.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    summary = stats_mod.summarize(str(path))
    assert "tokens_input" not in summary
    assert "tokens_cache_read" not in summary


def test_stats_live_running_not_error(tmp_path: Path) -> None:
    export = _export(extra_parts=[{"type": "tool", "tool": "bash", "state": {"status": "running"}}])
    path = tmp_path / "e.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    summary = stats_mod.summarize(str(path))
    assert summary["tool_calls"] == 3
    assert summary["tool_errors"] == 1


@pytest.mark.parametrize("bad", ['{not json', '{"nope": true}', '[1,2]', '"str"', 'null'])
def test_stats_malformed_and_non_session(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError):
        stats_mod.summarize(str(path))


def test_stats_empty_info_messages_rejected(tmp_path: Path) -> None:
    for doc in ({"info": {}, "messages": []}, {"info": {"id": "x"}, "messages": []}):
        path = tmp_path / "e.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(ValueError, match="empty info/messages"):
            stats_mod.summarize(str(path))


def test_stats_unknown_parts_ignored(tmp_path: Path) -> None:
    export = _export(
        extra_parts=[
            {"type": "text", "text": "hello"},
            {"type": "reasoning", "text": "think"},
            {"type": "future-kind", "blob": [1, 2]},
            "not-a-dict",
            {"no-type": True},
        ]
    )
    path = tmp_path / "e.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    summary = stats_mod.summarize(str(path))
    assert summary["tool_calls"] == 2
    blob = json.dumps(summary)
    assert "hello" not in blob


def test_stats_model_shape_variants(tmp_path: Path) -> None:
    export = _export(model={"id": "solo-model"})
    path = tmp_path / "e.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    summary = stats_mod.summarize(str(path))
    assert summary["model"] == "solo-model"
    assert "provider" not in summary
    export2 = _export(model="not-a-dict")  # type: ignore[dict-item]
    path.write_text(json.dumps(export2), encoding="utf-8")
    summary2 = stats_mod.summarize(str(path))
    assert "model" not in summary2


# --- capture happy path + provenance ----------------------------------------


def test_capture_exact_success_autocaptured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {"ses_abc123": _export("ses_abc123")})
    monkeypatch.delenv("FOUNDRY_OPENCODE_SESSION_ID", raising=False)
    result = capture_mod.capture(
        run_dir=str(run_dir), session_id="ses_abc123", opencode_bin=str(stub), task_id="WS199"
    )
    assert result["status"] == "CAPTURED"
    assert result["sanitized"] is True
    records = [json.loads(line) for line in (run_dir / "metrics.jsonl").read_text().splitlines()]
    assert len(records) == 1
    entry = records[0]
    assert entry["task_id"] == "WS199"
    assert entry["task_class"] == "session-telemetry"
    assert entry["session_id"] == "ses_abc123"
    assert entry["model"] == "opencode-go/muse-spark-1.3-contributor"
    for field in (
        "model", "provider", "model_turns", "tool_calls", "tool_calls_by_tool",
        "tool_errors", "tokens_input", "tokens_cache_read", "cost_usd", "patch_count",
    ):
        assert entry["provenance"][field] == "AUTOCAPTURED", field
    assert entry["provenance"]["task_id"] == "CALLER_SUPPLIED"  # explicit --task-id
    assert "compaction_count" not in entry  # unavailable stays absent
    status = json.loads((run_dir / "telemetry-status.json").read_text())
    assert status["status"] == "CAPTURED"


def test_capture_context_task_id_autocaptured(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "launch-context.json").write_text(json.dumps({"workstream": "CTX-WS"}), encoding="utf-8")
    stub = _stub(tmp_path, {"ses_abc123": _export("ses_abc123")})
    result = capture_mod.capture(run_dir=str(run_dir), session_id="ses_abc123", opencode_bin=str(stub))
    assert result["status"] == "CAPTURED"
    entry = json.loads((run_dir / "metrics.jsonl").read_text().splitlines()[0])
    assert entry["task_id"] == "CTX-WS"
    assert entry["provenance"]["task_id"] == "AUTOCAPTURED"


def test_capture_sanitize_absent_still_captures(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {"ses_abc123": _export("ses_abc123")}, advertise_sanitize=False)
    assert capture_mod.supports_sanitize(str(stub)) is False
    result = capture_mod.capture(run_dir=str(run_dir), session_id="ses_abc123", opencode_bin=str(stub))
    assert result["status"] == "CAPTURED"
    assert result["sanitized"] is False


def test_capture_export_failure_pending(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {}, fail_export_rc=1)
    result = capture_mod.capture(run_dir=str(run_dir), session_id="ses_abc123", opencode_bin=str(stub))
    assert result["status"] == "PENDING"
    assert not (run_dir / "metrics.jsonl").exists()


def test_capture_session_not_found_reason(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {"ses_other": _export("ses_other")})
    result = capture_mod.capture(run_dir=str(run_dir), session_id="ses_missing", opencode_bin=str(stub))
    assert result["status"] == "PENDING"
    assert result["reason"] == "SESSION_NOT_FOUND"
    assert not (run_dir / "metrics.jsonl").exists()


def test_capture_malformed_export_failed(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {}, malformed_sids={"ses_bad"})
    result = capture_mod.capture(run_dir=str(run_dir), session_id="ses_bad", opencode_bin=str(stub))
    assert result["status"] == "FAILED"
    assert result["reason"].startswith("INVALID_EXPORT")


def test_capture_attribution_mismatch_refused(tmp_path: Path) -> None:
    """Stub serves session B when session A was requested: must not append."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {"ses_aaa": _export("ses_bbb")})
    result = capture_mod.capture(run_dir=str(run_dir), session_id="ses_aaa", opencode_bin=str(stub))
    assert result["status"] == "FAILED"
    assert result["reason"] == "ATTRIBUTION_MISMATCH"
    assert not (run_dir / "metrics.jsonl").exists()


def test_capture_malformed_session_id_rejected(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {})
    with pytest.raises(ValueError):
        capture_mod.capture(run_dir=str(run_dir), session_id="  ", opencode_bin=str(stub))
    with pytest.raises(ValueError):
        capture_mod.capture(run_dir=str(run_dir), session_id="../evil", opencode_bin=str(stub))


def test_capture_ownership_mismatch_refused(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a"
    run_a.mkdir()
    (run_a / "launch-context.json").write_text(json.dumps({"workstream": "WS-A"}), encoding="utf-8")
    stub = _stub(tmp_path, {"ses_abc123": _export("ses_abc123")})
    result = capture_mod.capture(
        run_dir=str(run_a), session_id="ses_abc123", opencode_bin=str(stub), task_id="WS-B"
    )
    assert result["status"] == "FAILED"
    assert result["reason"] == "OWNERSHIP_MISMATCH"
    assert not (run_a / "metrics.jsonl").exists()


def test_capture_raw_inside_worktree_refused(tmp_path: Path) -> None:
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
    wt = tmp_path / "wt"
    wt.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=wt, check=True, env=env, capture_output=True)
    (wt / "f").write_text("x\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {"ses_abc123": _export("ses_abc123")})
    result = capture_mod.capture(
        run_dir=str(run_dir),
        session_id="ses_abc123",
        opencode_bin=str(stub),
        raw_path=str(wt / "raw.json"),
        worktree=str(wt),
    )
    assert result["status"] == "FAILED"
    assert result["reason"] == "RAW_INSIDE_WORKTREE"
    assert not (wt / "raw.json").exists()


# --- parallel-session adversarial -------------------------------------------


def test_parallel_run_dirs_cannot_steal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir()
    run_b.mkdir()
    (run_a / "launch-context.json").write_text(json.dumps({"workstream": "WS-A"}), encoding="utf-8")
    (run_b / "launch-context.json").write_text(json.dumps({"workstream": "WS-B"}), encoding="utf-8")
    stub = _stub(
        tmp_path,
        {"ses_aaa": _export("ses_aaa"), "ses_bbb": _export("ses_bbb", tokens={"input": 999})},
    )
    monkeypatch.delenv("FOUNDRY_OPENCODE_SESSION_ID", raising=False)
    ra = capture_mod.capture(run_dir=str(run_a), session_id="ses_aaa", opencode_bin=str(stub))
    rb = capture_mod.capture(run_dir=str(run_b), session_id="ses_bbb", opencode_bin=str(stub))
    assert ra["status"] == "CAPTURED" and rb["status"] == "CAPTURED"
    ea = json.loads((run_a / "metrics.jsonl").read_text().splitlines()[0])
    eb = json.loads((run_b / "metrics.jsonl").read_text().splitlines()[0])
    assert ea["session_id"] == "ses_aaa" and ea["task_id"] == "WS-A"
    assert eb["session_id"] == "ses_bbb" and eb["task_id"] == "WS-B"
    assert eb["tokens_input"] == 999
    assert ea["tokens_input"] != eb["tokens_input"]
    # Raw files are disjoint and LOCAL_ONLY (under each run dir, never worktree).
    assert (run_a / "raw-export-ses_aaa.json").is_file()
    assert (run_b / "raw-export-ses_bbb.json").is_file()
    assert not (run_a / "raw-export-ses_bbb.json").exists()


def test_explicit_id_maps_only_to_that_session(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sid_file = tmp_path / "sids.log"
    stub = _stub(
        tmp_path,
        {"ses_one": _export("ses_one"), "ses_two": _export("ses_two")},
        record_argv=sid_file,
    )
    result = capture_mod.capture(run_dir=str(run_dir), session_id="ses_two", opencode_bin=str(stub))
    assert result["status"] == "CAPTURED"
    entry = json.loads((run_dir / "metrics.jsonl").read_text().splitlines()[0])
    assert entry["session_id"] == "ses_two"


def test_missing_session_never_substitutes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {"ses_real": _export("ses_real")})
    result = capture_mod.capture(run_dir=str(run_dir), session_id="ses_ghost", opencode_bin=str(stub))
    assert result["status"] == "PENDING"
    assert result["reason"] == "SESSION_NOT_FOUND"
    assert not (run_dir / "metrics.jsonl").exists()


def test_session_list_never_consulted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture uses only the exact ID; the stub fails any list invocation."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stub = _stub(tmp_path, {"ses_abc123": _export("ses_abc123")})
    monkeypatch.delenv("FOUNDRY_OPENCODE_SESSION_ID", raising=False)
    result = capture_mod.capture(run_dir=str(run_dir), session_id="ses_abc123", opencode_bin=str(stub))
    assert result["status"] == "CAPTURED"  # succeeded without any list call


def test_read_exact_session_id_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "opencode-session-id").write_text("ses_file\n", encoding="utf-8")
    monkeypatch.setenv("FOUNDRY_OPENCODE_SESSION_ID", "ses_env")
    assert capture_mod.read_exact_session_id(str(run_dir), "ses_explicit") == "ses_explicit"
    assert capture_mod.read_exact_session_id(str(run_dir), None) == "ses_env"
    monkeypatch.delenv("FOUNDRY_OPENCODE_SESSION_ID")
    assert capture_mod.read_exact_session_id(str(run_dir), None) == "ses_file"
    assert capture_mod.read_exact_session_id(str(tmp_path / "norun"), None) is None


def test_latest_ordering_cannot_attribute() -> None:
    """There is deliberately no newest-session helper to misuse."""
    assert not hasattr(capture_mod, "latest_session")
    assert not hasattr(capture_mod, "pick_newest")
    assert not hasattr(capture_mod, "auto_select_session")


# --- privacy / content exclusion --------------------------------------------


def test_privacy_no_session_content_in_metrics_or_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    secret = "sk-live-SECRET-abc123 hunter2 PROMPT: rm -rf /"
    stub = _stub(tmp_path, {"ses_abc123": _export("ses_abc123", secret_text=secret)})
    rc = capture_mod.main(
        ["--run-dir", str(run_dir), "--session-id", "ses_abc123", "--opencode-bin", str(stub)]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
    metrics_blob = (run_dir / "metrics.jsonl").read_text(encoding="utf-8")
    status_blob = (run_dir / "telemetry-status.json").read_text(encoding="utf-8")
    assert secret not in metrics_blob
    assert secret not in status_blob
    entry = json.loads(metrics_blob.splitlines()[0])
    for banned in (
        "prompt", "command", "output", "text", "patch", "reasoning", "input", "files", "env",
    ):
        assert banned not in entry, banned
    allowed = set(capture_mod.EXPORT_TO_METRICS.values()) | {"task_id", "task_class", "recorded_utc", "provenance"}
    assert set(entry) - {"provenance"} <= allowed


def test_metrics_new_identity_fields_round_trip(tmp_path: Path) -> None:
    metrics = tmp_path / "m.jsonl"
    entry = metrics_mod.record(
        str(metrics),
        _provenance={"session_id": "AUTOCAPTURED", "provider": "AUTOCAPTURED"},
        task_id="T",
        session_id="ses_x",
        provider="opencode-go",
        variant="high",
        agent="foundry-implementer",
        cli_version="1.18.30",
    )
    assert entry["session_id"] == "ses_x"
    assert entry["provenance"]["session_id"] == "AUTOCAPTURED"


# --- launcher integration ----------------------------------------------------


def _git(args: list[str], cwd: Path, env: dict | None = None) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False, env=env)
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


def _canon(tmp_path: Path) -> Path:
    import json as _json

    root = tmp_path / "canon"
    (root / ".opencode" / "agents").mkdir(parents=True)
    (root / ".opencode" / "skills").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    (root / ".opencode" / "agents" / "foundry-implementer.md").write_text("---\nvariant: high\n---\n", encoding="utf-8")
    real = _json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
    (root / "opencode.json").write_text(
        _json.dumps(
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


def _target(tmp_path: Path) -> dict:
    import yaml

    locks = tmp_path / "locks"
    locks.mkdir()
    wt = tmp_path / "wt"
    wt.mkdir()
    env = _env()
    _git(["init", "-b", "main"], wt, env)
    _git(["config", "remote.origin.url", "https://github.com/moeendres-png/commander-playtest-lab.git"], wt, env)
    (wt / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    (wt / "code.txt").write_text("x\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "init"], wt, env)
    base = _git(["rev-parse", "HEAD"], wt, env)
    _git(["checkout", "-b", "project/test"], wt, env)
    state = {
        "schema_version": "2.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "worktree": str(wt),
        "branch": "project/test",
        "audit_base_sha": base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": base,
        "validated_head": base,
        "objective": "test objective",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "TEST-WS",
        "status": "ACTIVE",
        "exact_next_action": "go",
    }
    state_path = wt / ".foundry" / "WORKSTREAM_STATE.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    return {"wt": wt, "locks": locks, "env": env, "state": state_path, "base": base}


def _plan(target: dict, canon: Path, stub: Path, **over) -> dict:
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
        "opencode_bin": str(stub),
    }
    kwargs.update(over)
    return launcher_mod.init(**kwargs)


def test_launcher_pending_hint_preserves_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    target = _target(tmp_path)
    canon = _canon(tmp_path)
    child = tmp_path / "child-bin"
    child.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        "if sys.argv[1:] == ['--version']:\n    print('1.18.30')\n    sys.exit(0)\n"
        "sys.exit(5)\n",
        encoding="utf-8",
    )
    child.chmod(0o755)
    plan = _plan(target, canon, child)
    assert plan["verdict"] == "LAUNCH_READY", plan
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    monkeypatch.delenv("FOUNDRY_OPENCODE_SESSION_ID", raising=False)
    rc = launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high")
    assert rc == 5  # child exit preserved despite missing telemetry
    captured = capsys.readouterr()
    assert "TELEMETRY_PENDING" in captured.err
    assert "TELEMETRY_HINT" in captured.err
    assert "session_capture.py --run-dir" in captured.err


def test_launcher_exact_id_captures_and_preserves_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    target = _target(tmp_path)
    canon = _canon(tmp_path)
    combined = tmp_path / "combined-bin"
    export_doc = _export("ses_launch1")
    combined.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"EXPORT = json.loads({json.dumps(export_doc)!r})\n"
        "argv = sys.argv[1:]\n"
        "if argv == ['--version']:\n    print('1.18.30')\n    sys.exit(0)\n"
        "if argv[:1] == ['export'] and argv[-1] == 'ses_launch1':\n"
        "    if '--help' in argv:\n        print('--sanitize')\n        sys.exit(0)\n"
        "    sys.stdout.write(json.dumps(EXPORT))\n    sys.exit(0)\n"
        "if argv[:1] == ['export'] and argv[-1] == '--help':\n"
        "    print('--sanitize')\n    sys.exit(0)\n"
        "if len(argv) >= 2 and argv[0] in ('run', '--auto'):\n    sys.exit(3)\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )
    combined.chmod(0o755)
    plan = _plan(target, canon, combined, opencode_session_id="ses_launch1")
    assert plan["verdict"] == "LAUNCH_READY", plan
    assert plan["opencode_session_id"] == "ses_launch1"
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    monkeypatch.delenv("FOUNDRY_OPENCODE_SESSION_ID", raising=False)
    rc = launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high")
    assert rc == 3
    captured = capsys.readouterr()
    assert "TELEMETRY_CAPTURED" in captured.out
    metrics_file = Path(plan["run_dir"]) / "metrics.jsonl"
    records = [json.loads(line) for line in metrics_file.read_text().splitlines()]
    telemetry = [r for r in records if r.get("task_class") == "session-telemetry"]
    assert len(telemetry) == 1
    assert telemetry[0]["session_id"] == "ses_launch1"
    assert telemetry[0]["provenance"]["session_id"] == "AUTOCAPTURED"


def test_launcher_telemetry_failure_preserves_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    target = _target(tmp_path)
    canon = _canon(tmp_path)
    child = tmp_path / "child-bin"
    child.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        "if sys.argv[1:] == ['--version']:\n    print('1.18.30')\n    sys.exit(0)\n"
        "sys.exit(9)\n",
        encoding="utf-8",
    )
    child.chmod(0o755)
    plan = _plan(target, canon, child, opencode_session_id="ses_missing")
    assert plan["verdict"] == "LAUNCH_READY", plan
    monkeypatch.setenv("FOUNDRY_LOCK_DIR", str(target["locks"]))
    monkeypatch.delenv("FOUNDRY_OPENCODE_SESSION_ID", raising=False)
    real_capture = capture_mod.capture

    def boom(**kwargs):
        raise RuntimeError("telemetry defect")

    monkeypatch.setattr(capture_mod, "capture", boom)
    monkeypatch.setattr(launcher_mod.session_capture_mod, "capture", boom)
    rc = launcher_mod.launch(plan, [], str(target["wt"]), "TEST-WS", "high")
    assert rc == 9
    captured = capsys.readouterr()
    assert "TELEMETRY_PENDING" in captured.err
    monkeypatch.setattr(capture_mod, "capture", real_capture)
    monkeypatch.setattr(launcher_mod.session_capture_mod, "capture", real_capture)


def test_launcher_tui_headless_telemetry_parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _target(tmp_path)
    canon = _canon(tmp_path)
    child = tmp_path / "child-bin"
    child.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        "if sys.argv[1:] == ['--version']:\n    print('1.18.30')\n    sys.exit(0)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    child.chmod(0o755)
    for mode in ("headless", "tui"):
        plan = _plan(target, canon, child, ui_mode=mode)
        assert plan["verdict"] == "LAUNCH_READY", plan
        assert plan["opencode_session_id"] == ""


def test_no_rotation_threshold_introduced() -> None:
    for name in ("session_capture.py", "session_stats.py", "launcher.py", "metrics.py"):
        text = (ROOT / "tools" / "foundry" / name).read_text(encoding="utf-8")
        lowered = text.lower()
        assert "rotate after" not in lowered
        assert "rotation_threshold" not in lowered
        assert "SESSION_ROTATION_THRESHOLD" not in text
        assert "compaction.prune" not in lowered
    capture_text = (ROOT / "tools" / "foundry" / "session_capture.py").read_text(encoding="utf-8")
    for banned in ("subprocess.run([\"kill", "os.kill", "signal.SIG", "--model", "--provider"):
        assert banned not in capture_text, banned


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

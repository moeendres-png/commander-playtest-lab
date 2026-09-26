"""Tests for telemetry provenance (metrics), session export aggregation
(session_stats), safe_push metric emission, and the selective-test mapper
(test_impact). Session fixtures are synthetic export shapes, never real
session content.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(ROOT / "tools"))

from foundry import metrics as metrics_mod  # noqa: E402
from foundry import session_stats as session_stats_mod  # noqa: E402
from foundry import test_impact as test_impact_mod  # noqa: E402


def _git(args: list[str], cwd: Path, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False, env=env
    )
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


def _export_fixture() -> dict:
    return {
        "info": {
            "id": "ses_test",
            "agent": "foundry-implementer",
            "model": {
                "providerID": "opencode-go",
                "id": "muse-spark-1.3-contributor",
                "variant": "xhigh",
            },
            "version": "1.18.30",
            "cost": 0.13,
            "tokens": {
                "input": 100,
                "output": 20,
                "reasoning": 5,
                "cache": {"read": 7, "write": 0},
            },
            "time": {"created": 1789049441000, "updated": 1789049501000},
        },
        "messages": [
            {"info": {}, "parts": [{"type": "step-start", "id": "s1"}]},
            {
                "info": {},
                "parts": [
                    {"type": "tool", "tool": "bash", "state": {"status": "completed"}},
                    {"type": "tool", "tool": "edit", "state": {"status": "completed"}},
                    {"type": "tool", "tool": "bash", "state": {"status": "error"}},
                    {"type": "step-finish", "tokens": {"total": 10}},
                    {"type": "patch", "files": ["a.py"], "hash": "x"},
                ],
            },
        ],
    }


def test_session_stats_counts_only(tmp_path: Path) -> None:
    path = tmp_path / "export.json"
    path.write_text(json.dumps(_export_fixture()), encoding="utf-8")
    summary = session_stats_mod.summarize(str(path))
    assert summary["session_id"] == "ses_test"
    assert summary["agent"] == "foundry-implementer"
    assert summary["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert summary["variant"] == "xhigh"
    assert summary["model_turns"] == 1
    assert summary["tool_calls"] == 3
    assert summary["tool_calls_by_tool"] == {"bash": 2, "edit": 1}
    assert summary["tool_errors"] == 1
    assert summary["patch_count"] == 1
    assert summary["tokens_input"] == 100
    assert summary["tokens_cache_read"] == 7
    assert summary["cost_usd"] == 0.13
    assert summary["elapsed_seconds"] == 60.0
    assert summary["compaction_count"] is None  # unavailable, never inferred
    # No content fields leak into the summary.
    for banned in ("command", "output", "text", "files"):
        assert banned not in summary, banned


def test_session_stats_rejects_garbage(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"nope": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="info/messages"):
        session_stats_mod.summarize(str(path))


def test_session_stats_against_live_export_shape() -> None:
    """The real 1.18.30 export of this session aggregates to sane counts."""
    live = Path("/tmp/opencode/session-shape.json")
    if not live.is_file():
        pytest.skip("no live export snapshot present")
    summary = session_stats_mod.summarize(str(live))
    assert summary["model"] == "opencode-go/muse-spark-1.3-contributor"
    assert summary["model_turns"] > 100
    assert summary["tool_calls"] >= summary["model_turns"]
    assert summary["tokens_input"] > 0
    assert summary["compaction_count"] is None


def test_metrics_provenance_accepted_and_validated(tmp_path: Path) -> None:
    metrics = tmp_path / "m.jsonl"
    entry = metrics_mod.record(
        str(metrics),
        _provenance={"task_id": "AUTOCAPTURED", "tool_calls": "AUTOCAPTURED"},
        task_id="T",
        tool_calls=3,
    )
    assert entry["provenance"] == {"task_id": "AUTOCAPTURED", "tool_calls": "AUTOCAPTURED"}
    with pytest.raises(ValueError, match="bad provenance"):
        metrics_mod.record(str(metrics), _provenance={"task_id": "GUESSED"}, task_id="T")
    with pytest.raises(ValueError, match="unknown metric fields"):
        metrics_mod.record(str(metrics), no_such_field=1)
    with pytest.raises(ValueError, match="unknown field"):
        metrics_mod.record(str(metrics), _provenance={"nope": "UNKNOWN"})


def test_metrics_new_fields_round_trip(tmp_path: Path) -> None:
    metrics = tmp_path / "m.jsonl"
    entry = metrics_mod.record(
        str(metrics),
        repo_profile="mage",
        model="opencode-go/muse-spark-1.3-contributor",
        started_utc="2026-09-10T00:00:00Z",
        ended_utc="2026-09-10T01:00:00Z",
        exit_status=0,
        push_result="PUSHED",
        model_turns=12,
        tool_errors=1,
        cost_usd=0.5,
    )
    assert entry["repo_profile"] == "mage"
    assert entry["push_result"] == "PUSHED"
    assert entry["exit_status"] == 0


def test_safe_push_emits_metrics(tmp_path: Path) -> None:
    import os

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
    remote = tmp_path / "slug-here" / "r.git"
    remote.parent.mkdir(parents=True)
    _git(["init", "--bare", "-b", "main", str(remote)], tmp_path, env)
    wt = tmp_path / "wt"
    _git(["clone", str(remote), str(wt)], tmp_path, env)
    (wt / "f").write_text("x\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "i"], wt, env)
    _git(["push", "origin", "HEAD:refs/heads/main"], wt, env)
    _git(["checkout", "-b", "project/m"], wt, env)
    (wt / "g").write_text("y\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "w"], wt, env)
    head = _git(["rev-parse", "HEAD"], wt, env)
    base = _git(["rev-parse", "origin/main"], wt, env)
    state = {
        "schema_version": "2.0",
        "repository": "r",
        "worktree": str(wt),
        "branch": "project/m",
        "audit_base_sha": base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": head,
        "validated_head": head,
        "objective": "o",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "METRICS-WS",
        "status": "ACTIVE",
        "exact_next_action": "x",
    }
    state_path = wt / "S.yaml"
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "s"], wt, env)
    metrics = tmp_path / "m.jsonl"
    locks = tmp_path / "locks"
    locks.mkdir()
    lock_env = dict(env)
    lock_env["FOUNDRY_LOCK_DIR"] = str(locks)
    lock_env["PYTHONPATH"] = str(ROOT / "tools")
    driver = (
        "import subprocess, sys; "
        "from foundry import writer_lock; "
        "lock = writer_lock.WriterLock(sys.argv[1], 'METRICS-WS', 'project/m', 's'); "
        "lock.acquire(); "
        f"p = subprocess.run([sys.executable, {str(ROOT / 'tools' / 'foundry' / 'safe_push.py')!r}, "
        "'--worktree', sys.argv[1], '--expected-branch', 'project/m', "
        "'--state', sys.argv[2], '--expected-slug', 'slug-here', "
        "'--dry-run', '--metrics', sys.argv[3]], capture_output=True, text=True); "
        "sys.stdout.write(p.stdout); sys.stderr.write(p.stderr); "
        "lock.release(); sys.exit(p.returncode)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", driver, str(wt), str(state_path), str(metrics)],
        capture_output=True,
        text=True,
        timeout=60,
        env=lock_env,
    )
    assert proc.returncode == 0, proc.stderr
    records = [json.loads(line) for line in metrics.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["task_id"] == "METRICS-WS"
    assert records[0]["push_result"] == "DRY_RUN_OK"
    assert records[0]["provenance"]["push_result"] == "AUTOCAPTURED"


def test_impact_mapper_rules(tmp_path: Path) -> None:
    plan = test_impact_mod.plan(
        ["tools/foundry/writer_lock.py", "docs/notes.md", "src/new/engine.py"]
    )
    assert "pytest tests/foundry/test_writer_lock.py -q" in plan["minimum"]
    assert plan["reasons"]["docs/notes.md"] == "prose only (no test surface)"
    assert "docs/notes.md" not in str(plan["minimum"])
    assert plan["requalification_required"] is True
    assert "pytest tests/ -q" in plan["minimum"]
    assert "Contract-required" in plan["contract_override"]


def test_impact_opencode_json_requires_manual_battery() -> None:
    plan = test_impact_mod.plan(["opencode.json"])
    assert any("battery" in step for step in plan["manual"])
    assert "pytest tests/foundry/ -q" in plan["minimum"]


def test_impact_unknown_base_errors(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    _git(["init", "-b", "main"], wt)
    with pytest.raises(ValueError, match="cannot diff"):
        test_impact_mod.changed_files(str(wt), "deadbeef" * 5)


def test_redact_url_shapes() -> None:
    from foundry import safe_push as safe_push_mod

    assert (
        safe_push_mod._redact_url("https://user:s3cret@github.com/o/r.git")
        == "https://<redacted>@github.com/o/r.git"
    )
    assert (
        safe_push_mod._redact_url("https://token123@github.com/o/r.git")
        == "https://<redacted>@github.com/o/r.git"
    )
    plain = "https://github.com/o/r.git"
    assert safe_push_mod._redact_url(plain) == plain
    assert safe_push_mod._redact_url("/tmp/local/path.git") == "/tmp/local/path.git"


def test_push_reject_redacts_credentialed_remote(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A credential-bearing remote URL must never surface raw in diagnostics."""
    import os

    from foundry import safe_push as safe_push_mod

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
    _git(["init", "-b", "main"], wt, env)
    _git(
        ["config", "remote.origin.url", "https://user:s3cret-token@github.com/other/repo.git"],
        wt,
        env,
    )
    (wt / "f").write_text("x\n", encoding="utf-8")
    _git(["add", "."], wt, env)
    _git(["commit", "-m", "i"], wt, env)
    head = _git(["rev-parse", "HEAD"], wt, env)
    state = {
        "schema_version": "2.0",
        "repository": "r",
        "worktree": str(wt),
        "branch": "main",
        "audit_base_sha": head,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": head,
        "validated_head": head,
        "objective": "o",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "REDAC-WS",
        "status": "ACTIVE",
        "exact_next_action": "x",
    }
    state_path = wt / "S.yaml"
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    rc = safe_push_mod.safe_push(str(wt), "project/x", str(state_path), "origin", "no-such-slug")
    assert rc == 2
    captured = capsys.readouterr()
    assert "s3cret-token" not in captured.err
    assert "<redacted>@" in captured.err


def test_session_stats_ignores_secret_shaped_content(tmp_path: Path) -> None:
    export = _export_fixture()
    export["messages"][1]["parts"].append(
        {
            "type": "tool",
            "tool": "bash",
            "state": {"status": "completed", "output": "sk-live-abc123 token=hunter2"},
        }
    )
    path = tmp_path / "export.json"
    path.write_text(json.dumps(export), encoding="utf-8")
    summary = session_stats_mod.summarize(str(path))
    blob = json.dumps(summary)
    assert "sk-live-abc123" not in blob
    assert "hunter2" not in blob
    assert summary["tool_calls"] == 4


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

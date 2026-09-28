"""Corrupt exports must not become authoritative zero-valued metrics."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from foundry import session_stats as stats


def export():
    return {
        "info": {"id": "ses_fixture", "tokens": {"input": 7}, "cost": 0.2},
        "messages": [
            {"parts": [{"type": "tool", "tool": "bash", "state": {"status": "completed"}}]}
        ],
    }


def save(tmp_path, data):
    path = tmp_path / "export.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    "messages", [[None], [{}], [{"parts": "private sentinel"}], [{"parts": [None]}]]
)
def test_invalid_messages_not_zero_counts(tmp_path, messages):
    data = export()
    data["messages"] = messages
    with pytest.raises(ValueError):
        stats.summarize(save(tmp_path, data))


@pytest.mark.parametrize("number", [True, -1, 0.5, float("nan"), float("inf")])
def test_invalid_token_totals(tmp_path, number):
    data = export()
    data["info"]["tokens"]["input"] = number
    with pytest.raises(ValueError):
        stats.summarize(save(tmp_path, data))


def test_valid_export(tmp_path):
    result = stats.summarize(save(tmp_path, export()))
    assert result["tool_calls"] == 1
    assert result["tool_errors"] == 0
    assert result["tokens_input"] == 7
    assert result["compaction_count"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("cost", -0.01),
        ("cost", True),
        ("cost", "0.1"),
        ("model", []),
        ("agent", {"text": "PRIVATE_SENTINEL"}),
        ("tokens", []),
        ("tokens", {"cache": []}),
        ("time", {"created": 2000, "updated": 1000}),
        ("time", {"created": 10**300}),
        ("time", {"updated": True}),
    ],
)
def test_invalid_optional_measurements_rejected(tmp_path, field, value):
    data = export()
    data["info"][field] = value
    with pytest.raises(ValueError) as error:
        stats.summarize(save(tmp_path, data))
    assert "PRIVATE_SENTINEL" not in str(error.value)


@pytest.mark.parametrize(
    "part",
    [
        {},
        {"type": {}},
        {"type": "tool"},
        {"type": "tool", "tool": {"secret": "PRIVATE_SENTINEL"}},
        {"type": "tool", "tool": "bash", "state": None},
        {"type": "tool", "tool": "bash", "state": {"status": "unknown"}},
    ],
)
def test_incomplete_tool_is_not_success(tmp_path, part):
    data = export()
    data["messages"][0]["parts"] = [part]
    with pytest.raises(ValueError):
        stats.summarize(save(tmp_path, data))


@pytest.mark.parametrize(
    "raw",
    [
        b'{"PRIVATE_SENTINEL": "unterminated',
        b'{"info":{},"info":{"id":"PRIVATE_SENTINEL"},"messages":[]}',
        b"PRIVATE_SENTINEL\xff",
        b"[" * 2000,
    ],
)
def test_cli_invalid_input_never_publishes_or_exposes_content(tmp_path, capsys, raw):
    source = tmp_path / "private-input.json"
    source.write_bytes(raw)
    output = tmp_path / "summary.json"
    output.write_text("old summary")
    assert stats.main(["--export", str(source), "--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "SESSION_STATS_INVALID" in captured.err
    assert "PRIVATE_SENTINEL" not in captured.err
    assert output.read_text() == "old summary"


def test_unknown_metrics_not_estimated_from_private_step_content(tmp_path):
    data = export()
    data["info"] = {"id": "ses_fixture"}
    data["messages"][0]["parts"] += [
        {"type": "text", "text": "PRIVATE_SENTINEL"},
        {"type": "step-finish", "tokens": {"input": 100}, "cost": 999},
        {"type": "patch", "files": ["PRIVATE_SENTINEL"]},
        {"type": "step-start"},
    ]
    result = stats.summarize(save(tmp_path, data))
    assert "tokens_input" not in result and "cost_usd" not in result
    assert "PRIVATE_SENTINEL" not in json.dumps(result)
    assert result["patch_count"] == result["model_turns"] == 1


@pytest.mark.parametrize(
    "status,error_count", [("pending", 0), ("running", 0), ("completed", 0), ("error", 1)]
)
def test_known_statuses_preserved(tmp_path, status, error_count):
    data = export()
    data["messages"][0]["parts"][0]["state"] = {"status": status, "error": "PRIVATE_SENTINEL"}
    result = stats.summarize(save(tmp_path, data))
    assert result["tool_errors"] == error_count
    assert "PRIVATE_SENTINEL" not in json.dumps(result)


def test_output_cannot_destroy_raw_export(tmp_path, capsys):
    source = save(tmp_path, export())
    before = Path(source).read_bytes()
    assert stats.main(["--export", source, "--output", source]) == 1
    assert Path(source).read_bytes() == before
    assert "SESSION_STATS_INVALID" in capsys.readouterr().err


def test_output_io_failure_is_structured(tmp_path, capsys):
    source = save(tmp_path, export())
    assert stats.main(["--export", source, "--output", str(tmp_path / "absent/out.json")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "SESSION_STATS_INVALID" in captured.err


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_output_aliases_do_not_mutate_input(tmp_path, capsys, kind):
    source = Path(save(tmp_path, export()))
    output = tmp_path / "alias.json"
    try:
        if kind == "symlink":
            output.symlink_to(source)
        else:
            os.link(source, output)
    except OSError:
        pytest.skip("link creation unavailable")
    before = source.read_bytes()
    assert stats.main(["--export", str(source), "--output", str(output)]) == 1
    assert source.read_bytes() == before
    assert "aliases" in capsys.readouterr().err


def test_failed_replace_preserves_previous_output(tmp_path, monkeypatch, capsys):
    source = save(tmp_path, export())
    output = tmp_path / "summary.json"
    output.write_text("previous summary")

    def fail(*args):
        raise OSError("PRIVATE_SENTINEL")

    monkeypatch.setattr(stats.os, "replace", fail)
    assert stats.main(["--export", source, "--output", str(output)]) == 1
    assert output.read_text() == "previous summary"
    assert not list(tmp_path.glob(".session-stats-*"))
    assert "PRIVATE_SENTINEL" not in capsys.readouterr().err


def test_atomic_output_and_missing_metrics(tmp_path, capsys):
    data = export()
    data["info"] = {"id": "ses_fixture", "time": {"created": 1000, "updated": 2600}}
    source = save(tmp_path, data)
    output = tmp_path / "summary.json"
    assert stats.main(["--export", source, "--output", str(output)]) == 0
    summary = json.loads(output.read_text())
    assert summary["elapsed_seconds"] == 1.6
    assert "tokens_input" not in summary
    assert "cost_usd" not in summary
    assert not list(tmp_path.glob(".session-stats-*"))
    assert capsys.readouterr().out == ""

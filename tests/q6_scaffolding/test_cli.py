"""Tests: CLI operability and fail-closed behavior."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from q6_scaffolding import cli

from .support import FIXTURES, INPUTS_SPEC, REPO_ROOT, run_pipeline


def _out(tmp_path, name="o.json"):
    return str(tmp_path / name)


def test_cli_intake_missing_source_lock_fails_closed(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "inputs": [
                    {
                        "path": str(FIXTURES / "cards" / "divination.txt"),
                        "source_corpus": "forge-card-scripts",
                        "source_repository": "https://github.com/Card-Forge/forge.git",
                        "source_path": "x",
                    }
                ]
            }
        )
    )
    assert cli.main(["intake", "--inputs", str(spec), "--out", _out(tmp_path)]) == 2
    assert not (tmp_path / "o.json").exists()


def test_cli_intake_hash_mismatch_fails_closed(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "inputs": [
                    {
                        "path": str(FIXTURES / "cards" / "divination.txt"),
                        "source_corpus": "c",
                        "source_repository": "r",
                        "source_commit": "ab" * 20,
                        "source_path": "p",
                        "expected_hash": "00" * 32,
                    }
                ]
            }
        )
    )
    assert cli.main(["intake", "--inputs", str(spec), "--out", _out(tmp_path)]) == 2


def test_cli_intake_duplicate_identity_fails_closed(tmp_path):
    first = json.loads(INPUTS_SPEC.read_text())
    entry = dict(first["inputs"][0])
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"inputs": [entry, entry]}))
    assert (
        cli.main(
            [
                "intake",
                "--inputs",
                str(spec),
                "--corpus-root",
                str(REPO_ROOT),
                "--out",
                _out(tmp_path),
            ]
        )
        == 2
    )


def test_cli_intake_rejects_malformed_spec(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text('{"inputs": [{"path": "x"}]}')
    assert cli.main(["intake", "--inputs", str(spec), "--out", _out(tmp_path)]) == 2
    spec.write_text("not json")
    assert cli.main(["intake", "--inputs", str(spec), "--out", _out(tmp_path)]) == 2


def test_cli_stage_order_enforced(tmp_path):
    out = run_pipeline(tmp_path)
    intake_p = tmp_path / "intake.json"
    assert cli.main(["generate-skeletons", "--in", str(intake_p), "--out", _out(tmp_path)]) == 2
    _ = out


def test_cli_validate_rejects_unknown_state(tmp_path):
    out = run_pipeline(tmp_path)
    manifest = dict(out["manifest"])
    manifest["records"] = [dict(r) for r in manifest["records"]]
    manifest["records"][0] = dict(manifest["records"][0])
    manifest["records"][0]["state"] = "BEHAVIOR_PASS"
    bad_p = tmp_path / "bad_manifest.json"
    bad_p.write_text(json.dumps(manifest))
    assert cli.main(["validate", "--manifest", str(bad_p)]) == 2


def test_cli_machine_readable_summaries_are_json(tmp_path, capsys):
    out_path = _out(tmp_path, "intake.json")
    code = cli.main(
        [
            "intake",
            "--inputs",
            str(INPUTS_SPEC),
            "--corpus-root",
            str(REPO_ROOT),
            "--out",
            out_path,
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert summary["command"] == "intake"
    assert summary["records"] == 55

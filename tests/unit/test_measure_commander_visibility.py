"""Tests for commander visibility and counterfactual tax measurement (#1040)."""

from __future__ import annotations

import copy
import gzip
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "measure_commander_visibility.py"
spec = importlib.util.spec_from_file_location("measure_commander_visibility_under_test", SCRIPT)
assert spec and spec.loader
measurer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurer)

measure = measurer.measure
FIXTURE = ROOT / "tests" / "fixtures" / "pilot_real_requests" / "real_pod_v1.jsonl.gz"


def _write_gz_dump(path: Path, header: dict[str, object], rows: list[dict[str, object]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _find_priority_row_with_cz_option(rows: list[dict[str, object]]) -> dict[str, object]:
    for r in rows:
        req = r.get("request", {})
        if not isinstance(req, dict) or req.get("decision_class") != "priority":
            continue
        ps = req.get("pilot_state", {})
        if not isinstance(ps, dict):
            continue
        actor_id = ps.get("actor_id")
        actor: dict[str, object] | None = None
        players = ps.get("players", [])
        if isinstance(players, list):
            for p in players:
                if isinstance(p, dict) and (
                    p.get("is_actor") or str(p.get("player_id")) == str(actor_id)
                ):
                    actor = p
                    break
        cmd = actor.get("command", []) if isinstance(actor, dict) else []
        cmd_ids = {
            str(item.get("object_id"))
            for item in cmd
            if isinstance(item, dict) and item.get("object_id")
        }
        legal_opts = req.get("legal_options", [])
        if isinstance(legal_opts, list):
            for opt in legal_opts:
                if isinstance(opt, dict):
                    meta = opt.get("metadata")
                    meta_dict = meta if isinstance(meta, dict) else {}
                    if str(meta_dict.get("source_object_id")) in cmd_ids:
                        return r
    raise AssertionError("No priority row with command zone option found")


def test_measure_real_pod_v1_fixture() -> None:
    """Verifies exact counted baseline metrics on the real_pod_v1 fixture.

    The numbers are those of the fixture as re-recorded with the hand-value discard (#1071). The
    sample holds no taxed commander cast any more; the taxed path is covered by the synthetic
    test below.
    """
    results = measure([FIXTURE])

    assert results["requests_total"] == 446
    assert results["priority_requests"] == 80
    assert results["requests_with_own_commander_damage"] == 88
    assert results["requests_with_commander_damage_ge_14"] == 152
    assert results["commander_zone_cast_options"] == 3
    assert results["commander_zone_cast_options_taxed"] == 0
    assert results["requests_with_taxed_commander_option"] == 0
    assert results["answers_changed_by_tax"] == 0
    assert results["answers_changed_without_taxed_option"] == 0

    evidence = results["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["source"] == ["real_pod_v1.jsonl.gz"]
    assert evidence["seeds"] == [1, 2]
    assert "DIRECTLY_VERIFIED" in str(evidence["classification"])


def test_measure_synthetic_mini_request_and_determinism(tmp_path: Path) -> None:
    """A synthetic priority request with casts_from_command=3 increments taxed count and is deterministic."""
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as handle:
        header_raw = json.loads(handle.readline())
        assert isinstance(header_raw, dict)
        header: dict[str, object] = header_raw
        rows = [json.loads(line) for line in handle]

    target_row = _find_priority_row_with_cz_option(rows)

    synth_row = copy.deepcopy(target_row)
    synth_req = synth_row["request"]
    assert isinstance(synth_req, dict)
    synth_ps = synth_req["pilot_state"]
    assert isinstance(synth_ps, dict)
    actor_id = synth_ps["actor_id"]

    cmd_status = synth_ps.get("commander_status", [])
    assert isinstance(cmd_status, list)
    for entry in cmd_status:
        if isinstance(entry, dict) and str(entry.get("owner_id")) == str(actor_id):
            entry["casts_from_command"] = 3

    dump_path = tmp_path / "synthetic_dump.jsonl.gz"
    _write_gz_dump(dump_path, header, [synth_row])

    first = measure([dump_path])
    second = measure([dump_path])

    assert first == second, "measure() must be strictly deterministic"
    assert first["requests_total"] == 1
    assert first["priority_requests"] == 1
    assert int(first["commander_zone_cast_options"]) >= 1
    assert int(first["commander_zone_cast_options_taxed"]) >= 1
    assert first["requests_with_taxed_commander_option"] == 1
    assert first["answers_changed_without_taxed_option"] == 0


def test_principal_scoping_opponent_casts_do_not_tax_own_commander(tmp_path: Path) -> None:
    """Negative control: an opponent's commander cast count must not tax the actor's commander."""
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as handle:
        header_raw = json.loads(handle.readline())
        assert isinstance(header_raw, dict)
        header: dict[str, object] = header_raw
        rows = [json.loads(line) for line in handle]

    target_row = _find_priority_row_with_cz_option(rows)

    modified_row = copy.deepcopy(target_row)
    req = modified_row["request"]
    assert isinstance(req, dict)
    ps = req["pilot_state"]
    assert isinstance(ps, dict)
    actor_id = ps["actor_id"]

    for entry in ps.get("commander_status", []):
        if isinstance(entry, dict) and str(entry.get("owner_id")) == str(actor_id):
            entry["casts_from_command"] = 0

    ps["commander_status"].append(
        {
            "owner_id": "opponent-scoping-id",
            "name": "Ishai, Ojutai Dragonspeaker",
            "casts_from_command": 5,
            "commander_damage_to_player": [],
        }
    )

    dump_path = tmp_path / "opponent_scoping_dump.jsonl.gz"
    _write_gz_dump(dump_path, header, [modified_row])

    results = measure([dump_path])

    assert int(results["commander_zone_cast_options"]) >= 1
    assert results["commander_zone_cast_options_taxed"] == 0, (
        "Opponent casts must not tax own commander (principal scoping)"
    )
    assert results["requests_with_taxed_commander_option"] == 0
    assert results["answers_changed_without_taxed_option"] == 0


def test_cli_execution_with_json_output(tmp_path: Path) -> None:
    """CLI execution must print metrics, write valid JSON when requested, and exit 0."""
    json_out = tmp_path / "out.json"
    cmd = [
        sys.executable,
        str(SCRIPT),
        str(FIXTURE),
        "--json",
        str(json_out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"CLI exited with {proc.returncode}: {proc.stderr}"
    assert "requests_total: 446" in proc.stdout
    assert "answers_changed_without_taxed_option: 0" in proc.stdout

    assert json_out.is_file()
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["requests_total"] == 446
    assert payload["answers_changed_by_tax"] == 0

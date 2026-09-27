from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from commander_lab.meta_qualification import run_meta_verification


def test_real_xmage_replay_mutations_are_killed_and_not_run_is_visible(
    repo_root: Path,
) -> None:
    tape_path = repo_root / "qualification/ws218-semantic-replay-tape-v1/tapes/ws218-tape-4p.json"
    tape = json.loads(tape_path.read_text())
    report = run_meta_verification(tape, source_tape=str(tape_path.relative_to(repo_root)))

    assert report["attempted"] == 7
    assert report["killed"] == 7
    assert report["survived"] == 0
    assert report["not_run"] == 1
    assert report["kill_rate"] == 1.0
    assert report["catalog_coverage"] == 7 / 8

    by_id = {row["mutation_id"]: row for row in report["results"]}
    assert by_id["MQ-HIDDEN-001"]["status"] == "NOT_RUN"
    assert by_id["MQ-HIDDEN-001"]["observed_detector"] is None
    assert all(by_id[mid]["status"] == "KILLED" for mid in by_id if mid != "MQ-HIDDEN-001")


def test_meta_verification_report_validates_against_schema(repo_root: Path) -> None:
    tape_path = repo_root / "qualification/ws218-semantic-replay-tape-v1/tapes/ws218-tape-4p.json"
    tape = json.loads(tape_path.read_text())
    report = run_meta_verification(tape, source_tape=str(tape_path.relative_to(repo_root)))
    schema_path = (
        repo_root
        / "qualification/protocol/meta_verification_v1/meta_verification_result_v1.schema.json"
    )
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)


def test_catalog_and_runner_denominators_match(repo_root: Path) -> None:
    catalog_path = (
        repo_root / "qualification/protocol/meta_verification_v1/rules_mutation_catalog_v1.json"
    )
    catalog = json.loads(catalog_path.read_text())
    ids = [row["id"] for row in catalog["mutations"]]
    assert len(ids) == len(set(ids)) == 8
    assert ids == [
        "MQ-LEGAL-001",
        "MQ-DECISION-001",
        "MQ-RNG-001",
        "MQ-EVENT-001",
        "MQ-OBS-001",
        "MQ-STATE-001",
        "MQ-TERMINAL-001",
        "MQ-HIDDEN-001",
    ]

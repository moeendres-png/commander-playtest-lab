from __future__ import annotations

from pathlib import Path

from commander_lab.qualification.current_boundary import pb03_runtime as R
from commander_lab.qualification.current_boundary.dimension_admission import (
    PB03_FIXTURE_IDS,
)


def _report(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "TEST-org.commanderlab.xmage.Example.xml"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<testsuite tests="1" failures="0" errors="0" skipped="0">\n' + body + "\n</testsuite>\n",
        encoding="utf-8",
    )
    return path


def test_runtime_ledger_covers_exact_pb03_denominator() -> None:
    assert set(R.PB03_RUNTIME_CASES) == set(PB03_FIXTURE_IDS)
    assert len(R.PB03_RUNTIME_CASES) == 30


def test_runtime_ledger_contains_all_seven_former_gaps() -> None:
    gaps = {
        "PILOT_DECLARE_ATTACKER",
        "PILOT_DECLARE_BLOCKER",
        "WS05-MP-ELIM-CONTROL-3",
        "WS05-MP-ELIM-PRIO-3",
        "WS05-MP-ELIM-STACK-3",
        "WS05-MP-ELIM-TURN-3",
        "WS05-MP-TURN-3",
    }
    assert gaps <= set(R.PB03_RUNTIME_CASES)


def test_parser_only_temporal_test_is_never_runtime_credit() -> None:
    identities = {case["method_name"] for case in R.PB03_RUNTIME_CASES.values()}
    assert "parserAcceptsOnlyQualifiedFrozenTemporalTargets" not in identities


def test_blocked_admission_rows_can_have_genuine_runtime_routes() -> None:
    for fixture_id in (
        "MICRO_RULES_RANDOMNESS",
        "WS05-MP-PRIO-3",
        "WS05-MP-TRIG-3",
        "WS05-MP-TURN-5",
        "WS05-MP-ELIM-STACK-3",
        "WS05-CMD-ZONE-GY-YES",
        "WS05-CMD-ZONE-LIB-YES",
    ):
        assert fixture_id in R.PB03_RUNTIME_CASES
        assert R.PB03_RUNTIME_CASES[fixture_id]["route"] in {
            R.GENUINE_CAUSAL_DEVIATION,
            R.TEMPORAL_PROGRESSION,
        }


def test_pilot_fixture_ids_are_not_lost_by_ws05_only_matching() -> None:
    assert R.PB03_RUNTIME_CASES["PILOT_DECLARE_ATTACKER"]["class_name"] == (
        "XmagePb03RuntimeGapClosureTest"
    )
    assert R.PB03_RUNTIME_CASES["PILOT_DECLARE_BLOCKER"]["class_name"] == (
        "XmagePb03RuntimeGapClosureTest"
    )


def test_exact_green_junit_case_counts_as_executed(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        '<testcase classname="org.commanderlab.xmage.Example" name="doesThing" time="0.01" />',
    )
    assert R._case_passed(report, "Example", "doesThing") is True


def test_failed_junit_case_does_not_count(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        '<testcase classname="org.commanderlab.xmage.Example" '
        'name="doesThing"><failure message="boom"/></testcase>',
    )
    assert R._case_passed(report, "Example", "doesThing") is False


def test_skipped_junit_case_does_not_count(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        '<testcase classname="org.commanderlab.xmage.Example" '
        'name="doesThing"><skipped/></testcase>',
    )
    assert R._case_passed(report, "Example", "doesThing") is False


def test_wrong_method_or_class_does_not_count(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        '<testcase classname="org.commanderlab.xmage.Other" name="different" time="0.01" />',
    )
    assert R._case_passed(report, "Example", "doesThing") is False


def test_missing_or_malformed_report_does_not_count(tmp_path: Path) -> None:
    assert R._case_passed(tmp_path / "missing.xml", "Example", "doesThing") is False
    malformed = tmp_path / "broken.xml"
    malformed.write_text("<testsuite><testcase", encoding="utf-8")
    assert R._case_passed(malformed, "Example", "doesThing") is False


# --- runtime ledger freshness (runner + engine + loaded artifact) ---------- #


def _ledger(**overrides: object) -> dict:
    from commander_lab.qualification.current_boundary import receipts as receipt_mod

    body: dict = {
        "schema_version": "commander-lab.pb03-runtime-execution/2.0.0",
        "classification": "PASS",
        "rows_total": len(PB03_FIXTURE_IDS),
        "executed_pass": len(PB03_FIXTURE_IDS),
        "not_run_or_failed": 0,
        "rows": [
            {"fixture_id": fixture_id, "runtime_execution": "PASS"}
            for fixture_id in PB03_FIXTURE_IDS
        ],
        "runner_commit": "a" * 40,
        "runner_tree": "b" * 40,
        "runner_digest": "c" * 64,
        "candidate_commit": "d" * 40,
        "engine_artifact_kind": "file",
        "engine_artifact_sha256": "e" * 64,
    }
    body.update(overrides)
    body["receipt_digest"] = receipt_mod.document_digest(body)
    return body


_EXPECTED = {
    "expected_runner_digest": "c" * 64,
    "expected_candidate_commit": "d" * 40,
    "expected_engine_artifact_sha256": "e" * 64,
}


def test_matching_runner_engine_and_artifact_is_fresh() -> None:
    assert R.runtime_execution_freshness(_ledger(), **_EXPECTED) == R.PB03_RUNTIME_FRESH


def test_a_different_engine_artifact_is_stale() -> None:
    ledger = _ledger(engine_artifact_sha256="f" * 64)
    assert R.runtime_execution_freshness(ledger, **_EXPECTED) == R.PB03_RUNTIME_STALE


def test_a_missing_engine_artifact_is_missing() -> None:
    ledger = _ledger(engine_artifact_sha256="")
    assert R.runtime_execution_freshness(ledger, **_EXPECTED) == R.PB03_RUNTIME_MISSING
    without_kind = _ledger(engine_artifact_kind="")
    assert R.runtime_execution_freshness(without_kind, **_EXPECTED) == R.PB03_RUNTIME_MISSING


def test_a_malformed_or_directory_artifact_is_invalid() -> None:
    malformed = _ledger(engine_artifact_sha256="not-a-digest")
    assert R.runtime_execution_freshness(malformed, **_EXPECTED) == R.PB03_RUNTIME_INVALID
    directory = _ledger(engine_artifact_kind="directory", engine_artifact_sha256=None)
    assert R.runtime_execution_freshness(directory, **_EXPECTED) == R.PB03_RUNTIME_INVALID


def test_an_unavailable_expected_artifact_is_never_fresh() -> None:
    ledger = _ledger()
    expectations = dict(_EXPECTED)
    expectations["expected_engine_artifact_sha256"] = ""
    assert R.runtime_execution_freshness(ledger, **expectations) == R.PB03_RUNTIME_MISSING


def test_runner_or_candidate_drift_is_stale() -> None:
    assert (
        R.runtime_execution_freshness(
            _ledger(), **{**_EXPECTED, "expected_runner_digest": "9" * 64}
        )
        == R.PB03_RUNTIME_STALE
    )
    assert (
        R.runtime_execution_freshness(
            _ledger(), **{**_EXPECTED, "expected_candidate_commit": "9" * 40}
        )
        == R.PB03_RUNTIME_STALE
    )


def test_a_non_all_green_or_tampered_ledger_is_invalid() -> None:
    partial = _ledger(
        classification="PARTIAL",
        executed_pass=len(PB03_FIXTURE_IDS) - 1,
        not_run_or_failed=1,
    )
    assert R.runtime_execution_freshness(partial, **_EXPECTED) == R.PB03_RUNTIME_INVALID
    tampered = _ledger()
    tampered["candidate_commit"] = "9" * 40
    assert R.runtime_execution_freshness(tampered, **_EXPECTED) == R.PB03_RUNTIME_INVALID
    without_digest = _ledger()
    del without_digest["receipt_digest"]
    assert R.runtime_execution_freshness(without_digest, **_EXPECTED) == R.PB03_RUNTIME_MISSING

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

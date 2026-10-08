"""#479 E2: the serial-vs-shadow packet comparator is sensitive and noise-free.

The comparator exists to answer one question: did the shadow overlap change any
semantic outcome? These tests pin that it detects the outcomes that matter (an
AF gate verdict, a FULL107 count and row state, a native-suite failure count, a
native-suite return code, an unexecuted class) and ignores the run noise that
legitimately differs (timestamps, receipt digests, run ids).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "compare_pb03_shadow.py"


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("pb03_shadow_compare", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_packet(
    root: Path,
    *,
    af04_verdict: str = "PASS",
    pass_count: int = 102,
    row_b_state: str = "UNKNOWN",
    forge_direct_failed: int = 0,
    forge_direct_returncode: int = 0,
    forge_direct_unexecuted: list[str] | None = None,
    stamp: str = "2026-01-01T00:00:00+00:00",
    run_id: str = "111111",
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for candidate in ("xmage", "forge"):
        (root / f"AF00_AF11_{candidate.upper()}.json").write_text(
            json.dumps(
                {
                    "candidate": candidate,
                    "run_id": run_id,
                    "gates": [
                        {
                            "gate": f"AF{i:02d}",
                            "verdict": af04_verdict if i == 4 else "PASS",
                            "blocking_rows": ["ROW_B"] if i == 4 and af04_verdict != "PASS" else [],
                        }
                        for i in range(12)
                    ],
                }
            ),
            encoding="utf-8",
        )
        rows = [
            {"fixture_id": "ROW_A", "exit_state": "PASS"},
            {"fixture_id": "ROW_B", "exit_state": row_b_state},
            *[
                {
                    "fixture_id": f"ROW_EXTRA_{i:03d}",
                    "exit_state": "PASS" if i < pass_count - 1 else "UNKNOWN",
                }
                for i in range(105)
            ],
        ]
        (root / f"FULL107_{candidate.upper()}_RESULTS.json").write_text(
            json.dumps(
                {
                    "candidate": candidate,
                    "run_id": run_id,
                    "total": 107,
                    "counts": dict(Counter(row["exit_state"] for row in rows)),
                    "rows": rows,
                }
            ),
            encoding="utf-8",
        )
    receipts = root / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    for candidate in ("xmage", "forge"):
        for group in ("direct", "mechanism"):
            is_forge_direct = (candidate, group) == ("forge", "direct")
            (receipts / f"native-{candidate}-{group}.json").write_text(
                json.dumps(
                    {
                        "candidate": candidate,
                        "group": group,
                        "tests": 10,
                        "failed": forge_direct_failed if is_forge_direct else 0,
                        "errors": 0,
                        "skipped": 0,
                        "returncode": forge_direct_returncode if is_forge_direct else 0,
                        "unexecuted_classes": (
                            [
                                *list(forge_direct_unexecuted or ()),
                                *(["ExampleTest"] if forge_direct_failed else []),
                            ]
                            if is_forge_direct
                            else []
                        ),
                        "classes": ["ExampleTest", *(forge_direct_unexecuted or ())]
                        if is_forge_direct
                        else ["ExampleTest"],
                        "executed_classes": {
                            "ExampleTest": {
                                "tests": 10,
                                "failures": forge_direct_failed if is_forge_direct else 0,
                                "errors": 0,
                                "skipped": 0,
                                "reports": [f"report-{run_id}.xml"],
                            },
                            **{
                                name: {"fresh_reports_scanned": 1, "unparseable_reports": []}
                                for name in (forge_direct_unexecuted or ())
                                if is_forge_direct
                            },
                        },
                        "started_utc": stamp,
                        "ended_utc": stamp,
                        "receipt_digest": f"digest-{stamp}",
                    }
                ),
                encoding="utf-8",
            )
    (root / "EPOCH_IDENTITY.json").write_text(
        json.dumps(
            {
                "created_utc": stamp,
                "run_id": run_id,
                "producing_source": {
                    "repository": "https://github.com/example/lab",
                    "commit": "a" * 40,
                    "tree": "b" * 40,
                },
            }
        ),
        encoding="utf-8",
    )


def test_identical_packets_have_no_differences(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial)
    _write_packet(shadow)
    assert module.compare_packets(serial, shadow) == []


def test_a_changed_af_verdict_is_detected(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial)
    _write_packet(shadow, af04_verdict="FAIL")
    differences = module.compare_packets(serial, shadow)
    assert any(
        "AF04 verdict" in line and "serial='PASS'" in line and "shadow='FAIL'" in line
        for line in differences
    ), differences


def test_a_changed_full107_count_and_row_verdict_are_detected(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial)
    _write_packet(shadow, pass_count=101, row_b_state="FAIL")
    differences = module.compare_packets(serial, shadow)
    assert any("FULL107 counts.PASS" in line and "serial=102" in line for line in differences)
    assert any("FULL107 row ROW_B" in line and "shadow='FAIL'" in line for line in differences)


def test_a_changed_native_failure_count_is_detected(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial)
    _write_packet(shadow, forge_direct_failed=2)
    differences = module.compare_packets(serial, shadow)
    assert any(
        "native receipt forge:direct failures" in line and "serial=0" in line and "shadow=2" in line
        for line in differences
    ), differences


def test_a_changed_native_return_code_is_detected(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial)
    _write_packet(shadow, forge_direct_returncode=1)
    differences = module.compare_packets(serial, shadow)
    assert any(
        "native receipt forge:direct returncode" in line
        and "serial=0" in line
        and "shadow=1" in line
        for line in differences
    ), differences


def test_a_changed_native_unexecuted_class_set_is_detected(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial)
    _write_packet(shadow, forge_direct_unexecuted=["ForgeDirectResidualTest"])
    differences = module.compare_packets(serial, shadow)
    assert any(
        "native receipt forge:direct unexecuted_classes" in line
        and "shadow=['ForgeDirectResidualTest']" in line
        for line in differences
    ), differences


def test_reordered_unexecuted_classes_are_not_a_difference(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial, forge_direct_unexecuted=["AlphaTest", "BetaTest"])
    _write_packet(shadow, forge_direct_unexecuted=["BetaTest", "AlphaTest"])
    assert module.compare_packets(serial, shadow) == []


def test_timestamps_durations_and_run_ids_are_ignored(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial, stamp="2026-01-01T00:00:00+00:00", run_id="111111")
    _write_packet(shadow, stamp="2026-10-06T12:34:56+00:00", run_id="999999")
    assert module.compare_packets(serial, shadow) == []


def test_a_missing_document_is_reported(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial)
    _write_packet(shadow)
    (shadow / "AF00_AF11_XMAGE.json").unlink()
    differences = module.compare_packets(serial, shadow)
    assert any("missing from the shadow packet" in line for line in differences), differences


def test_the_cli_exit_code_is_non_zero_on_any_difference(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial)
    _write_packet(shadow, forge_direct_failed=1)
    assert module.main([str(serial), str(shadow)]) == 1
    assert module.main([str(serial), str(tmp_path / "serial")]) == 0


def _change(root: Path, name: str, mutate: Any) -> None:
    path = root / name
    document = json.loads(path.read_text())
    mutate(document)
    path.write_text(json.dumps(document))


@pytest.mark.parametrize("sides", [("shadow",), ("serial", "shadow")])
@pytest.mark.parametrize(
    ("name", "mutate", "reason"),
    [
        ("AF00_AF11_XMAGE.json", lambda d: d["gates"].pop(), "12 gates"),
        (
            "AF00_AF11_XMAGE.json",
            lambda d: d["gates"].__setitem__(1, d["gates"][0]),
            "duplicate AF00-AF11",
        ),
        ("AF00_AF11_XMAGE.json", lambda d: d["gates"][0].pop("verdict"), "malformed gate"),
        ("AF00_AF11_XMAGE.json", lambda d: d.__setitem__("candidate", "forge"), "candidate-bound"),
        ("FULL107_XMAGE_RESULTS.json", lambda d: d["rows"].pop(), "107 rows"),
        (
            "FULL107_XMAGE_RESULTS.json",
            lambda d: d["rows"].__setitem__(2, d["rows"][0]),
            "duplicate fixture",
        ),
        (
            "FULL107_XMAGE_RESULTS.json",
            lambda d: d["rows"][0].pop("exit_state"),
            "malformed fixture",
        ),
        (
            "FULL107_XMAGE_RESULTS.json",
            lambda d: d["counts"].__setitem__("PASS", True),
            "malformed outcome counts",
        ),
        (
            "FULL107_XMAGE_RESULTS.json",
            lambda d: d["counts"].__setitem__("PASS", 101),
            "counts disagree",
        ),
        (
            "FULL107_XMAGE_RESULTS.json",
            lambda d: d.__setitem__("total", 106),
            "total must be exactly 107",
        ),
        (
            "receipts/native-forge-direct.json",
            lambda d: d.pop("classes"),
            "declared/unexecuted classes",
        ),
        (
            "receipts/native-forge-direct.json",
            lambda d: d["classes"].append("ExampleTest"),
            "duplicate declared/unexecuted classes",
        ),
        (
            "receipts/native-forge-direct.json",
            lambda d: d["executed_classes"]["ExampleTest"].pop("tests"),
            "per-class execution counts",
        ),
        (
            "receipts/native-forge-direct.json",
            lambda d: d["unexecuted_classes"].append("ExampleTest"),
            "unexecuted identity inconsistent",
        ),
        (
            "receipts/native-forge-direct.json",
            lambda d: d.__setitem__("returncode", False),
            "malformed native return code",
        ),
    ],
)
def test_equal_or_one_sided_invalid_packets_never_compare_as_equivalent(
    tmp_path: Path, sides: tuple[str, ...], name: str, mutate: Any, reason: str
) -> None:
    module = _module()
    roots = {side: tmp_path / side for side in ("serial", "shadow")}
    for root in roots.values():
        _write_packet(root)
    for side in sides:
        _change(roots[side], name, mutate)
    differences = module.compare_packets(roots["serial"], roots["shadow"])
    for side in sides:
        assert any(line.startswith(side) and reason in line for line in differences), differences
    assert module.main([str(roots["serial"]), str(roots["shadow"])]) == 1


@pytest.mark.parametrize("duplicate", [False, True])
def test_equal_native_group_omissions_or_duplicates_are_rejected(
    tmp_path: Path, duplicate: bool
) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    for root in (serial, shadow):
        _write_packet(root)
        path = root / "receipts/native-forge-direct.json"
        if duplicate:
            (root / "receipts/native-forge-duplicate.json").write_bytes(path.read_bytes())
        else:
            path.unlink()
    differences = module.compare_packets(serial, shadow)
    reason = "duplicate candidate/group" if duplicate else "required group is missing"
    assert any(reason in line for line in differences), differences


def test_native_class_outcomes_cannot_hide_behind_equal_aggregates(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    for root in (serial, shadow):
        _write_packet(root, forge_direct_failed=2)

        def install_two_classes(doc: dict) -> None:
            doc["classes"] = ["ExampleTest", "OtherTest"]
            doc["executed_classes"] = {
                "ExampleTest": {"tests": 5, "failures": 2, "errors": 0, "skipped": 0},
                "OtherTest": {"tests": 5, "failures": 0, "errors": 0, "skipped": 0},
            }

        _change(root, "receipts/native-forge-direct.json", install_two_classes)
    assert module.compare_packets(serial, shadow) == []

    def redistribute(doc: dict) -> None:
        doc["executed_classes"]["ExampleTest"]["failures"] = 1
        doc["executed_classes"]["OtherTest"]["failures"] = 1
        doc["unexecuted_classes"] = ["ExampleTest", "OtherTest"]

    _change(shadow, "receipts/native-forge-direct.json", redistribute)
    differences = module.compare_packets(serial, shadow)
    assert any("executed_classes" in line for line in differences), differences
    assert not any("forge:direct failures:" in line for line in differences), differences


def test_malformed_top_level_objects_fail_closed(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    for root in (serial, shadow):
        _write_packet(root)
        (root / "FULL107_XMAGE_RESULTS.json").write_text("[]")
    assert any("candidate-bound object" in line for line in module.compare_packets(serial, shadow))


@pytest.mark.parametrize("field", ["repository", "commit", "tree"])
def test_equal_outcomes_from_another_source_are_not_a_valid_pair(
    tmp_path: Path, field: str
) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    _write_packet(serial)
    _write_packet(shadow)

    def change_source(doc: dict) -> None:
        doc["producing_source"][field] = (
            "https://github.com/example/other" if field == "repository" else "c" * 40
        )

    _change(shadow, "EPOCH_IDENTITY.json", change_source)
    assert module.compare_packets(serial, shadow) == [
        "epoch identity: producing repository/commit/tree differ"
    ]


def test_missing_epoch_identity_on_both_sides_is_not_a_valid_pair(tmp_path: Path) -> None:
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"
    for root in (serial, shadow):
        _write_packet(root)
        (root / "EPOCH_IDENTITY.json").unlink()
    differences = module.compare_packets(serial, shadow)
    assert len(differences) == 2
    assert all("missing or malformed producing source" in line for line in differences)


@pytest.mark.parametrize("outcome", ["absent", "failure", "skipped", "zero_cases"])
def test_real_producer_unexecuted_shapes_compare_and_one_sided_gaps_are_detected(
    tmp_path: Path, outcome: str
) -> None:
    from commander_lab.qualification.current_boundary.receipts import observed_class_executions

    reports = tmp_path / "reports"
    reports.mkdir()
    if outcome != "absent":
        case = {
            "failure": '<testcase classname="ExampleTest" name="case"><failure/></testcase>',
            "skipped": '<testcase classname="ExampleTest" name="case"><skipped/></testcase>',
            "zero_cases": "",
        }[outcome]
        (reports / "TEST-ExampleTest.xml").write_text(f'<testsuite tests="0">{case}</testsuite>')
    observed, unexecuted = observed_class_executions([reports], ("ExampleTest",), not_before=0)
    assert unexecuted == ("ExampleTest",)
    module = _module()
    serial, shadow = tmp_path / "serial", tmp_path / "shadow"

    def producer_shape(doc: dict) -> None:
        doc["executed_classes"] = observed
        doc["unexecuted_classes"] = list(unexecuted)

    for root in (serial, shadow):
        _write_packet(root)
        _change(root, "receipts/native-forge-direct.json", producer_shape)
    assert module.compare_packets(serial, shadow) == []
    _write_packet(shadow)
    differences = module.compare_packets(serial, shadow)
    assert any("forge:direct unexecuted_classes" in line for line in differences), differences
    assert not any("invalid comparison input" in line for line in differences), differences

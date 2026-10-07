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
from pathlib import Path
from typing import Any

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
        (root / f"FULL107_{candidate.upper()}_RESULTS.json").write_text(
            json.dumps(
                {
                    "candidate": candidate,
                    "run_id": run_id,
                    "counts": {"PASS": pass_count, "UNKNOWN": 107 - pass_count},
                    "rows": [
                        {"fixture_id": "ROW_A", "exit_state": "PASS"},
                        {"fixture_id": "ROW_B", "exit_state": row_b_state},
                    ],
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
                            list(forge_direct_unexecuted or ()) if is_forge_direct else []
                        ),
                        "started_utc": stamp,
                        "ended_utc": stamp,
                        "receipt_digest": f"digest-{stamp}",
                    }
                ),
                encoding="utf-8",
            )
    (root / "EPOCH_IDENTITY.json").write_text(
        json.dumps({"created_utc": stamp, "run_id": run_id}), encoding="utf-8"
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

"""The SpotBugs gate fails only for new findings at or above the configured priority."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "spotbugs_gate", ROOT / "scripts" / "spotbugs_gate.py"
)
assert _spec is not None and _spec.loader is not None
GATE: Any = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GATE)


def _bug(bug_type: str, priority: int, cls: str, method: str, line: int) -> str:
    return (
        f"<BugInstance type='{bug_type}' priority='{priority}'>"
        f"<Class classname='{cls}' primary='true'><SourceLine start='1' end='9'/></Class>"
        f"<Method classname='{cls}' name='{method}' primary='true'>"
        f"<SourceLine start='{line}' end='{line}'/></Method>"
        f"<SourceLine start='{line}' end='{line}'/></BugInstance>"
    )


def _write_xml(path: Path, *bugs: str) -> Path:
    path.write_text(f"<BugCollection>{''.join(bugs)}</BugCollection>", encoding="utf-8")
    return path


def _run(tmp_path: Path, *bugs: str) -> int:
    baseline = tmp_path / "baseline.json"
    GATE.write_baseline(
        baseline,
        GATE.load_findings(_write_xml(tmp_path / "base.xml", _bug("A", 2, "p.C", "m", 10))),
    )
    xml = _write_xml(tmp_path / "now.xml", *bugs)
    return int(GATE.main([str(xml), "--baseline", str(baseline), "--fail-on-new-priority", "1"]))


def test_same_finding_is_ok(tmp_path: Path) -> None:
    assert _run(tmp_path, _bug("A", 2, "p.C", "m", 10)) == 0


def test_line_change_is_ok(tmp_path: Path) -> None:
    assert _run(tmp_path, _bug("A", 2, "p.C", "m", 250)) == 0


def test_new_high_finding_fails(tmp_path: Path) -> None:
    assert _run(tmp_path, _bug("A", 2, "p.C", "m", 10), _bug("B", 1, "p.C", "m", 11)) == 1


def test_new_low_priority_finding_is_ok(tmp_path: Path) -> None:
    assert _run(tmp_path, _bug("A", 2, "p.C", "m", 10), _bug("B", 2, "p.C", "other", 11)) == 0


def test_baseline_roundtrip_schema(tmp_path: Path) -> None:
    baseline = tmp_path / "b.json"
    GATE.write_baseline(
        baseline, GATE.load_findings(_write_xml(tmp_path / "x.xml", _bug("A", 2, "p.C", "m", 1)))
    )
    assert json.loads(baseline.read_text())["schema"] == "spotbugs-baseline/v1"
    assert GATE.load_baseline(baseline) == {"A|p.C|method:m"}

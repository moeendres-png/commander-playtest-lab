#!/usr/bin/env python3
"""Compare a SpotBugs XML report against a reviewed baseline.

A finding is identified by (bug type, class, method or field) without line
numbers, so unrelated edits that move code do not make a baselined finding
"new". The gate exits non-zero only for findings that are not in the baseline
and whose priority is <= ``--fail-on-new-priority`` (1 = High). Other new
findings are listed but do not fail.

The XML is produced by the project's own CI build step (not untrusted input);
only the standard library parser is used.

    python scripts/spotbugs_gate.py target/spotbugsXml.xml --baseline config/spotbugs-baseline.json
    python scripts/spotbugs_gate.py target/spotbugsXml.xml --baseline config/spotbugs-baseline.json --write-baseline
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SCHEMA = "spotbugs-baseline/v1"


def finding_key(bug: ET.Element) -> str:
    """Stable identity: ``TYPE|class|member`` (member is ``method:name``, ``field:name`` or empty)."""
    cls = bug.find("Class[@primary='true']")
    if cls is None:
        cls = bug.find("Class")
    class_name = cls.get("classname", "") if cls is not None else ""
    member = ""
    method = bug.find("Method[@primary='true']")
    if method is not None:
        member = f"method:{method.get('name', '')}"
    else:
        field = bug.find("Field[@primary='true']")
        if field is not None:
            member = f"field:{field.get('name', '')}"
    return f"{bug.get('type', '')}|{class_name}|{member}"


def load_findings(xml_path: Path) -> dict[str, dict[str, Any]]:
    """Map finding key -> {"priority": best (lowest) priority, "count": occurrences}."""
    findings: dict[str, dict[str, Any]] = {}
    for bug in ET.parse(xml_path).getroot().iter("BugInstance"):
        entry = findings.setdefault(finding_key(bug), {"priority": 99, "count": 0})
        entry["priority"] = min(entry["priority"], int(bug.get("priority", "99")))
        entry["count"] += 1
    return findings


def load_baseline(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"{path}: unsupported baseline schema {data.get('schema')!r}")
    return {item["key"] for item in data["findings"]}


def write_baseline(path: Path, findings: dict[str, dict[str, Any]]) -> None:
    items = [
        {"key": key, "priority": value["priority"], "count": value["count"]}
        for key, value in sorted(findings.items())
    ]
    payload = {"schema": SCHEMA, "findings": items}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("xml", type=Path, help="SpotBugs XML report (target/spotbugsXml.xml)")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--fail-on-new-priority", type=int, default=1)
    parser.add_argument(
        "--write-baseline", action="store_true", help="write the baseline from the XML and exit 0"
    )
    args = parser.parse_args(argv)

    findings = load_findings(args.xml)
    if args.write_baseline:
        write_baseline(args.baseline, findings)
        print(f"spotbugs-gate: wrote {len(findings)} findings to {args.baseline}")
        return 0

    baseline = load_baseline(args.baseline)
    new = {key: value for key, value in findings.items() if key not in baseline}
    blocking = {
        key: value for key, value in new.items() if value["priority"] <= args.fail_on_new_priority
    }
    fixed = baseline - findings.keys()
    print(
        f"spotbugs-gate: {len(findings)} findings, {len(baseline)} baselined, "
        f"{len(new)} new ({len(blocking)} blocking at priority <= {args.fail_on_new_priority}), "
        f"{len(fixed)} baselined no longer reported"
    )
    for key, value in sorted(new.items()):
        marker = "BLOCKING" if key in blocking else "new"
        print(f"  {marker} p{value['priority']} {key}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())

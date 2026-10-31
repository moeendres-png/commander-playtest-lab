#!/usr/bin/env python3
"""Report the Java libraries inside a bridge jar against a local advisory table.

Report only. The script reads the jar (``META-INF/maven/*/*/pom.properties`` and two class files)
and ``data/security/java_dependency_advisories.json``; it never goes online and no workflow calls
it. ``pip-audit`` cannot see the libraries shaded into the jar, so this is the only place where
they are compared with anything.

Statuses per library:

``ADVISORY_OPEN``  the table has an advisory whose ``fixed_in`` is above the jar's version.
``CHECKED_CLEAN``  the table lists the library as checked without a finding (on ``checked_on``).
``UNKNOWN``        the library is in neither list, or its version cannot be ordered. Never a pass.

The table is made by hand and ages: the report prints its age and says so when it is older than
``--max-age-days``. An old table can only say "nothing known on that date".

Usage:
    python3 scripts/report_java_dependencies.py --jar bridge.jar [--json out.json] [--strict]

Exit code 0 unless ``--strict`` is given; then 1 for any ADVISORY_OPEN or UNKNOWN library.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TABLE = ROOT / "data" / "security" / "java_dependency_advisories.json"

# Libraries the project builds itself; they have no advisories to look up.
OWN_GROUPS = ("org.mage", "org.commanderlab")

# Shaded libraries that leave no pom.properties; the version is not in the jar.
UNVERSIONED_PACKAGES = {"com/google/protobuf/": "com.google.protobuf:protobuf-java"}

H2_CONSTANTS_CLASS = "org/h2/engine/Constants.class"
H2_VERSION_PATTERN = re.compile(rb"\b1\.\d\.\d{3}\b")
DATABASE_UTILS_CLASS = "mage/cards/repository/DatabaseUtils.class"
SEVERITY_ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass(frozen=True)
class Component:
    key: str
    version: str
    source: str


@dataclass(frozen=True)
class Advisory:
    advisory_id: str
    component: str
    severity: str
    fixed_in: str
    summary: str
    reachability: str


@dataclass(frozen=True)
class Table:
    checked_on: dt.date
    advisories: tuple[Advisory, ...]
    checked_clean: frozenset[str]
    jar_facts: dict[str, str]


@dataclass(frozen=True)
class AdvisoryHit:
    advisory_id: str
    severity: str
    fixed_in: str
    summary: str
    reachability: str


@dataclass
class ComponentReport:
    key: str
    version: str
    status: str
    advisories: list[AdvisoryHit] = field(default_factory=list)
    note: str = ""


def _version_key(version: str) -> tuple[int, ...] | None:
    """Leading dotted numbers of a Maven version ("33.4.8-jre" -> (33, 4, 8)), or None."""
    match = re.match(r"^(\d+(?:\.\d+)*)", version.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _below(version: str, fixed_in: str) -> bool | None:
    """True if ``version`` sorts below ``fixed_in``; None if either cannot be ordered."""
    left, right = _version_key(version), _version_key(fixed_in)
    if left is None or right is None:
        return None
    width = max(len(left), len(right))
    pad = (0,) * width
    return (left + pad)[:width] < (right + pad)[:width]


def load_table(path: Path) -> Table:
    raw = json.loads(path.read_text(encoding="utf-8"))
    advisories = tuple(
        Advisory(
            advisory_id=str(entry["id"]),
            component=str(entry["component"]),
            severity=str(entry["severity"]),
            fixed_in=str(entry["fixed_in"]),
            summary=str(entry.get("summary", "")),
            reachability=str(entry.get("reachability", "")),
        )
        for entry in raw["advisories"]
    )
    return Table(
        checked_on=dt.date.fromisoformat(str(raw["checked_on"])),
        advisories=advisories,
        checked_clean=frozenset(str(item) for item in raw["checked_without_advisory"]),
        jar_facts={str(key): str(value) for key, value in raw.get("jar_facts", {}).items()},
    )


def read_components(jar: Path) -> tuple[list[Component], dict[str, str]]:
    """Libraries found in the jar plus the facts read from class files."""
    components: list[Component] = []
    facts: dict[str, str] = {}
    with zipfile.ZipFile(jar) as archive:
        names = set(archive.namelist())
        for name in sorted(names):
            if not (name.startswith("META-INF/maven/") and name.endswith("/pom.properties")):
                continue
            properties: dict[str, str] = {}
            for line in archive.read(name).decode("utf-8", "replace").splitlines():
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    properties[key.strip()] = value.strip()
            group, artifact = properties.get("groupId"), properties.get("artifactId")
            version = properties.get("version")
            if group and artifact and version:
                components.append(Component(f"{group}:{artifact}", version, "pom.properties"))
        for prefix, key in UNVERSIONED_PACKAGES.items():
            if any(name.startswith(prefix) for name in names) and all(
                component.key != key for component in components
            ):
                components.append(Component(key, "unknown", "class prefix"))
        if H2_CONSTANTS_CLASS in names:
            # The class holds the running version and the last stable one (1.4.197 and 1.4.196);
            # the running one is the highest.
            found = [
                match.decode("ascii")
                for match in set(H2_VERSION_PATTERN.findall(archive.read(H2_CONSTANTS_CLASS)))
            ]
            version = max(found, key=lambda text: _version_key(text) or ()) if found else "unknown"
            components.append(Component("com.h2database:h2", version, "class literal"))
        if DATABASE_UTILS_CLASS in names:
            marker = b"AUTO_SERVER=TRUE" in archive.read(DATABASE_UTILS_CLASS)
            facts["h2_auto_server"] = "present" if marker else "not found"
        else:
            facts["h2_auto_server"] = "class not in jar (not determined)"
    return components, facts


def classify(components: list[Component], table: Table) -> list[ComponentReport]:
    reports: list[ComponentReport] = []
    for component in components:
        if component.key.split(":", 1)[0] in OWN_GROUPS:
            continue
        hits: list[AdvisoryHit] = []
        unordered = False
        for entry in table.advisories:
            if entry.component != component.key:
                continue
            below = _below(component.version, entry.fixed_in)
            if below is None:
                unordered = True
            elif below:
                hits.append(
                    AdvisoryHit(
                        entry.advisory_id,
                        entry.severity,
                        entry.fixed_in,
                        entry.summary,
                        entry.reachability,
                    )
                )
        if hits:
            hits.sort(key=lambda hit: -SEVERITY_ORDER.get(hit.severity, -1))
            reports.append(ComponentReport(component.key, component.version, "ADVISORY_OPEN", hits))
        elif unordered or _version_key(component.version) is None:
            note = "version cannot be ordered against the table"
            reports.append(ComponentReport(component.key, component.version, "UNKNOWN", [], note))
        elif component.key in table.checked_clean:
            reports.append(ComponentReport(component.key, component.version, "CHECKED_CLEAN"))
        else:
            note = "no entry in the table"
            reports.append(ComponentReport(component.key, component.version, "UNKNOWN", [], note))
    return reports


def render(
    reports: list[ComponentReport],
    facts: dict[str, str],
    table: Table,
    age_days: int,
    max_age_days: int,
) -> list[str]:
    lines = [f"table checked_on {table.checked_on} ({age_days} days old)"]
    if age_days > max_age_days:
        lines.append(
            f"WARNING: the table is older than {max_age_days} days; it can only say what was "
            "known on its date."
        )
    for report in reports:
        lines.append(
            f"{report.status:<14} {report.key} {report.version}"
            + (f"  [{report.note}]" if report.note else "")
        )
        for hit in report.advisories:
            lines.append(
                f"    {hit.severity} {hit.advisory_id} fixed in {hit.fixed_in}: {hit.summary}"
            )
            if hit.reachability:
                lines.append(f"      reachability: {hit.reachability}")
    h2_fact = facts.get("h2_auto_server")
    if h2_fact is not None:
        lines.append(f"jar fact h2_auto_server: {h2_fact}")
        if h2_fact == "present":
            lines.append(f"    {table.jar_facts.get('h2_auto_server', '')}")
    counts: dict[str, int] = {}
    for report in reports:
        counts[report.status] = counts.get(report.status, 0) + 1
    lines.append(
        "summary: "
        + ", ".join(f"{name} {count}" for name, count in sorted(counts.items()))
        + " (report only; UNKNOWN is not a pass)"
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--json", type=Path, default=None, dest="json_out")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-age-days", type=int, default=30)
    parser.add_argument("--today", type=dt.date.fromisoformat, default=None, help="test hook")
    args = parser.parse_args(argv)

    table = load_table(args.table)
    components, facts = read_components(args.jar)
    reports = classify(components, table)
    today = args.today or dt.date.today()
    age_days = (today - table.checked_on).days
    for line in render(reports, facts, table, age_days, args.max_age_days):
        print(line)
    if args.json_out is not None:
        payload = {
            "checked_on": table.checked_on.isoformat(),
            "table_age_days": age_days,
            "jar_facts": facts,
            "components": [asdict(report) for report in reports],
        }
        args.json_out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    bad = any(report.status != "CHECKED_CLEAN" for report in reports)
    return 1 if (args.strict and bad) else 0


if __name__ == "__main__":
    sys.exit(main())

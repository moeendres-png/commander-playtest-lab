#!/usr/bin/env python3
"""Project the owner's private data into the public stand-in the repository carries.

The repository holds a stand-in for every owner-data path (see ``commander_lab.owner_data``):
the same files and schema, but

* every pointer to the owner's own storage (file ids, file names, workbook names) is
  ``redacted`` and every digest of such a file is 64 zeros;
* every count is at most one copy per named card (``0`` stays ``0``), and basic-land-sized
  counts (50 or more) become 99, so the stand-in says "one copy of every named card";
* printed (non-English) names and printing codes of the physical cards are dropped.

Card names, deck structure and the project's own scope decisions are kept.

    python scripts/project_owner_data.py --source PRIVATE_ROOT --target REPO_ROOT
    python scripts/project_owner_data.py --check REPO_ROOT       # stand-in is already projected

The real data lives in the private folder named by ``COMMANDER_LAB_OWNER_DATA``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commander_lab.owner_data import OWNER_DATA_PATHS  # noqa: E402

REDACTED = "redacted"
ZERO_DIGEST = "0" * 64
POINTER_KEYS = frozenset(
    {
        "drive_id",
        "drive_file_id",
        "source_drive_id",
        "source_drive_file_id",
        "inventory_source_drive_id",
        "source_path",
        "source_name",
        "source_file",
        "source_file_name",
        "source_workbook",
        "google_drive_modified",
    }
)
POINTER_LIST_KEYS = frozenset({"source_drive_ids"})
DIGEST_KEYS = frozenset({"sha256", "source_sha256", "source_file_sha256"})
DROPPED_KEYS = frozenset({"printed_name", "edition"})
QUANTITY_KEYS = frozenset(
    {"quantity", "physical_available_quantity", "available_quantity", "reserved_quantity"}
)
COUNT_MAPPING_KEYS = frozenset({"released_allocations"})
BASIC_LAND_SIZED = 50
BASIC_LAND_STAND_IN = 99


def _count(value: int) -> int:
    if value >= BASIC_LAND_SIZED:
        return BASIC_LAND_STAND_IN
    return min(value, 1)


def project(value: Any, key: str | None = None) -> Any:
    """The public stand-in of one JSON value (``key`` is the key it sits under)."""
    if isinstance(value, dict):
        if key in COUNT_MAPPING_KEYS:
            return {
                name: _count(count)
                if isinstance(count, int) and not isinstance(count, bool)
                else count
                for name, count in value.items()
            }
        return {
            name: project(item, name) for name, item in value.items() if name not in DROPPED_KEYS
        }
    if isinstance(value, list):
        if key in POINTER_LIST_KEYS:
            return [REDACTED for _ in value]
        return [project(item, key) for item in value]
    if key in POINTER_KEYS and isinstance(value, str):
        return REDACTED
    if key in DIGEST_KEYS and isinstance(value, str):
        return ZERO_DIGEST
    if key in QUANTITY_KEYS and isinstance(value, int) and not isinstance(value, bool):
        return _count(value)
    return value


def render(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def owner_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for entry in OWNER_DATA_PATHS:
        path = root / entry.rstrip("/")
        if path.is_dir():
            found.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        elif path.is_file():
            found.append(path)
    return found


def project_tree(source: Path, target: Path) -> int:
    written = 0
    for path in owner_files(source):
        relative = path.relative_to(source)
        payload = json.loads(path.read_text(encoding="utf-8"))
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render(project(payload)), encoding="utf-8")
        written += 1
    return written


def check_tree(root: Path) -> list[str]:
    """Owner-data files of ``root`` that are not already their own projection."""
    return [
        str(path.relative_to(root))
        for path in owner_files(root)
        if project(json.loads(path.read_text(encoding="utf-8")))
        != json.loads(path.read_text(encoding="utf-8"))
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    if args.check is not None:
        offenders = check_tree(args.check)
        for name in offenders:
            print(f"not a stand-in: {name}")
        return 1 if offenders else 0
    if args.source is None or args.target is None:
        parser.error("--source and --target (or --check) are required")
    print(f"projected {project_tree(args.source, args.target)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

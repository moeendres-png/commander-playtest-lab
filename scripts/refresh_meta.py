"""Report the freshness of meta data files (Meta-Lane PR6).

Read-only: snapshots under data/meta/snapshots, package files under
data/meta/packages, and data/meta/spellbook_combos.json. No network, no
refetch, no writes — a refresh is a new snapshot (the PR1 store refuses
to overwrite), never an edit of these files. Per file: each source's
retrieved_at, its stale boundary, status and days remaining; the combos
file carries a single provenance.retrieved_at.

Exit codes: 0 normally; 2 with --fail-on-stale when anything is stale
at --as-of; 1 when a file cannot be read or validated.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from commander_lab.models import MetaSource
from commander_lab.models.meta import expires_at_for
from commander_lab.whole_deck.meta import is_source_stale, load_snapshot

ROOT = Path(__file__).resolve().parents[1]


def parse_as_of(value: str) -> datetime:
    """Parse --as-of: a date (2027-09-01) or a full ISO timestamp."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _source_entry(source: MetaSource, now: datetime) -> dict[str, object]:
    stale = is_source_stale(source, now)
    boundary = (
        source.expires_at if source.expires_at is not None else expires_at_for(source.retrieved_at)
    )
    days = (boundary - now).days
    return {
        "source_id": source.source_id,
        "retrieved_at": source.retrieved_at.isoformat(),
        "expires_at": boundary.isoformat(),
        "status": "stale" if stale else "fresh",
        "days_remaining": days,
    }


def _file_status(entries: list[dict[str, object]]) -> str:
    stale = sum(1 for entry in entries if entry["status"] == "stale")
    if not entries or stale == len(entries):
        return "stale"
    if stale:
        return "partial"
    return "fresh"


def _snapshot_entry(path: Path, now: datetime) -> dict[str, object]:
    try:
        snapshot = load_snapshot(path)
    except (OSError, ValueError) as error:
        return {"path": str(path), "status": "error", "error": str(error)}
    entries = [_source_entry(source, now) for source in snapshot.sources]
    return {
        "path": str(path),
        "status": _file_status(entries),
        "sources": entries,
    }


def _combos_entry(path: Path, now: datetime) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        retrieved_raw = data["provenance"]["retrieved_at"]
        retrieved = parse_as_of(str(retrieved_raw))
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"path": str(path), "status": "error", "error": str(error)}
    boundary = expires_at_for(retrieved)
    stale = now >= boundary
    days = (boundary - now).days
    return {
        "path": str(path),
        "status": "stale" if stale else "fresh",
        "retrieved_at": retrieved.isoformat(),
        "expires_at": boundary.isoformat(),
        "days_remaining": days,
    }


def build_report(root: Path, now: datetime) -> dict[str, object]:
    """Freshness report over the meta files under `root` at `now`."""
    snapshot_files = sorted((root / "data/meta/snapshots").glob("*.json"))
    package_files = sorted((root / "data/meta/packages").glob("*.json"))
    snapshots = [_snapshot_entry(path, now) for path in snapshot_files]
    packages = [_snapshot_entry(path, now) for path in package_files]
    combos = _combos_entry(root / "data/meta/spellbook_combos.json", now)
    all_entries = snapshots + packages + [combos]
    stale_files = sum(1 for entry in all_entries if entry["status"] in ("stale", "partial"))
    error_files = sum(1 for entry in all_entries if entry["status"] == "error")
    return {
        "as_of": now.isoformat(),
        "snapshots": snapshots,
        "packages": packages,
        "combos": combos,
        "summary": {
            "files": len(all_entries),
            "stale_files": stale_files,
            "error_files": error_files,
        },
    }


def _render(report: dict[str, object]) -> str:
    lines = [f"meta freshness as of {report['as_of']}"]
    for section in ("snapshots", "packages"):
        entries = report[section]
        assert isinstance(entries, list)
        for entry in entries:
            assert isinstance(entry, dict)
            lines.append(f"{entry['path']}: {entry['status']}")
            if entry["status"] == "error":
                lines.append(f"  error: {entry['error']}")
                continue
            sources = entry["sources"]
            assert isinstance(sources, list)
            for source in sources:
                assert isinstance(source, dict)
                days = source["days_remaining"]
                assert isinstance(days, int)
                remaining = f"{days} days left" if days >= 0 else f"{-days} days overdue"
                lines.append(
                    f"  {source['source_id']}: {source['status']}, "
                    f"retrieved {source['retrieved_at']}, "
                    f"expires {source['expires_at']}, {remaining}"
                )
    combos = report["combos"]
    assert isinstance(combos, dict)
    lines.append(f"{combos['path']}: {combos['status']}")
    if combos["status"] == "error":
        lines.append(f"  error: {combos['error']}")
    else:
        days = combos["days_remaining"]
        assert isinstance(days, int)
        remaining = f"{days} days left" if days >= 0 else f"{-days} days overdue"
        lines.append(
            f"  provenance: retrieved {combos['retrieved_at']}, "
            f"expires {combos['expires_at']}, {remaining}"
        )
    summary = report["summary"]
    assert isinstance(summary, dict)
    lines.append(
        f"files: {summary['files']}, stale: {summary['stale_files']}, "
        f"errors: {summary['error_files']}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report meta data freshness (PR6).")
    parser.add_argument(
        "--as-of",
        default=None,
        help="Reference time, e.g. 2027-09-01 (default: now, UTC).",
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="Exit 2 when anything is stale at --as-of.",
    )
    args = parser.parse_args(argv)
    now = parse_as_of(args.as_of) if args.as_of else datetime.now(UTC)
    report = build_report(args.root, now)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_render(report))
    summary = report["summary"]
    assert isinstance(summary, dict)
    if summary["error_files"]:
        return 1
    if args.fail_on_stale and summary["stale_files"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

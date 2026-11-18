"""Guard for an import into a store COPY: snapshot before, snapshot after, compare.

``snapshot`` opens the store read only (``mode=ro``; add ``--immutable`` only while no Studio
process has the file open) and writes a JSON with: SQLite ``integrity_check``, the number of rows
``foreign_key_check`` returns, a digest of the schema, rows and a content digest per table, a digest
of the ``card_id`` to ``oracle_id`` map, and size and SHA-256 of the file.

``compare BEFORE AFTER [--allow-changed TABLE ...]`` prints what changed and exits 1 when the
integrity check or the foreign key check is not clean afterwards, the schema changed, the card to
oracle id map changed, or a table outside ``--allow-changed`` changed. Use it after each import
step with the tables that step may touch (RUNBOOK.md lists them). Run it on copies only.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common


def snapshot(db_path: Path, *, immutable: bool = False) -> dict[str, Any]:
    if not db_path.is_file():
        raise common.WaveError(f"store file not found: {db_path}")
    connection = sqlite3.connect(common.sqlite_uri(db_path, immutable=immutable), uri=True)
    try:
        result: dict[str, Any] = {
            "file_bytes": db_path.stat().st_size,
            "file_sha256": common.sha256_file(db_path),
            "integrity_check": [row[0] for row in connection.execute("PRAGMA integrity_check")],
            "foreign_key_check_rows": len(
                connection.execute("PRAGMA foreign_key_check").fetchall()
            ),
        }
        schema = "\n".join(
            f"{row[0]}|{row[1]}|{row[2]}"
            for row in connection.execute(
                "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
            )
        )
        result["schema_digest"] = hashlib.sha256(schema.encode("utf-8")).hexdigest()
        tables: dict[str, dict[str, Any]] = {}
        names = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for (name,) in names:
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')]
            order = ",".join(str(index + 1) for index in range(len(columns)))
            digest = hashlib.sha256()
            rows = 0
            for row in connection.execute(f'SELECT * FROM "{name}" ORDER BY {order}'):
                digest.update(repr(row).encode("utf-8"))
                digest.update(b"\n")
                rows += 1
            tables[name] = {"rows": rows, "digest": digest.hexdigest()}
        result["tables"] = tables
        if "card" in tables:
            pairs = connection.execute(
                "SELECT card_id, oracle_id FROM card ORDER BY card_id"
            ).fetchall()
            result["card_oracle_map_digest"] = hashlib.sha256(
                repr(pairs).encode("utf-8")
            ).hexdigest()
            result["card_oracle_null"] = sum(
                1 for _card_id, oracle_id in pairs if oracle_id is None
            )
    finally:
        connection.close()
    return result


def compare(
    before: dict[str, Any], after: dict[str, Any], allowed: set[str]
) -> tuple[list[str], list[str]]:
    """Return (report lines, failures)."""
    lines: list[str] = []
    failures: list[str] = []
    lines.append(
        f"integrity_check before/after: {before['integrity_check']} / {after['integrity_check']}"
    )
    lines.append(
        "foreign_key_check rows before/after: "
        f"{before['foreign_key_check_rows']} / {after['foreign_key_check_rows']}"
    )
    if after["integrity_check"] != ["ok"]:
        failures.append("integrity_check is not ok after the step")
    if after["foreign_key_check_rows"] != 0:
        failures.append("foreign_key_check reports rows after the step")
    same_schema = before["schema_digest"] == after["schema_digest"]
    lines.append(f"schema digest equal: {same_schema}")
    if not same_schema:
        failures.append("the schema changed")
    same_map = before.get("card_oracle_map_digest") == after.get("card_oracle_map_digest")
    lines.append(f"card.oracle_id map equal: {same_map}")
    if not same_map:
        failures.append("the card to oracle id map changed")
    changed: list[str] = []
    for name in sorted(set(before["tables"]) | set(after["tables"])):
        old, new = before["tables"].get(name), after["tables"].get(name)
        if old is None or new is None:
            changed.append(name)
            lines.append(f"  {name}: table added or removed")
        elif old != new:
            changed.append(name)
            lines.append(f"  {name}: rows {old['rows']} -> {new['rows']}, content changed")
    lines.append(f"tables changed: {len(changed)} of {len(after['tables'])}")
    for name in changed:
        if name not in allowed:
            failures.append(f"table {name} changed but is not in --allow-changed")
    return lines, failures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    shot = commands.add_parser("snapshot", help="write a snapshot JSON of a store copy")
    shot.add_argument("--db", type=Path, required=True)
    shot.add_argument("--out", type=Path, required=True)
    shot.add_argument("--immutable", action="store_true")
    diff = commands.add_parser("compare", help="compare two snapshots")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--allow-changed", nargs="*", default=[], metavar="TABLE")
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot":
            result = snapshot(args.db, immutable=args.immutable)
            common.write_json(args.out, result)
            print(
                f"{args.db}: integrity {result['integrity_check']}, "
                f"foreign_key_check rows {result['foreign_key_check_rows']}, "
                f"{len(result['tables'])} tables"
            )
            return (
                0
                if result["integrity_check"] == ["ok"] and not result["foreign_key_check_rows"]
                else 1
            )
        lines, failures = compare(
            common.read_json(args.before), common.read_json(args.after), set(args.allow_changed)
        )
    except (common.WaveError, OSError, sqlite3.Error) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    for failure in failures:
        print(f"FAIL: {failure}")
    print("GUARD: FAIL" if failures else "GUARD: PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

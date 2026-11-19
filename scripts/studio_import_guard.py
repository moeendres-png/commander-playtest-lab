"""Import guard for the Studio store: ``before`` and ``verify`` around one import step.

It extends ``scripts/data_wave1/db_guard.py`` (rows and content digest per table, schema digest,
integrity and foreign key check, card to oracle id map) and does not repeat that logic. It adds
what the guard lacks:

* the Studio schema version (``meta.schema_version``),
* an EXPECTED ROW DELTA per table (``--expect TABLE=+N``), not only "this table may change",
* consistency counts of content that lives twice (rulings, role claims, cohorts, deck stats) and
  of exact duplicate rows in ``observation``, each as n of N or ``unbekannt`` (never 0) when a
  table is missing.

``before --db STORE --out FILE`` opens the store read only (``mode=ro``) and writes a JSON outside
the repository. ``verify --db STORE --before FILE --expect TABLE=DELTA ...`` measures again and
prints PASS or FAIL with the deviating tables; exit 0 for PASS, 1 for FAIL, 2 for a usage or
store error. DELTA is ``+N``, ``-N``, ``0`` or ``any`` (rows may change by any amount). A table
that is not listed must be unchanged in rows and content. The output holds table names and numbers
only: no card names, no deck addresses. Run it on a store copy while no Studio process has it open.
Opening a store with newer code can add indexes without a new schema version (#1548) and that
changes the schema digest: open the copy once with the new code, then run ``before``.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent / "data_wave1"))
import _common as common
import db_guard

UNKNOWN = "unbekannt"
DELTA_PATTERN = re.compile(r"^(?:any|[+-]?\d+)$")

# name -> (SQL returning (n, N), tables it needs): how many rows of the first table are also
# found in its twin table; only measurable when the tables exist.
_RATIO_CHECKS: dict[str, tuple[str, tuple[str, ...]]] = {
    "card_ruling_in_card_ruling_source": (
        "SELECT SUM(EXISTS (SELECT 1 FROM card_ruling_source s WHERE s.oracle_id = r.oracle_id"
        " AND s.published_at = r.published_at AND s.comment = r.comment)), COUNT(*)"
        " FROM card_ruling r",
        ("card_ruling", "card_ruling_source"),
    ),
    "card_role_in_card_role_claim": (
        "SELECT SUM(EXISTS (SELECT 1 FROM card_role_claim c WHERE c.oracle_id = r.oracle_id"
        " AND c.role = r.role)), COUNT(*) FROM card_role r",
        ("card_role", "card_role_claim"),
    ),
    "corpus_deck_cohort_in_corpus_cohort": (
        "SELECT SUM(EXISTS (SELECT 1 FROM corpus_cohort c WHERE c.deck_id = d.deck_id"
        " AND c.cohort = 'commander:' || d.cohort)), COUNT(*) FROM corpus_deck d",
        ("corpus_deck", "corpus_cohort"),
    ),
    "corpus_deck_with_stat_row": (
        "SELECT SUM(EXISTS (SELECT 1 FROM corpus_deck_stat s WHERE s.deck_id = d.deck_id)),"
        " COUNT(*) FROM corpus_deck d",
        ("corpus_deck", "corpus_deck_stat"),
    ),
}
_OBSERVATION_DUPLICATES = (
    "SELECT COUNT(*), COALESCE(SUM(n), 0) FROM ("
    " SELECT COUNT(*) AS n FROM observation"
    " GROUP BY card_id, card_name, metric, cohort, value, numerator, denominator,"
    " data_class, url, snapshot, source_id HAVING COUNT(*) > 1)"
)


_OBSERVATION_DUPLICATES_NO_SOURCE = _OBSERVATION_DUPLICATES.replace(
    "data_class, url, snapshot, source_id HAVING", "data_class, url, snapshot HAVING"
)


def _open(db_path: Path, immutable: bool) -> sqlite3.Connection:
    return sqlite3.connect(common.sqlite_uri(db_path, immutable=immutable), uri=True)


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def consistency(db_path: Path, *, immutable: bool = False) -> dict[str, Any]:
    """Counts of doubled content and exact duplicates; numbers only, ``unbekannt`` if unmeasurable."""
    connection = _open(db_path, immutable)
    try:
        tables = _table_names(connection)
        result: dict[str, Any] = {}
        for name, (sql, needs) in _RATIO_CHECKS.items():
            if not set(needs) <= tables:
                result[name] = UNKNOWN
                continue
            found, total = connection.execute(sql).fetchone()
            result[name] = {"n": int(found or 0), "N": int(total)}
        if "observation" in tables:
            groups, rows = connection.execute(_OBSERVATION_DUPLICATES).fetchone()
            result["observation_exact_duplicates"] = {"groups": int(groups), "rows": int(rows)}
            groups, rows = connection.execute(_OBSERVATION_DUPLICATES_NO_SOURCE).fetchone()
            result["observation_duplicates_ignoring_source_id"] = {
                "groups": int(groups),
                "rows": int(rows),
            }
        else:
            result["observation_exact_duplicates"] = UNKNOWN
            result["observation_duplicates_ignoring_source_id"] = UNKNOWN
        return result
    finally:
        connection.close()


def _schema_version(db_path: Path, immutable: bool) -> str:
    connection = _open(db_path, immutable)
    try:
        if "meta" not in _table_names(connection):
            return UNKNOWN
        row = connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return UNKNOWN if row is None else str(row[0])
    finally:
        connection.close()


def measure(db_path: Path, *, immutable: bool = False) -> dict[str, Any]:
    result = db_guard.snapshot(db_path, immutable=immutable)
    result["schema_version"] = _schema_version(db_path, immutable)
    result["consistency"] = consistency(db_path, immutable=immutable)
    return result


def parse_expect(items: Sequence[str]) -> dict[str, str]:
    expected: dict[str, str] = {}
    for item in items:
        table, separator, delta = item.partition("=")
        if not separator or not table or not DELTA_PATTERN.match(delta):
            raise common.WaveError(
                f"--expect needs TABLE=+N, TABLE=-N, TABLE=0 or TABLE=any: {item}"
            )
        if table in expected:
            raise common.WaveError(f"--expect names the table twice: {table}")
        expected[table] = delta
    return expected


def verify(
    before: dict[str, Any], after: dict[str, Any], expected: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Return (report lines, failures)."""
    lines, failures = db_guard.compare(before, after, set(expected))
    old_version, new_version = before.get("schema_version"), after.get("schema_version")
    lines.append(f"schema_version before/after: {old_version} / {new_version}")
    if old_version != new_version:
        failures.append(f"schema_version changed: {old_version} -> {new_version}")
    for table, delta in sorted(expected.items()):
        old, new = before["tables"].get(table), after["tables"].get(table)
        if old is None or new is None:
            failures.append(f"table {table} is expected but missing ({UNKNOWN})")
            continue
        actual = new["rows"] - old["rows"]
        lines.append(
            f"  expect {table}: {delta}, actual {actual:+d} ({old['rows']} -> {new['rows']})"
        )
        if delta != "any" and int(delta) == 0 and old["digest"] != new["digest"]:
            failures.append(f"table {table}: expected no change, content digest differs")
        if delta != "any" and actual != int(delta):
            failures.append(f"table {table}: expected row delta {delta}, actual {actual:+d}")
    old_consistency = before.get("consistency", {})
    for name, value in sorted(after.get("consistency", {}).items()):
        lines.append(
            f"consistency {name} before/after: {old_consistency.get(name, UNKNOWN)} / {value}"
        )
    old_dupes = old_consistency.get("observation_exact_duplicates")
    new_dupes = after.get("consistency", {}).get("observation_exact_duplicates")
    if (
        isinstance(old_dupes, dict)
        and isinstance(new_dupes, dict)
        and new_dupes["rows"] > old_dupes["rows"]
    ):
        failures.append(
            f"observation exact duplicate rows grew: {old_dupes['rows']} -> {new_dupes['rows']}"
        )
    return lines, failures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    first = commands.add_parser("before", help="measure the store, write a JSON outside the repo")
    first.add_argument("--db", type=Path, required=True)
    first.add_argument("--out", type=Path, required=True)
    first.add_argument("--immutable", action="store_true")
    second = commands.add_parser("verify", help="measure again, compare with the expected delta")
    second.add_argument("--db", type=Path, required=True)
    second.add_argument("--before", type=Path, required=True)
    second.add_argument("--expect", nargs="*", default=[], metavar="TABLE=DELTA")
    second.add_argument("--immutable", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.db.is_file():
            raise common.WaveError(f"store file not found: {args.db}")
        if args.command == "before":
            out_path = common.assert_outside_repository(args.out)
            result = measure(args.db, immutable=args.immutable)
            common.write_json(out_path, result)
            print(
                f"before: schema_version {result['schema_version']}, "
                f"{len(result['tables'])} tables, integrity {result['integrity_check']}"
            )
            return 0
        expected = parse_expect(args.expect)
        lines, failures = verify(
            common.read_json(args.before), measure(args.db, immutable=args.immutable), expected
        )
    except (common.WaveError, OSError, sqlite3.Error) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    for failure in failures:
        print(f"FAIL: {failure}")
    print("IMPORT GUARD: FAIL" if failures else "IMPORT GUARD: PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

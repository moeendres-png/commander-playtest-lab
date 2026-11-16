"""Importers for research files that no other Studio importer reads.

Each importer reads one original file, records it as a source with its SHA-256 and writes in
one transaction, replacing only its own scope, so repeating it changes nothing.

* ``import_tagger_roles``: the tagger bulk (CSV with ``oracle_id``, ``category``,
  ``bulk_label``) is converted into a full role snapshot and merged through
  ``roles.import_role_snapshot``. Only the roles of the Studio vocabulary (``roles.ROLES``)
  are taken; a category outside it is counted and listed, never turned into a role.
* ``import_rubric``: the Chulane rating rubric (``summary.csv`` of a ``chulane_rubric_<date>``
  folder) becomes three stored signals of one commander (``signals.SIGNAL_RUBRIC`` and its two
  companions), recorded as a source with its SHA-256; a repeated import replaces only these
  signals of that commander.
* ``capture_date``: the date a research file was fetched, read from the folder's README table.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

from . import roles, signals, strength
from .store import DataClass, StudioStore, sha256_file

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TAGGER_REQUIRED = {"oracle_id", "category", "bulk_label"}
_SCOPE_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")
CROSSWALK_VERSION = "category-column-1"

# The commander a rubric folder belongs to, by the folder name without its date. An explicit
# table: a rubric folder whose name is not in it is not imported (no guessing a commander).
RUBRIC_COMMANDERS: dict[str, str] = {"chulane_rubric": "Chulane, Teller of Tales"}
RUBRIC_SUMMARY = "summary.csv"
RUBRIC_COLUMNS = (
    "card",
    "H_mean",
    "H_sd",
    "raters",
    "anchor",
    "E_mean",
    "F_mean",
    "T_mean",
    "R_mean",
    "W_mean",
)
_RUBRIC_FOLDER = re.compile(r"^(?P<key>[a-z0-9_]+_rubric)_(?P<date>\d{8})$")


def capture_date(readme: Path, file_stem: str) -> str | None:
    """The latest ``YYYY-MM-DD`` on the README line that names ``file_stem``, if any.

    ``Abruf 2026-11-11/12`` reads as 2026-11-12: the shorthand after the slash is a day of the
    same month. A file the README does not name has no known capture date."""
    if not readme.is_file():
        return None
    found: list[str] = []
    for line in readme.read_text(encoding="utf-8-sig").splitlines():
        if file_stem not in line:
            continue
        for match in re.finditer(r"(\d{4}-\d{2}-)(\d{2})(?:/(\d{1,2}))?", line):
            found.append(match.group(1) + (match.group(3) or match.group(2)).zfill(2))
    return max(found) if found else None


def _scope_key(path: Path) -> str:
    return _SCOPE_CHARS.sub("_", path.stem).strip("_.-")[:40] or "tagger_bulk"


def import_tagger_roles(
    store: StudioStore, path: str | Path, *, fetched_at: str | None = None, force: bool = False
) -> dict[str, object]:
    """Import the tagger bulk CSV as a full role snapshot of its own scope.

    A row whose ``category`` is one of the Studio roles gives that card the role; the row's
    ``bulk_label`` is kept as the original tag of the role. A file without any role row never
    replaces the scope (``status`` NO_ROWS); a file that would remove more than half of the
    scope's earlier claims replaces only with ``force`` (``status`` WARNUNG, nothing changed).
    Rows with another category, or
    without a usable oracle id, are counted (``unknown_categories``, ``rows_skipped``).
    The scope is the file's own: importing a changed file replaces the claims of this scope
    only (``claims_removed`` says how many); claims of other origins and scopes stay."""
    file_path = Path(path)
    members: dict[str, set[str]] = {role: set() for role in roles.ROLES}
    labels: dict[str, set[str]] = {role: set() for role in roles.ROLES}
    unknown: dict[str, int] = {}
    read = skipped = 0
    with file_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = _TAGGER_REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{file_path.name}: missing column(s) {', '.join(sorted(missing))}")
        for row in reader:
            read += 1
            oracle_id = (row.get("oracle_id") or "").strip()
            category = (row.get("category") or "").strip()
            if not oracle_id or re.search(r"[\s:]", oracle_id) or len(oracle_id) > 64:
                skipped += 1
                continue
            if category not in roles.ROLES:
                unknown[category or "(empty)"] = unknown.get(category or "(empty)", 0) + 1
                continue
            members[category].add(oracle_id)
            label = (row.get("bulk_label") or "").strip()
            if label:
                labels[category].add(label)
    new_pairs = {(oid, role) for role, ids in members.items() for oid in ids}
    scope = _scope_key(file_path)
    old_pairs = {
        (str(r[0]), str(r[1]))
        for r in store.connection.execute(
            "SELECT oracle_id, role FROM card_role_claim WHERE role_origin = ? AND scope_key = ?",
            (roles.ORIGIN_CROSSWALK, scope),
        )
    }
    counts: dict[str, object] = {
        "rows_read": read,
        "rows_skipped": skipped,
        "rows_with_other_category": sum(unknown.values()),
        "unknown_categories": dict(sorted(unknown.items())),
        "claims_in_file": len(new_pairs),
        "claims_in_scope_before": len(old_pairs),
    }
    if not new_pairs:
        return {
            **counts,
            "status": "NO_ROWS",
            "message": "the file has no row for a Studio role: the scope was left unchanged",
        }
    removed = len(old_pairs - new_pairs)
    if old_pairs and removed * 2 > len(old_pairs) and not force:
        return {
            **counts,
            "status": "WARNUNG",
            "message": f"the file would remove {removed} of {len(old_pairs)} earlier claims of "
            "this scope: nothing was changed; run again with --force if that is intended",
        }
    parsed = roles.RoleFile(
        origin=roles.ORIGIN_CROSSWALK,
        mode=roles.FULL_SNAPSHOT,
        scope_key=scope,
        fetched_at=fetched_at or "",
        tags={role: "|".join(sorted(labels[role])) or role for role in roles.ROLES},
        mapping_rule=f"crosswalk:{CROSSWALK_VERSION}",
        roles={role: tuple(sorted(ids)) for role, ids in members.items()},
    )
    report = roles.import_role_snapshot(
        store,
        parsed,
        title=file_path.name,
        sha256=sha256_file(file_path),
        allow_scope_replace=True,
    )
    return {
        **report,
        **counts,
        "status": "IMPORTED",
        "roles_without_cards": sorted(role for role, ids in members.items() if not ids),
    }


def rubric_folder_key(folder: Path) -> tuple[str, str] | None:
    """``(commander, date)`` of a rubric folder (``<key>_rubric_<YYYYMMDD>``), ``None`` when
    the name has another shape or its key is not in ``RUBRIC_COMMANDERS``."""
    match = _RUBRIC_FOLDER.match(folder.name)
    if match is None or match.group("key") not in RUBRIC_COMMANDERS:
        return None
    return RUBRIC_COMMANDERS[match.group("key")], match.group("date")


def find_rubric_folders(research: Path) -> list[Path]:
    """The rubric folders of ``research`` that hold a ``summary.csv``: per commander only the
    newest one (by the date in its name), in commander order."""
    newest: dict[str, tuple[str, Path]] = {}
    if research.is_dir():
        for folder in sorted(research.iterdir()):
            found = rubric_folder_key(folder)
            if found is None or not (folder / RUBRIC_SUMMARY).is_file():
                continue
            commander, date = found
            if commander not in newest or date > newest[commander][0]:
                newest[commander] = (date, folder)
    return [item[1] for _commander, item in sorted(newest.items())]


def _rubric_number(text: str, name: str, line: int) -> float:
    try:
        value = float(text)
    except ValueError:
        raise ValueError(
            f"{RUBRIC_SUMMARY} line {line}: {name} is not a number: {text!r}"
        ) from None
    if not math.isfinite(value):
        raise ValueError(f"{RUBRIC_SUMMARY} line {line}: {name} must be finite")
    return value


def read_rubric(path: Path) -> list[dict[str, str | float | int]]:
    """The rows of a rubric ``summary.csv``, checked. The header must be exactly
    ``RUBRIC_COLUMNS`` (an unknown layout raises ValueError), ``H_mean`` must lie in 1..10,
    ``H_sd`` and the criterion means must not be negative, ``raters`` must be a whole number
    and ``anchor`` 0 or 1; a card named twice raises, nothing is dropped silently."""
    rows: list[dict[str, str | float | int]] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != RUBRIC_COLUMNS:
            raise ValueError(
                f"{path.name}: unknown column layout {list(reader.fieldnames or [])}, "
                f"expected {list(RUBRIC_COLUMNS)}"
            )
        for number, row in enumerate(reader, start=2):
            card = (row["card"] or "").strip()
            if not card:
                raise ValueError(f"{path.name} line {number}: card name is empty")
            if card.casefold() in seen:
                raise ValueError(f"{path.name} line {number}: card {card!r} appears twice")
            seen.add(card.casefold())
            h_mean = _rubric_number(row["H_mean"] or "", "H_mean", number)
            if strength.rubric_value(h_mean) is None:
                raise ValueError(f"{path.name} line {number}: H_mean {h_mean} is outside 1..10")
            h_sd = _rubric_number(row["H_sd"] or "", "H_sd", number)
            raters = _rubric_number(row["raters"] or "", "raters", number)
            anchor = _rubric_number(row["anchor"] or "", "anchor", number)
            if h_sd < 0 or raters < 0 or raters != int(raters) or anchor not in (0.0, 1.0):
                raise ValueError(f"{path.name} line {number}: H_sd, raters or anchor is invalid")
            for column in RUBRIC_COLUMNS[5:]:
                if _rubric_number(row[column] or "", column, number) < 0:
                    raise ValueError(f"{path.name} line {number}: {column} is negative")
            rows.append(
                {
                    "card": card,
                    "H_mean": h_mean,
                    "H_sd": h_sd,
                    "raters": int(raters),
                    "anchor": int(anchor),
                }
            )
    if not rows:
        raise ValueError(f"{path.name}: the file has no rating row")
    return rows


def import_rubric(store: StudioStore, folder: str | Path) -> dict[str, object]:
    """Import ``summary.csv`` of a rubric folder as signals of the folder's commander.

    The commander comes from ``RUBRIC_COMMANDERS`` by the folder name (ValueError for a folder
    that is not in it). The file is recorded as a source with its SHA-256 (data class
    ``HEURISTIC_MODEL``: a rating, not a measurement). Written in one transaction, replacing
    only the three rubric signals of that commander, so repeating the import changes nothing.
    ``rows_unmatched`` counts the cards that no card of the store carries by name (0 for a
    store that holds no card at all: nothing to match against)."""
    root = Path(folder)
    found = rubric_folder_key(root)
    if found is None:
        raise ValueError(
            f"{root.name}: not a known rubric folder (known: {sorted(RUBRIC_COMMANDERS)})"
        )
    commander, date = found
    path = root / RUBRIC_SUMMARY
    rows = read_rubric(path)
    digest = sha256_file(path)
    known = signals.known_card_names(store)
    unmatched = sorted(
        str(row["card"]) for row in rows if known and str(row["card"]).casefold() not in known
    )
    names = (signals.SIGNAL_RUBRIC, signals.SIGNAL_RUBRIC_SD, signals.SIGNAL_RUBRIC_RATERS)
    snap = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 and date.isdigit() else date
    with store.connection as db:
        source_id = store.register_source(
            data_class=DataClass.HEURISTIC_MODEL,
            title=f"{root.name}/{RUBRIC_SUMMARY}",
            sha256=digest,
            snapshot_date=snap,
        )
        marks = ", ".join("?" for _ in names)
        replaced = int(
            db.execute(
                f"SELECT COUNT(*) FROM card_signal WHERE commander_name = ? AND signal IN ({marks})",
                (commander, *names),
            ).fetchone()[0]
        )
        db.execute(
            f"DELETE FROM card_signal WHERE commander_name = ? AND signal IN ({marks})",
            (commander, *names),
        )
        db.executemany(
            "INSERT INTO card_signal(commander_name, signal, card_name, value, numerator, "
            "denominator, source_id) VALUES (?, ?, ?, ?, NULL, NULL, ?)",
            [
                (commander, signal, row["card"], row[column], source_id)
                for row in rows
                for signal, column in zip(names, ("H_mean", "H_sd", "raters"), strict=True)
            ],
        )
    return {
        "rows_read": len(rows),
        "rows_written": len(rows) * len(names),
        "rows_replaced": replaced,
        "rows_unmatched": len(unmatched),
        "anchors": sum(1 for row in rows if row["anchor"] == 1),
        "commander": commander,
        "folder_date": date,
        "source_id": source_id,
        "sha256": digest,
        "unmatched": unmatched,
    }

"""Importers for research files that no other Studio importer reads.

Each importer reads one original file, records it as a source with its SHA-256 and writes in
one transaction, replacing only its own scope, so repeating it changes nothing.

* ``import_tagger_roles``: the tagger bulk (CSV with ``oracle_id``, ``category``,
  ``bulk_label``) is converted into a full role snapshot and merged through
  ``roles.import_role_snapshot``. Only the roles of the Studio vocabulary (``roles.ROLES``)
  are taken; a category outside it is counted and listed, never turned into a role.
* ``capture_date``: the date a research file was fetched, read from the folder's README table.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from . import roles
from .store import StudioStore, sha256_file

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TAGGER_REQUIRED = {"oracle_id", "category", "bulk_label"}
_SCOPE_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")
CROSSWALK_VERSION = "category-column-1"


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

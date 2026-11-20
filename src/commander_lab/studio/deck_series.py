"""Stored paired series that involve a revision of one deck (read-only; #1404).

Reads the ``*.paired.json`` files that ``paired_series`` writes and keeps the ones whose base
(A) or variant (B) is a revision of the deck. It reproduces the stored fields and nothing else:
counts with n/N, the stored difference and intervals, seeds, seats and provenance. No verdict,
no ranking, no weight: a simulation result never enters the tier list or the strength index.
A series that is not completed (running, interrupted, cancelled, failed) never counts as a
result; its numbers stay unknown instead of 0. A corrupt or foreign file is skipped and counted.

Since B2 (#1658) the series of a deck come from the experiment index (``experiments``): every
indexed series is delivered, with no scan limit; a series whose plan SHA does not match its plan
file does not count. Files the index does not name (old series before an import) are still
found by the bounded folder scan, so nothing the Owner played disappears.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from .games import games_folder
from .paired_series import SCHEMA_PAIRED_JOB, validate_series_id
from .store import StudioStore

#: An index row with its variant (``variant_revision_id``), as every reader of the index needs.
EXPERIMENT_SELECT = (
    "SELECT e.*, (SELECT v.revision_id FROM experiment_arm v WHERE v.experiment_id = "
    "e.experiment_id AND v.role = 'variant') AS variant_revision_id FROM experiment e"
)

#: Same bound as the revision chain of ``swap``; also the cap of the answer.
SERIES_LIMIT = 200
#: Files looked at at most, so a huge games folder cannot stall the route.
SCAN_LIMIT = 2000
#: A series file is a few KB; anything above this is not one and is skipped (counted).
MAX_FILE_BYTES = 2_000_000

STATUS_COMPLETED = "completed"
STATUS_STOPPED_EARLY = "stopped_early"
STATUS_CANCELLED = "cancelled"
STATUS_FAILED = "failed"
STATUS_INCOMPLETE = "incomplete"
STATUS_PLAN_MISMATCH = "plan_mismatch"

_STATUS_TEXT = {
    STATUS_COMPLETED: "abgeschlossen",
    STATUS_STOPPED_EARLY: "vorzeitig gestoppt nach Regel",
    STATUS_CANCELLED: "abgebrochen",
    STATUS_FAILED: "fehlgeschlagen",
    STATUS_INCOMPLETE: "nicht abgeschlossen",
    STATUS_PLAN_MISMATCH: "Plan-SHA passt nicht zum Ergebnis (zählt nicht)",
}


def deck_revision_ids(store: StudioStore, deck_id: str) -> list[str] | None:
    """Revision ids of the deck, newest first, at most ``SERIES_LIMIT``; None for an unknown deck."""
    db = store.connection
    if db.execute("SELECT 1 FROM deck WHERE deck_id = ?", (deck_id,)).fetchone() is None:
        return None
    return [
        str(row[0])
        for row in db.execute(
            "SELECT revision_id FROM deck_revision WHERE deck_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (deck_id, SERIES_LIMIT),
        )
    ]


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, int) and not isinstance(item, bool)]


def _str_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _interval(value: object) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    low, high = _as_float(value[0]), _as_float(value[1])
    return None if low is None or high is None else [low, high]


def series_status(raw: Mapping[str, object]) -> str:
    """Map the stored job state to one of the five stated kinds.

    Only ``completed`` with a stored result counts; it is "stopped early" when the stop rule
    ended it before the planned pairs were played. Everything else is not a result.
    """
    state = raw.get("status")
    if state == "cancelled":
        return STATUS_CANCELLED
    if state == "failed":
        return STATUS_FAILED
    result = raw.get("result")
    if state != "completed" or not isinstance(result, dict):
        return STATUS_INCOMPLETE
    completed = _as_int(result.get("pairs_completed"))
    if completed is None or completed < 1:
        return STATUS_INCOMPLETE  # no evaluable pair (or malformed): not a result
    planned = _as_int(raw.get("budget_pairs"))
    played = _as_int(result.get("pairs_played"))
    stop_reason = result.get("stop_reason")
    if (
        isinstance(stop_reason, str)
        and stop_reason.startswith("DECIDED_")
        and planned is not None
        and played is not None
        and played < planned
    ):
        return STATUS_STOPPED_EARLY
    return STATUS_COMPLETED


def _entry(raw: Mapping[str, object], status: str) -> dict[str, object]:
    result = raw.get("result")
    res: Mapping[str, object] = result if isinstance(result, dict) else {}
    counts = status in (STATUS_COMPLETED, STATUS_STOPPED_EARLY)
    done = _as_int(res.get("pairs_completed")) if counts else None
    seats = (
        (_int_list(res.get("tested_seats")) or _int_list(raw.get("tested_seats")))
        if counts
        else _int_list(raw.get("tested_seats"))
    )
    seeds = _int_list(res.get("seeds")) or _int_list(res.get("seeds_completed"))
    bridge_shas = _str_list(res.get("bridge_jar_sha256s")) or _str_list(
        raw.get("bridge_jar_sha256s")
    )
    qualification = _str_list(res.get("bridge_qualification_states")) or _str_list(
        raw.get("bridge_qualification_states")
    )
    stop_reason = res.get("stop_reason")
    # Library slots of the variant: a series without slot_alignment was played before the
    # alignment existed; aligned and unaligned series are never added up.
    raw_alignment = raw.get("slot_alignment")
    alignment = raw_alignment if isinstance(raw_alignment, dict) else None
    if alignment is None:
        alignment_state = "not_aligned_legacy"
    elif (_as_int(alignment.get("appended")) or 0) + (_as_int(alignment.get("dropped")) or 0):
        alignment_state = "not_congruent"
    else:
        alignment_state = "aligned"
    return {
        "series_id": str(raw["series_id"]),
        "created_at": raw.get("created_at") if isinstance(raw.get("created_at"), str) else None,
        "base_ref": str(raw["base_ref"]),
        "variant_ref": str(raw["variant_ref"]),
        "pod": raw.get("pod") if isinstance(raw.get("pod"), str) else None,
        "status": status,
        "status_text": _STATUS_TEXT[status],
        "counts_as_result": counts,
        "pairs_planned": _as_int(raw.get("budget_pairs")),
        "pairs_completed": done,
        "pairs_attempted": _as_int(raw.get("pairs_attempted")),
        "pairs_censored": _as_int(res.get("pairs_censored")) if counts else None,
        "difference_pp": _as_float(res.get("difference_pp")) if counts else None,
        "difference_ci95_pp": _interval(res.get("difference_ci95_pp")) if counts else None,
        "decision_ci_pp": _interval(res.get("decision_ci_pp")) if counts else None,
        "decision_level_pct": _as_float(res.get("decision_level_pct")) if counts else None,
        "stop_reason": stop_reason if counts and isinstance(stop_reason, str) else None,
        "seeds": seeds,
        "tested_seats": seats,
        "seats_planned": not counts,
        "pilots": _str_list(res.get("pilots")),
        "bridge_jar_sha256s": bridge_shas,
        "bridge_qualification_states": qualification,
        "covered_by_sealed_epoch": bool(res.get("covered_by_sealed_epoch")) if res else None,
        "error": raw.get("error") if isinstance(raw.get("error"), str) else None,
        "slot_alignment": alignment,
        "slot_alignment_state": alignment_state,
    }


def read_series_file(path: Path) -> dict[str, object] | None:
    """The parsed series, or None for a file that is corrupt, foreign or not this format."""
    try:
        # Only regular files: opening a FIFO without a writer would block for good.
        if not path.is_file():
            return None
        # A bounded read: a file that grows after a size check cannot exceed the limit.
        with path.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            return None
        raw = json.loads(data.decode("utf-8"))
    except (OSError, ValueError, RecursionError, MemoryError):
        return None
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA_PAIRED_JOB:
        return None
    series_id = raw.get("series_id")
    if not isinstance(series_id, str) or path.name != f"{series_id}.paired.json":
        return None
    try:
        validate_series_id(series_id)
    except ValueError:
        return None
    if not isinstance(raw.get("base_ref"), str) or not isinstance(raw.get("variant_ref"), str):
        return None
    return raw


def entry_for_experiment(data_folder: str | Path, row: sqlite3.Row) -> dict[str, object]:
    """The history entry of one indexed experiment (or legacy series) from its result file."""
    from .experiments import experiment_view, plan_intact, plan_record

    folder = games_folder(Path(data_folder).resolve())
    series_id = row["series_id"]
    raw = read_series_file(folder / f"{series_id}.paired.json") if series_id else None
    if raw is None:  # no result file (yet): not a result, numbers unknown
        raw = {
            "series_id": str(series_id or row["experiment_id"]),
            "base_ref": str(row["base_revision_id"]),
            "variant_ref": str(row["variant_revision_id"] or ""),
        }
        status = STATUS_INCOMPLETE
    else:
        status = series_status(raw)
    experiment = experiment_view(data_folder, row)
    if experiment is not None and not plan_intact(
        plan_record(data_folder, str(row["experiment_id"])), raw
    ):
        status = STATUS_PLAN_MISMATCH
    entry = _entry(raw, status)
    entry["experiment"] = experiment
    return entry


def _indexed(
    store: StudioStore, data_folder: str | Path, deck_id: str
) -> tuple[list[dict[str, object]], set[str], set[str]]:
    """Every indexed series of the deck, the revisions it names, and every indexed series id."""
    db = store.connection
    rows = db.execute(
        f"{EXPERIMENT_SELECT} WHERE e.experiment_id IN (SELECT a.experiment_id FROM "
        "experiment_arm a JOIN deck_revision r ON r.revision_id = a.revision_id "
        "WHERE r.deck_id = ?)",
        (deck_id,),
    ).fetchall()
    revisions = {
        str(r[0])
        for r in db.execute(
            "SELECT a.revision_id FROM experiment_arm a JOIN deck_revision r "
            "ON r.revision_id = a.revision_id WHERE r.deck_id = ?",
            (deck_id,),
        )
    }
    every = {str(r[0]) for r in db.execute("SELECT series_id FROM experiment") if r[0]}
    return [entry_for_experiment(data_folder, row) for row in rows], revisions, every


def deck_series(
    data_folder: str | Path,
    revision_ids: list[str],
    *,
    store: StudioStore | None = None,
    deck_id: str | None = None,
) -> dict[str, object]:
    """Stored paired series whose A or B is one of ``revision_ids``, newest first.

    With ``store`` and ``deck_id`` the indexed series of the deck come from the index, all of
    them; the folder scan then only looks at files the index does not name."""
    wanted = set(revision_ids)
    indexed: list[dict[str, object]] = []
    known: set[str] = set()
    if store is not None and deck_id is not None:
        indexed, revisions, known = _indexed(store, data_folder, deck_id)
        wanted |= revisions
    folder = games_folder(Path(data_folder).resolve())
    every = (
        sorted(
            (
                p
                for p in folder.glob("paired-*.paired.json")
                if p.name.removesuffix(".paired.json") not in known
            ),
            reverse=True,
        )
        if folder.is_dir()
        else []
    )
    files = every[:SCAN_LIMIT]
    found: list[dict[str, object]] = []
    skipped = 0
    for path in files:
        raw = read_series_file(path)
        if raw is None:
            skipped += 1
            continue
        if raw["base_ref"] in wanted or raw["variant_ref"] in wanted:
            entry = _entry(raw, series_status(raw))
            entry["experiment"] = None
            found.append(entry)
    found.sort(key=lambda item: str(item["created_at"] or ""), reverse=True)
    scanned = found[:SERIES_LIMIT]
    series = sorted(
        [*indexed, *scanned],
        key=lambda item: (str(item["created_at"] or ""), str(item["series_id"])),
        reverse=True,
    )
    by_revision: dict[str, list[dict[str, str]]] = {}
    for item in series:
        for role, own, other in (
            ("base", item["base_ref"], item["variant_ref"]),
            ("variant", item["variant_ref"], item["base_ref"]),
        ):
            if str(own) in wanted:
                by_revision.setdefault(str(own), []).append(
                    {
                        "series_id": str(item["series_id"]),
                        "role": role,
                        "counterpart_ref": str(other),
                    }
                )
    return {
        "schema": "studio-deck-series-1",
        "data_class": "SIMULATED_RESULT",
        "series": series,
        "by_revision": by_revision,
        "skipped": skipped,
        "series_total": len(series),
        "truncated": len(found) > SERIES_LIMIT,
        "scan_limit": SCAN_LIMIT,
        "scan_truncated": max(0, len(every) - SCAN_LIMIT),
    }

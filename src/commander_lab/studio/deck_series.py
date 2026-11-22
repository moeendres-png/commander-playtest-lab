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
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from .games import games_folder
from .launch import MAX_SEATS, MIN_SEATS
from .paired_series import SCHEMA_PAIRED_JOB, observed_table_sizes, validate_series_id
from .store import StudioStore
from .table_spec import sha256_of

#: An experiment id as ``experiments`` writes it; a legacy row's id is its series id.
EXPERIMENT_ID_PATTERN = re.compile(r"^exp-[A-Za-z0-9_-]{1,90}$")

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


def revision_hashes(store: StudioStore, revision_ids: list[str]) -> dict[str, str]:
    """Deck hash of each of ``revision_ids`` (read-only); unknown ids are left out."""
    found: dict[str, str] = {}
    for start in range(0, len(revision_ids), 500):
        chunk = revision_ids[start : start + 500]
        marks = ",".join("?" * len(chunk))
        for row in store.connection.execute(
            f"SELECT revision_id, deck_hash FROM deck_revision WHERE revision_id IN ({marks})",
            chunk,
        ):
            found[str(row[0])] = str(row[1])
    return found


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


def series_table_check(raw: Mapping[str, object]) -> tuple[int | None, str]:
    """The table size of a stored series and how it was checked (#1661).

    The plan names it (``seed_plan.player_count``, 2 to 8, #1672); the played games name it too (the
    seat rows of their headers, ``paired_series.observed_table_sizes``). ``consistent``: the
    readable pods all show one size, none is unreadable, and it is the planned size (or, for a
    plan without a valid size such as an older series, a size of 2 to 8 the games alone show:
    ``series_table_source`` says so); ``mismatch``: the games show another size than the plan,
    or several sizes (unknown, fail-closed); ``unreadable``: a pod cannot be read or the pods do
    not cover the counted pairs (unknown); ``unobserved``: no pair is played yet; the planned size
    is named as planned only ("geplant, nicht an Partien geprüft"). Only ``consistent`` proves
    the size (``maturity.table_unproven``). Never the number of tested seats:
    a series without seat rotation tests one seat at any table size."""
    plan = raw.get("seed_plan")
    count = plan.get("player_count") if isinstance(plan, dict) else None
    planned = count if type(count) is int and MIN_SEATS <= count <= MAX_SEATS else None
    seen = observed_table_sizes(raw)
    if len(seen.sizes) > 1 or (planned is not None and seen.sizes and seen.sizes != [planned]):
        return None, "mismatch"
    if seen.unreadable:
        return None, "unreadable"
    if not seen.sizes:
        return planned, "unobserved"
    size = seen.sizes[0]
    if planned is None and not MIN_SEATS <= size <= MAX_SEATS:
        return None, "unreadable"
    return size, "consistent"


def series_table_source(raw: Mapping[str, object]) -> str | None:
    """Where a proven table size comes from: the plan and the games, or the games alone."""
    size, check = series_table_check(raw)
    if check != "consistent" or size is None:
        return None
    plan = raw.get("seed_plan")
    count = plan.get("player_count") if isinstance(plan, dict) else None
    planned = count if type(count) is int and MIN_SEATS <= count <= MAX_SEATS else None
    return (
        "aus Plan und gespielten Partien" if planned is not None else "aus den gespielten Partien"
    )


def series_table_size(raw: Mapping[str, object]) -> int | None:
    """The checked table size of a stored series (``series_table_check``), None = unknown."""
    return series_table_check(raw)[0]


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
        # 4-, 5- and 6-seat series are separate cohorts (base win rate 1/N); None = unknown
        "table_size": series_table_size(raw),
        "table_size_check": series_table_check(raw)[1],
        "table_size_source": series_table_source(raw),
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


# -- experiment index readers (B2, #1658); ``experiments`` writes, this module reads --


def experiments_folder(data_folder: str | Path) -> Path:
    return games_folder(Path(data_folder).resolve()) / "experiments"


def plan_sha(plan: Mapping[str, object], resolved: Mapping[str, object]) -> str:
    return sha256_of({"plan": plan, "resolved": resolved})


def plan_record(data_folder: str | Path, experiment_id: str) -> dict[str, object] | None:
    path = experiments_folder(data_folder) / experiment_id / "plan.json"
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    return raw if isinstance(raw, dict) else None


def plan_intact(record: Mapping[str, object] | None, series_raw: Mapping[str, object]) -> bool:
    """The result belongs to this plan: the plan file's own SHA is right and the series names
    it (M2). A result whose plan does not match never counts."""
    if record is None:
        return False
    plan, resolved = record.get("plan"), record.get("resolved")
    if not isinstance(plan, dict) or not isinstance(resolved, dict):
        return False
    sha = record.get("plan_sha")
    if sha != plan_sha(plan, resolved):
        return False
    experiment = series_raw.get("experiment")
    return isinstance(experiment, dict) and experiment.get("plan_sha") == sha


def experiment_view(row: sqlite3.Row) -> dict[str, object] | None:
    """What the history shows about an experiment; None for a legacy series (no plan)."""
    if row["plan_sha"] is None:
        return None
    decision = str(row["decision"])
    tested = row["decision_tested"]
    text = {"open": "offen", "adopted": "übernommen", "rejected": "verworfen"}[decision]
    if decision == "adopted" and tested == 0:
        text = "übernommen (ungetestet)"
    return {
        "experiment_id": str(row["experiment_id"]),
        "question": str(row["question"]),
        "question_kind": row["question_kind"],
        "purpose": str(row["purpose"]),
        "plan_sha": str(row["plan_sha"]),
        "table_hash": row["table_hash"],
        "seeds": [row["first_seed"], row["last_seed"]],
        "pilot_fingerprint": row["pilot_fingerprint"],
        "engine_pin": row["engine_pin"],
        "bridge_jar_sha256": row["bridge_jar_sha256"],
        "bridge_state": row["bridge_state"],
        "decision": decision,
        "decision_text": text,
        "decision_at": row["decision_at"],
        "decision_note": row["decision_note"],
        "decision_tested": None if tested is None else bool(tested),
    }


def entry_for_experiment(data_folder: str | Path, row: sqlite3.Row) -> dict[str, object]:
    """The history entry of one indexed experiment (or legacy series) from its result file."""
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
    experiment = experiment_view(row)
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
        # n/N of the bounded legacy scan (#1658 B2b): files read of the files present, series
        # shown of the series found in the files read (series in unread files stay unknown)
        "scan_files_read": len(files),
        "scan_files_total": len(every),
        "legacy_series_shown": len(scanned),
        "legacy_series_found": len(found),
        # with unread files the true number of legacy series is unknown: found is a lower bound
        "legacy_series_found_lower_bound": len(every) > len(files),
    }


def valid_index_id(value: str) -> bool:
    """An id the index can hold: an experiment id or, for a legacy row, the id of a
    ``paired-*.paired.json`` series (the only legacy files ``rebuild_index`` reads)."""
    if EXPERIMENT_ID_PATTERN.fullmatch(value):
        return True
    if not value.startswith("paired-"):
        return False
    try:
        return validate_series_id(value) == value
    except ValueError:
        return False


def _plan_state(record: Mapping[str, object] | None, row_sha: object) -> str:
    """Whether the plan file is there and its own SHA is the one the index names."""
    if row_sha is None:
        return "legacy"
    if record is None:
        return "missing"
    plan, resolved = record.get("plan"), record.get("resolved")
    if not isinstance(plan, dict) or not isinstance(resolved, dict):
        return "mismatch"
    sha = plan_sha(plan, resolved)
    return "intact" if record.get("plan_sha") == sha == row_sha else "mismatch"


_PLAN_FIELDS = (
    "question",
    "question_kind",
    "purpose",
    "budget_pairs",
    "look_every_pairs",
    "threshold_pp",
    "significance_level",
    "stop_rule",
    "first_seed",
    "table",
)


def experiment_detail(
    store: StudioStore, data_folder: str | Path, experiment_id: str
) -> dict[str, object] | None:
    """One indexed experiment (or legacy series) as stored: plan, arms, seeds, provenance,
    decision and the history entry of its result. Read-only: it writes no row and no file.
    None for an id the index does not hold. Files are only opened under the id of the row.

    What is not stored stays ``None`` (unknown), never 0. The maturity is not computed here;
    the route takes it from the same computation as ``/api/decks/{id}/series``."""
    db = store.connection
    row = db.execute(f"{EXPERIMENT_SELECT} WHERE e.experiment_id = ?", (experiment_id,)).fetchone()
    if row is None:
        return None
    own_id = str(row["experiment_id"])
    record = plan_record(data_folder, own_id) if row["plan_sha"] is not None else None
    state = _plan_state(record, row["plan_sha"])
    raw_plan = record.get("plan") if record and state == "intact" else None
    raw_resolved = record.get("resolved") if record and state == "intact" else None
    plan = {key: raw_plan.get(key) for key in _PLAN_FIELDS} if isinstance(raw_plan, dict) else None
    resolved = raw_resolved if isinstance(raw_resolved, dict) else {}
    seeds = resolved.get("seeds")
    arms = [
        {
            "role": str(a["role"]),
            "revision_id": str(a["revision_id"]),
            "deck_hash": a["deck_hash"],
        }
        for a in db.execute(
            "SELECT role, revision_id, deck_hash FROM experiment_arm WHERE experiment_id = ? "
            "ORDER BY CASE role WHEN 'base' THEN 0 ELSE 1 END, revision_id",
            (own_id,),
        )
    ]
    first, last = row["first_seed"], row["last_seed"]
    deck_id = str(row["deck_id"])
    main = (
        db.execute(
            "SELECT revision_id FROM deck_branch WHERE deck_id = ? AND branch = 'main'",
            (deck_id,),
        ).fetchone()
        if deck_id
        else None
    )
    return {
        "schema": "studio-experiment-detail-1",
        "data_class": "SIMULATED_RESULT",
        "experiment_id": own_id,
        "deck_id": deck_id or None,
        "legacy": row["plan_sha"] is None,
        "question": str(row["question"]),
        "purpose": str(row["purpose"]),
        "created_at": str(row["created_at"]) or None,
        "plan_state": state,
        "plan": plan,
        "table_hash": row["table_hash"],
        "table": resolved.get("table") if isinstance(resolved.get("table"), dict) else None,
        "tested_seats": _int_list(resolved.get("tested_seats")) or None,
        "arms": arms,
        "seeds": {
            "first": first,
            "last": last,
            "count": None if first is None or last is None else int(last) - int(first) + 1,
            "rule": seeds.get("rule") if isinstance(seeds, dict) else None,
        },
        "provenance": {
            "engine_pin": row["engine_pin"],
            "bridge_jar_sha256": row["bridge_jar_sha256"],
            "bridge_state": row["bridge_state"],
            "pilot_fingerprint": row["pilot_fingerprint"],
        },
        "experiment": experiment_view(row),
        "current_main_revision_id": None if main is None else str(main[0]),
        "result": entry_for_experiment(data_folder, row),
        "sources": {
            "plan": f"games/experiments/{own_id}/plan.json" if row["plan_sha"] else None,
            "result": f"games/{row['series_id']}.paired.json" if row["series_id"] else None,
            "index": "Studio-Store, Tabellen experiment/experiment_arm",
        },
    }

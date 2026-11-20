"""Experiment: one question about a deck, planned in a file before the first game (B2, #1658).

An experiment names a question (package, axis, single swap), the base deck state, its variant
arm(s), the table (``TableSpec``), budget, looks, threshold, seed plan, purpose (exploration,
confirmation, control) and stop rule. The plan is resolved (deck hashes, pilot fingerprint,
seeds, ``table_hash``) and written to ``experiments/<id>/plan.json`` with its SHA-256 before
the series starts; the series carries the plan SHA into its result. A result whose plan SHA does
not match its plan file never counts. The seed register (the index) refuses a confirmation on
seeds an exploration of the same deck already used. This is the core of #1525.

The store keeps only an additive index (``experiment``, ``experiment_arm``); raw data stays in
files, and :func:`rebuild_index` rebuilds the index from plan, run, decision and the old
``*.paired.json`` files. Adopting a variant sets the deck's ``main`` branch to the variant and
writes the decision to the row and to ``decision.json`` (E15 Q2: the click is the Owner's
decision on the Chulane base; ``data/decks/chulane_current.txt`` is never touched here). Every
number of an experiment stays ``SIMULATED_RESULT``.
"""

from __future__ import annotations

import contextlib
import itertools
import json
import os
import re
import shutil
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from . import paired_comparison, paired_series
from .deck_series import (
    EXPERIMENT_SELECT,
    entry_for_experiment,
    experiments_folder,
    plan_sha,
    read_series_file,
)
from .games import games_folder
from .launch import _precons, engine_state
from .pilot_fingerprint import pilot_fingerprint
from .play import POLICY_VERSION, snapshot_deck_hash
from .store import StudioStore, now_utc
from .table_spec import TableSpec, table_hash

SCHEMA_PLAN: Final = "studio-experiment-plan-1"
SCHEMA_RECORD = "studio-experiment-record-1"
SCHEMA_DECISION = "studio-experiment-decision-1"
DATA_CLASS = "SIMULATED_RESULT"
LEGACY_QUESTION = "Alt-Serie ohne Plan (vor #1658)"
MAX_FILE_BYTES = 2_000_000
_SAFE_ID = re.compile(r"^exp-[A-Za-z0-9_-]{1,90}$")
_SEQ = itertools.count(1)
_SEQ_LOCK = threading.Lock()


class ArmRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str = Field(min_length=1, max_length=200)


class ExperimentPlan(BaseModel):
    """The plan as the user (web or CLI) writes it; everything else is derived from it."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["studio-experiment-plan-1"] = Field(default=SCHEMA_PLAN, alias="schema")
    question: str = Field(min_length=1, max_length=500)
    question_kind: Literal["package", "axis", "single_swap"]
    deck_id: str = Field(min_length=1, max_length=200)
    base: ArmRef
    variants: list[ArmRef] = Field(min_length=1, max_length=8)
    table: TableSpec
    purpose: Literal["exploration", "confirmation", "control"]
    budget_pairs: int = Field(
        ge=paired_comparison.MIN_BUDGET_PAIRS, le=paired_comparison.MAX_BUDGET_PAIRS
    )
    look_every_pairs: int = Field(default=4, ge=1, le=100)
    threshold_pp: float = Field(default=paired_comparison.DEFAULT_THRESHOLD_PP, ge=-50, le=50)
    significance_level: float = Field(
        default=paired_comparison.DEFAULT_SIGNIFICANCE_LEVEL, gt=0.0, lt=0.5
    )
    first_seed: int = Field(ge=0, le=2_000_000_000)
    stop_rule: Literal["obf_looks"] = "obf_looks"


class SeedOverlap(ValueError):
    """A confirmation would run on seeds an exploration of the same deck already used."""


class DecisionRefused(RuntimeError):
    """The decision cannot be recorded (already decided, legacy series, foreign deck)."""


def validate_experiment_id(experiment_id: str) -> str:
    if not _SAFE_ID.fullmatch(experiment_id):
        raise ValueError(f"ungültige Experiment-ID: {experiment_id!r}")
    return experiment_id


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    return raw if isinstance(raw, dict) else None


def _revision_deck(store: StudioStore, revision_id: str) -> tuple[str, str] | None:
    row = store.connection.execute(
        "SELECT deck_id, deck_hash FROM deck_revision WHERE revision_id = ?", (revision_id,)
    ).fetchone()
    return None if row is None else (str(row["deck_id"]), str(row["deck_hash"]))


def _opponent_hash(store: StudioStore, ref: str) -> str | None:
    """The deck hash of one opponent; unknown is an error, never a stand-in (M5)."""
    by_id = {deck_id: path for deck_id, _n, _c, _y, path in _precons()}
    if ref in by_id:
        return snapshot_deck_hash(by_id[ref])
    if paired_series.is_revision_ref(ref):
        snap = paired_series._snapshot_for_ref(store, ref)  # KeyError for an unknown state
        return str(snap["studio_deck_hash"])
    raise ValueError(f"Unbekanntes Gegner-Deck: {ref!r}")


def resolve_plan(store: StudioStore, plan: ExperimentPlan) -> dict[str, object]:
    """The resolved plan: arms with deck hashes, the table with hashes and pilot fingerprint,
    seeds and tested seats, ``table_hash``; deterministic for the same plan and store."""
    plan.table.ensure_runnable()
    if len(plan.variants) != 1:
        raise ValueError(
            "mehrere Varianten in einem Experiment sind modelliert, aber noch nicht umgesetzt "
            "(heute genau eine Variante je Serie)"
        )
    arms: list[dict[str, object]] = []
    for role, ref in (("base", plan.base), ("variant", plan.variants[0])):
        found = _revision_deck(store, ref.revision_id)
        if found is None:
            raise KeyError(ref.revision_id)
        if found[0] != plan.deck_id:
            raise ValueError(f"{ref.revision_id} ist kein Stand des Decks {plan.deck_id}")
        arms.append({"role": role, "revision_id": ref.revision_id, "deck_hash": found[1]})
    if arms[0]["revision_id"] == arms[1]["revision_id"]:
        raise ValueError("Basis und Variante müssen zwei verschiedene Stände sein")
    tested = plan.table.tested_seats()
    count = -(-plan.budget_pairs // len(tested))
    table = {
        **plan.table.canonical(),
        "opponent_hashes": [_opponent_hash(store, ref) for ref in plan.table.opponents],
        "pilot_fingerprint": pilot_fingerprint(
            policy_version=POLICY_VERSION,
            strength=plan.table.pilot.strength,
            style=plan.table.pilot.style,
        ),
    }
    return {
        "arms": arms,
        "table": table,
        "table_hash": table_hash(table),
        "tested_seats": tested,
        "seeds": {
            "first": plan.first_seed,
            "last": plan.first_seed + count - 1,
            "count": count,
            "rule": "consecutive",
            "starting_seat_rule": "seed % seats",
        },
    }


def check_seed_register(
    store: StudioStore, deck_id: str, purpose: str, first: int, last: int
) -> None:
    """A confirmation never runs on seeds an exploration of the same deck used (M3)."""
    if purpose != "confirmation":
        return
    row = store.connection.execute(
        "SELECT experiment_id, first_seed, last_seed FROM experiment WHERE deck_id = ? "
        "AND purpose = 'exploration' AND first_seed IS NOT NULL AND last_seed IS NOT NULL "
        "AND first_seed <= ? AND last_seed >= ? ORDER BY first_seed LIMIT 1",
        (deck_id, last, first),
    ).fetchone()
    if row is not None:
        raise SeedOverlap(
            f"Bestätigung auf Seeds {first} bis {last} überschneidet die Erkundung "
            f"{row['experiment_id']} (Seeds {row['first_seed']} bis {row['last_seed']}); "
            "eine Bestätigung braucht neue Seeds"
        )


def _insert(
    store: StudioStore, row: Mapping[str, object], arms: Sequence[Mapping[str, object]]
) -> None:
    db = store.connection
    db.execute(
        "INSERT INTO experiment(experiment_id, deck_id, question, question_kind, purpose, "
        "base_revision_id, plan_sha, table_hash, first_seed, last_seed, series_id, engine_pin, "
        "bridge_jar_sha256, bridge_state, pilot_fingerprint, decision, decision_at, "
        "decision_note, decision_tested, decision_previous_revision_id, created_at) "
        "VALUES (:experiment_id, :deck_id, "
        ":question, :question_kind, :purpose, :base_revision_id, :plan_sha, :table_hash, "
        ":first_seed, :last_seed, :series_id, :engine_pin, :bridge_jar_sha256, :bridge_state, "
        ":pilot_fingerprint, :decision, :decision_at, :decision_note, :decision_tested, "
        ":decision_previous_revision_id, "
        ":created_at)",
        {
            "question_kind": None,
            "plan_sha": None,
            "table_hash": None,
            "series_id": None,
            "engine_pin": None,
            "bridge_jar_sha256": None,
            "bridge_state": None,
            "pilot_fingerprint": None,
            "decision": "open",
            "decision_at": None,
            "decision_note": None,
            "decision_tested": None,
            "decision_previous_revision_id": None,
            **row,
        },
    )
    db.executemany(
        "INSERT OR IGNORE INTO experiment_arm(experiment_id, role, revision_id, deck_hash) "
        "VALUES (?, ?, ?, ?)",
        [(row["experiment_id"], a["role"], a["revision_id"], a.get("deck_hash")) for a in arms],
    )


def _row_from_record(
    record: Mapping[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    plan = record["plan"]
    resolved = record["resolved"]
    if not isinstance(plan, dict) or not isinstance(resolved, dict):
        raise ValueError("plan record without plan")
    seeds = resolved["seeds"]
    table = resolved["table"]
    provenance = record.get("provenance")
    prov = provenance if isinstance(provenance, dict) else {}
    arms = [dict(a) for a in resolved["arms"]] if isinstance(resolved["arms"], list) else []
    if not isinstance(seeds, dict) or not isinstance(table, dict) or len(arms) != 2:
        raise ValueError("plan record incomplete")
    row: dict[str, object] = {
        "experiment_id": str(record["experiment_id"]),
        "deck_id": str(plan["deck_id"]),
        "question": str(plan["question"]),
        "question_kind": str(plan["question_kind"]),
        "purpose": str(plan["purpose"]),
        "base_revision_id": str(arms[0]["revision_id"]),
        "plan_sha": str(record["plan_sha"]),
        "table_hash": str(resolved["table_hash"]),
        "first_seed": int(str(seeds["first"])),
        "last_seed": int(str(seeds["last"])),
        "engine_pin": prov.get("engine_pin"),
        "bridge_jar_sha256": prov.get("bridge_jar_sha256"),
        "bridge_state": prov.get("bridge_state"),
        "pilot_fingerprint": table.get("pilot_fingerprint"),
        "created_at": str(record["created_at"]),
    }
    return row, arms


#: Starts the paired series of a plan from its settings (keyword arguments of ``start_series``).
SeriesStarter = Callable[[dict[str, object]], paired_series.PairedSeriesJob]


def _default_starter(store: StudioStore, data_path: Path) -> SeriesStarter:
    def start(settings: dict[str, object]) -> paired_series.PairedSeriesJob:
        return paired_series.paired_series_manager.start_series(store, data_path, **settings)  # type: ignore[arg-type]

    return start


def start_experiment(
    store: StudioStore,
    data_folder: str | Path,
    plan: ExperimentPlan,
    *,
    start_series: SeriesStarter | None = None,
) -> dict[str, object]:
    """Resolve and write the plan, index it, then start its paired series.

    ``start_series`` gets the series settings of the plan and starts the series; the caller
    (web route, CLI) adds its execution settings there, so this module never sets how many
    games share an engine process (the reviewed list of batch callers, #1170).

    The plan file exists before the first game; a start that fails removes the plan and its
    index rows again. The caller declares the write to the cache (``cache.write``)."""
    from commander_lab.bridge_qualification import bridge_qualification

    data_path = Path(data_folder).resolve()
    raw_plan = plan.model_dump(by_alias=True, mode="json")
    resolved = resolve_plan(store, plan)
    seeds = cast(dict[str, object], resolved["seeds"])
    check_seed_register(
        store, plan.deck_id, plan.purpose, int(str(seeds["first"])), int(str(seeds["last"]))
    )
    sha = plan_sha(raw_plan, resolved)
    with _SEQ_LOCK:
        seq = next(_SEQ)
    experiment_id = validate_experiment_id(f"exp-{int(time.time())}-{seq}-{sha[:10]}")
    qualification = bridge_qualification()
    record: dict[str, object] = {
        "schema": SCHEMA_RECORD,
        "data_class": DATA_CLASS,
        "experiment_id": experiment_id,
        "created_at": now_utc(),
        "plan": raw_plan,
        "resolved": resolved,
        "plan_sha": sha,
        "provenance": {
            "engine_pin": engine_state(data_path).get("pin"),
            "bridge_state": qualification.get("status"),
            "bridge_jar_sha256": None,  # the series records the JAR it played with
        },
    }
    folder = experiments_folder(data_path) / experiment_id
    _write_json(folder / "plan.json", record)
    row, arms = _row_from_record(record)
    try:
        _insert(store, row, arms)
        store.connection.commit()
        starter = start_series or _default_starter(store, data_path)
        job = starter(
            dict(
                base_revision_id=str(arms[0]["revision_id"]),
                variant_revision_id=str(arms[1]["revision_id"]),
                pod="table",
                opponent_ids=list(plan.table.opponents),
                budget_pairs=plan.budget_pairs,
                look_every_pairs=plan.look_every_pairs,
                base_seed=plan.first_seed,
                rotate_seats=plan.table.seat_policy == "rotate",
                table_seats=plan.table.seats,
                threshold_pp=plan.threshold_pp,
                significance_level=plan.significance_level,
                purpose=plan.purpose,
                experiment={
                    "experiment_id": experiment_id,
                    "plan_sha": sha,
                    "table_hash": resolved["table_hash"],
                },
            )
        )
    except Exception:
        store.connection.rollback()
        with store.connection:
            store.connection.execute(
                "DELETE FROM experiment_arm WHERE experiment_id = ?", (experiment_id,)
            )
            store.connection.execute(
                "DELETE FROM experiment WHERE experiment_id = ?", (experiment_id,)
            )
        shutil.rmtree(folder, ignore_errors=True)
        raise
    _write_json(folder / "run.json", {"experiment_id": experiment_id, "series_id": job.series_id})
    with store.connection:
        store.connection.execute(
            "UPDATE experiment SET series_id = ?, bridge_jar_sha256 = ? WHERE experiment_id = ?",
            (job.series_id, job.bridge_jar_sha256, experiment_id),
        )
    return {
        "experiment_id": experiment_id,
        "plan_sha": sha,
        "table_hash": resolved["table_hash"],
        "seeds": seeds,
        "tested_seats": resolved["tested_seats"],
        "arms": arms,
        "series_id": job.series_id,
        "data_class": DATA_CLASS,
    }


def decide(
    store: StudioStore,
    data_folder: str | Path,
    experiment_id: str,
    decision: Literal["adopted", "rejected"],
    note: str = "",
) -> dict[str, object]:
    """Adopt (``main`` := variant) or reject the variant; row and ``decision.json`` together.

    Adopting without a counted result is recorded as untested. The caller declares the write
    (``cache.write`` with DECKS and SIMULATION)."""
    validate_experiment_id(experiment_id)
    db = store.connection
    row = db.execute(f"{EXPERIMENT_SELECT} WHERE e.experiment_id = ?", (experiment_id,)).fetchone()
    if row is None:
        raise KeyError(experiment_id)
    if row["plan_sha"] is None:
        raise DecisionRefused("eine Alt-Serie ohne Plan kann nicht übernommen werden")
    if row["decision"] != "open":
        raise DecisionRefused(f"Experiment ist bereits entschieden ({row['decision']})")
    if row["variant_revision_id"] is None:
        raise DecisionRefused("Experiment ohne Variante")
    variant_id = str(row["variant_revision_id"])
    found = _revision_deck(store, variant_id)
    if decision == "adopted" and (found is None or found[0] != row["deck_id"]):
        raise DecisionRefused(f"{variant_id} ist kein Stand des Decks {row['deck_id']}")
    previous = _main_revision(store, str(row["deck_id"]))
    if decision == "adopted" and previous != row["base_revision_id"]:
        # never overwrite a base that moved since the plan (another adoption, a saved state)
        raise DecisionRefused(
            f"main steht nicht mehr auf der Basis des Experiments ({row['base_revision_id']}), "
            f"sondern auf {previous}; nichts wurde überschrieben"
        )
    entry = entry_for_experiment(data_folder, row)
    tested = bool(entry["counts_as_result"])
    decided_at = now_utc()
    payload: dict[str, object] = {
        "schema": SCHEMA_DECISION,
        "experiment_id": experiment_id,
        "decision": decision,
        "decided_at": decided_at,
        "note": note,
        "tested": tested,
        "branch": "main" if decision == "adopted" else None,
        "revision_id": variant_id,
        "previous_revision_id": previous if decision == "adopted" else None,
    }
    with db:
        # conditional writes: what was read above must still hold inside the transaction
        changed = db.execute(
            "UPDATE experiment SET decision = ?, decision_at = ?, decision_note = ?, "
            "decision_tested = ?, decision_previous_revision_id = ? "
            "WHERE experiment_id = ? AND decision = 'open'",
            (
                decision,
                decided_at,
                note,
                int(tested),
                payload["previous_revision_id"],
                experiment_id,
            ),
        ).rowcount
        if changed != 1:
            raise DecisionRefused("Experiment wurde inzwischen entschieden; nichts geändert")
        if decision == "adopted":
            moved = db.execute(
                "UPDATE deck_branch SET revision_id = ? WHERE deck_id = ? AND branch = 'main' "
                "AND revision_id = ?",
                (variant_id, row["deck_id"], row["base_revision_id"]),
            ).rowcount
            if moved != 1:
                raise DecisionRefused(
                    "main hat sich inzwischen bewegt und steht nicht mehr auf der Basis; "
                    "nichts wurde überschrieben"
                )
        # inside the transaction: a decision file that cannot be written undoes the row
        _write_json(experiments_folder(data_folder) / experiment_id / "decision.json", payload)
    return payload


def _main_revision(store: StudioStore, deck_id: str) -> str | None:
    row = store.connection.execute(
        "SELECT revision_id FROM deck_branch WHERE deck_id = ? AND branch = 'main'", (deck_id,)
    ).fetchone()
    return None if row is None else str(row[0])


def undo_decision(
    store: StudioStore, data_folder: str | Path, experiment_id: str
) -> dict[str, object]:
    """Take a decision back: after an adoption ``main`` returns to the stored previous state,
    but only while ``main`` still is the adopted variant. The experiment is open again; the
    undone decision stays in ``decision.json``. The caller declares the write."""
    validate_experiment_id(experiment_id)
    db = store.connection
    row = db.execute(f"{EXPERIMENT_SELECT} WHERE e.experiment_id = ?", (experiment_id,)).fetchone()
    if row is None:
        raise KeyError(experiment_id)
    if row["decision"] not in ("adopted", "rejected"):
        raise DecisionRefused("Experiment ist nicht entschieden, nichts zurückzunehmen")
    previous = row["decision_previous_revision_id"]
    if row["decision"] == "adopted":
        current = _main_revision(store, str(row["deck_id"]))
        if current != row["variant_revision_id"] or previous is None:
            raise DecisionRefused(
                f"main steht nicht mehr auf der übernommenen Variante (jetzt {current}); "
                "nichts wurde zurückgesetzt"
            )
    folder = experiments_folder(data_folder) / experiment_id
    undone = _read_json(folder / "decision.json")
    payload: dict[str, object] = {
        "schema": SCHEMA_DECISION,
        "experiment_id": experiment_id,
        "decision": "undone",
        "undone_at": now_utc(),
        "undone": undone,
        "restored_revision_id": previous if row["decision"] == "adopted" else None,
    }
    with db:
        changed = db.execute(
            "UPDATE experiment SET decision = 'open', decision_at = NULL, decision_note = NULL, "
            "decision_tested = NULL, decision_previous_revision_id = NULL "
            "WHERE experiment_id = ? AND decision = ?",
            (experiment_id, row["decision"]),
        ).rowcount
        if changed != 1:
            raise DecisionRefused("Entscheidung wurde inzwischen geändert; nichts zurückgesetzt")
        if row["decision"] == "adopted":
            moved = db.execute(
                "UPDATE deck_branch SET revision_id = ? WHERE deck_id = ? AND branch = 'main' "
                "AND revision_id = ?",
                (previous, row["deck_id"], row["variant_revision_id"]),
            ).rowcount
            if moved != 1:
                raise DecisionRefused(
                    "main steht nicht mehr auf der übernommenen Variante; nichts zurückgesetzt"
                )
        _write_json(folder / "decision.json", payload)
    return payload


def _legacy_row(
    store: StudioStore, raw: Mapping[str, object]
) -> tuple[dict[str, object], list[dict[str, object]]]:
    base, variant = str(raw["base_ref"]), str(raw["variant_ref"])
    found = _revision_deck(store, base) or _revision_deck(store, variant)
    plan = raw.get("seed_plan")
    seed_plan = plan if isinstance(plan, dict) else {}
    first, count = seed_plan.get("first_seed"), seed_plan.get("seeds_planned")
    ok = type(first) is int and type(count) is int and count > 0
    purpose = seed_plan.get("purpose")
    row: dict[str, object] = {
        "experiment_id": str(raw["series_id"]),
        "deck_id": found[0] if found else "",
        "question": LEGACY_QUESTION,
        "purpose": purpose if isinstance(purpose, str) else "unspecified",
        "base_revision_id": base,
        "first_seed": first if ok else None,
        "last_seed": int(str(first)) + int(str(count)) - 1 if ok else None,
        "series_id": str(raw["series_id"]),
        "created_at": str(raw.get("created_at") or ""),
    }
    arms: list[dict[str, object]] = [
        {"role": "base", "revision_id": base, "deck_hash": None},
        {"role": "variant", "revision_id": variant, "deck_hash": None},
    ]
    return row, arms


class RebuildRefused(RuntimeError):
    """A rebuild would lose indexed experiments whose plan files are gone."""


def rebuild_index(store: StudioStore, data_folder: str | Path) -> dict[str, int]:
    """Rebuild ``experiment``/``experiment_arm`` from the files (plan, run, decision; old
    ``*.paired.json`` without a plan as legacy rows). Everything is read first; when an indexed
    experiment has no readable plan file any more, nothing is replaced (``RebuildRefused``).
    The caller declares the write."""
    data_path = Path(data_folder).resolve()
    counts = {"experiments": 0, "legacy": 0, "skipped": 0}
    linked: set[str] = set()
    rows: list[tuple[dict[str, object], list[dict[str, object]]]] = []
    folder = experiments_folder(data_path)
    for plan_file in sorted(folder.glob("exp-*/plan.json")) if folder.is_dir() else []:
        record = _read_json(plan_file)
        try:
            if record is None or record.get("schema") != SCHEMA_RECORD:
                raise ValueError("not a plan record")
            validate_experiment_id(str(record["experiment_id"]))
            if plan_file.parent.name != record["experiment_id"]:
                raise ValueError("folder and id differ")
            row, arms = _row_from_record(record)
        except (KeyError, TypeError, ValueError):
            counts["skipped"] += 1
            continue
        run = _read_json(plan_file.parent / "run.json") or {}
        series_id = run.get("series_id")
        if isinstance(series_id, str):
            row["series_id"] = series_id
            linked.add(series_id)
            series_raw = read_series_file(games_folder(data_path) / f"{series_id}.paired.json")
            if series_raw is not None:
                jar = series_raw.get("bridge_jar_sha256")
                row["bridge_jar_sha256"] = jar if isinstance(jar, str) else None
        decision = _read_json(plan_file.parent / "decision.json") or {}
        if decision.get("schema") == SCHEMA_DECISION and decision.get("decision") in (
            "adopted",
            "rejected",
        ):
            row["decision"] = decision["decision"]
            row["decision_at"] = decision.get("decided_at")
            row["decision_note"] = decision.get("note")
            row["decision_tested"] = int(bool(decision.get("tested")))
            row["decision_previous_revision_id"] = decision.get("previous_revision_id")
        rows.append((row, arms))
        counts["experiments"] += 1
    games = games_folder(data_path)
    for path in sorted(games.glob("paired-*.paired.json")) if games.is_dir() else []:
        raw = read_series_file(path)
        if raw is None:
            continue
        if raw["series_id"] in linked or isinstance(raw.get("experiment"), dict):
            continue
        rows.append(_legacy_row(store, raw))
        counts["legacy"] += 1
    db = store.connection
    found = {str(row["experiment_id"]) for row, _arms in rows}
    lost = [
        str(r[0])
        for r in db.execute("SELECT experiment_id FROM experiment WHERE plan_sha IS NOT NULL")
        if str(r[0]) not in found
    ]
    if lost:
        raise RebuildRefused(
            f"{len(lost)} Experiment(e) im Index haben keine lesbare Plan-Datei mehr "
            f"(z. B. {lost[0]}); der Index bleibt unverändert"
        )
    with db:
        db.execute("DELETE FROM experiment_arm")
        db.execute("DELETE FROM experiment")
        for row, arms in rows:
            _insert(store, row, arms)
    return counts

"""``import-all``: every data layer of one commander from a few files, in the right order.

The steps are fixed: inventory workbook and public card data are required (the run stops when
one fails); everything else is optional. An optional input that is not delivered is reported as
``NICHT GELIEFERT`` and the run continues; an optional step that fails is reported as ``FEHLER``
and the run continues as well, so one bad file does not hide the rest. The last step is the
completeness report (``completeness.py``).

The research folder is searched in itself and in its direct subfolders for the files the
importers know (signals, tagger bulk, rulings). Files nothing reads are listed with the reason.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypedDict

from . import (
    catalog,
    completeness,
    decklist_import,
    importers,
    research_import,
    rulings,
    signals,
    universe,
)
from .builder import list_commanders
from .store import StudioStore, now_utc

STEP_OK = "OK"
STEP_NOT_DELIVERED = "NICHT GELIEFERT"
STEP_FAILED = "FEHLER"
STEP_WARNING = "WARNUNG"

TAGGER_PATTERN = "card_tagger_bulk*.csv"
RULINGS_PATTERNS = ("card_rulings*.jsonl", "scryfall_rulings*.jsonl")

# Files of a research folder that no importer reads, and why (checked in this order).
_NO_CONSUMER: tuple[tuple[str, str], ...] = (
    (
        r"mtgjson_printings_.*\.jsonl",
        "kein Abnehmer: Drucke (MTGJSON) werden im Studio nicht gelesen; Preise sind ausgeschlossen",
    ),
    (
        r"coverage_matrix_.*\.csv",
        "kein Abnehmer: Abdeckungszählung der Lieferung (Auswertung, keine Kartendaten)",
    ),
    (
        r"playgroup_commander_stats\.csv",
        "kein Abnehmer: Kennzahlen je Commander; die Signaltabelle führt nur Kartenwerte",
    ),
    (r"topdeck_commander_presence\.csv", "kein Abnehmer: Präsenz je Commander, keine Kartenwerte"),
    (
        r"edhtop16_probe_.*\.csv",
        "kein Abnehmer: Probeabruf mit anderen Spalten; die Spielraten stehen in "
        "edhtop16_commander_signals.csv",
    ),
    (
        r".*decklist_inclusion_.*\.csv",
        "kein Abnehmer: aus dem Korpus berechnete Ausgabe, keine Eingabe",
    ),
    (r".*gap_matrix.*\.json", "kein Abnehmer: Ausgabe von `sources --gap-report`"),
    (r".*role_coverage.*\.(json|md)", "kein Abnehmer: Messbericht"),
    (
        r"topdeck_.*_decks\.csv",
        "Turnierlisten eines anderen Commanders (gelesen wird nur die des gewählten)",
    ),
)
_IGNORED = frozenset({"README.md"})
NOT_READ = "nicht gelesen (Lauf abgebrochen)"


class StepRecord(TypedDict):
    step: str
    status: str
    inputs: list[str]
    message: str
    result: dict[str, object]


class ImportAllError(Exception):
    """A required step failed; the report written so far names it."""


class UnknownCommanderError(ImportAllError):
    """The commander is not in the collection; no report is computed for it."""


def _record(
    steps: list[StepRecord],
    step: str,
    status: str,
    *,
    inputs: Sequence[str] = (),
    message: str = "",
    result: dict[str, object] | None = None,
) -> None:
    steps.append(
        {
            "step": step,
            "status": status,
            "inputs": list(inputs),
            "message": message,
            "result": result or {},
        }
    )


def _folders(research: Path | None) -> list[Path]:
    if research is None or not research.is_dir():
        return []
    return [research, *sorted(p for p in research.iterdir() if p.is_dir())]


def _unused_files(
    folders: Sequence[Path], consumed: set[Path], *, aborted: bool = False
) -> list[dict[str, object]]:
    grouped: dict[str, list[str]] = {}
    for folder in folders:
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name in _IGNORED or path in consumed:
                continue
            reason = next(
                (why for pattern, why in _NO_CONSUMER if re.fullmatch(pattern, path.name)),
                "nicht erkannt: kein Importer kennt diese Datei",
            )
            if aborted:
                reason = NOT_READ
            grouped.setdefault(reason, []).append(f"{folder.name}/{path.name}")
    return [
        {"reason": reason, "files": files, "count": len(files)}
        for reason, files in sorted(grouped.items())
    ]


def _guarded(
    steps: list[StepRecord],
    step: str,
    inputs: Sequence[str],
    run: Callable[[], dict[str, object]],
    *,
    required: bool = False,
) -> dict[str, object] | None:
    """Run one step; a failure is recorded, and raised again for a required step."""
    try:
        result = run()
    except Exception as error:
        text = f"{type(error).__name__}: {error}"
        _record(steps, step, STEP_FAILED, inputs=inputs, message=text)
        if required:
            raise ImportAllError(f"{step}: {text}") from error
        return None
    _record(steps, step, STEP_OK, inputs=inputs, result=result)
    return result


def _summary(result: dict[str, object]) -> dict[str, object]:
    """The counts of an importer result. A list (card names, mostly) becomes its length under
    ``<key>_count``: the report holds counts only, the names stay in the importer's own output."""
    short: dict[str, object] = {}
    for key, value in result.items():
        if isinstance(value, list):
            short[f"{key}_count"] = len(value)
        else:
            short[key] = value
    return short


def import_all(
    store: StudioStore,
    *,
    commander: str,
    collection: Path,
    scryfall: Path,
    research: Path | None,
    decklists: Sequence[Path] = (),
    playgroup_atlas: Path | None = None,
    disambiguation: Path | None = None,
    force: bool = False,
) -> dict[str, object]:
    """Run every step and return the completeness report (also see ``completeness``).

    ``stopped_at`` in the report names the required step that failed; the report then holds
    what the store has. The caller writes it."""
    steps: list[StepRecord] = []
    consumed: set[Path] = set()
    folders = _folders(research)
    stopped_at: str | None = None
    name = commander.strip()
    try:
        _guarded(
            steps,
            "inventory",
            [collection.name],
            lambda: _summary(dict(importers.import_inventory_workbook(store, collection))),
            required=True,
        )
        _guarded(
            steps,
            "public_card_facts",
            [scryfall.name],
            lambda: _summary(
                catalog.import_scryfall_oracle(store, scryfall, disambiguation_path=disambiguation)
            ),
            required=True,
        )
        name = signals.resolve_commander_name(store, commander)
        _require_commander(store, name)
        _deck_steps(store, steps, name, decklists)
        _research_steps(store, steps, consumed, folders, research, name, force)
        if playgroup_atlas is None:
            _record(steps, "playgroup_atlas", STEP_NOT_DELIVERED, message="--playgroup-atlas fehlt")
        else:
            _guarded(
                steps,
                "playgroup_atlas",
                [playgroup_atlas.name],
                lambda: _summary(dict(importers.import_playgroup_atlas(store, playgroup_atlas))),
            )
        _guarded(steps, "relink_corpus", [], lambda: _summary(catalog.relink_corpus(store)))
        _profile_step(store, steps, name)
    except UnknownCommanderError:
        raise
    except ImportAllError as error:
        stopped_at = str(error)
    return _report(store, name, steps, folders, consumed, stopped_at, research)


def _require_commander(store: StudioStore, commander: str) -> None:
    found = store.connection.execute(
        "SELECT 1 FROM card_fact f JOIN inventory i USING (card_id) WHERE f.oracle_name = ?",
        (commander,),
    ).fetchone()
    if found is not None:
        return
    names = [
        str(item["name"])
        for item in list_commanders(store, include_collection=True)
        if item["in_collection"]
    ]
    shown = ", ".join(names[:30]) + (f" (+{len(names) - 30} weitere)" if len(names) > 30 else "")
    raise UnknownCommanderError(
        f"Der Commander {commander!r} steht nicht in der Sammlung. Verfügbare Commander: "
        f"{shown or 'keine gefunden'}"
    )


def _deck_steps(
    store: StudioStore, steps: list[StepRecord], commander: str, decklists: Sequence[Path]
) -> None:
    if not decklists:
        _record(steps, "decklists", STEP_NOT_DELIVERED, message="--decklists fehlt")
        return
    for folder in decklists:
        step = f"decklists:{folder.name}"
        if not folder.is_dir():
            _record(steps, step, STEP_NOT_DELIVERED, inputs=[str(folder)], message="Ordner fehlt")
            continue

        def run(folder: Path = folder) -> dict[str, object]:
            form = decklist_import.detect_format(folder)
            with store.importing_for(commander):
                result = decklist_import.import_decklists(
                    store, folder, format=form, commander=commander
                )
            return {"format": form, **_summary(result)}

        _guarded(steps, step, [folder.name], run)


def _research_steps(
    store: StudioStore,
    steps: list[StepRecord],
    consumed: set[Path],
    folders: list[Path],
    research: Path | None,
    commander: str,
    force: bool,
) -> None:
    if not folders:
        message = "Ordner fehlt" if research is not None else "--research fehlt"
        for step in ("signals", "tagger_roles", "rulings"):
            _record(steps, step, STEP_NOT_DELIVERED, message=message)
        return
    signal_folders = [folder for folder in folders if signals.has_signal_files(folder, commander)]
    if not signal_folders:
        _record(steps, "signals", STEP_NOT_DELIVERED, message="keine Signaldateien gefunden")
    for folder in signal_folders:

        def run_signals(folder: Path = folder) -> dict[str, object]:
            return signals.import_signals(store, folder, commander=commander)

        result = _guarded(steps, f"signals:{folder.name}", [folder.name], run_signals)
        if result is None:
            continue
        files = result.get("files")
        if isinstance(files, dict):
            for report in files.values():
                consumed |= {folder / part for part in report["parts"]}
            # the full file reports stay in the signal import result, not in this report
            result["files"] = {
                key: {k: v for k, v in value.items() if k != "sources"}
                for key, value in files.items()
            }
        if result.get("warnings"):
            steps[-1]["status"] = STEP_WARNING
    taggers = [path for folder in folders for path in sorted(folder.glob(TAGGER_PATTERN))]
    if not taggers:
        _record(steps, "tagger_roles", STEP_NOT_DELIVERED, message=f"keine Datei {TAGGER_PATTERN}")
    for path in taggers:
        consumed.add(path)
        date = research_import.capture_date(path.parent / "README.md", path.stem)

        def run_tagger(path: Path = path, date: str | None = date) -> dict[str, object]:
            return _summary(
                research_import.import_tagger_roles(store, path, fetched_at=date, force=force)
            )

        _guarded(steps, f"tagger_roles:{path.name}", [path.name], run_tagger)
    ruling_files = sorted(
        {
            path
            for folder in folders
            for pattern in RULINGS_PATTERNS
            for path in folder.glob(pattern)
        }
    )
    if not ruling_files:
        _record(steps, "rulings", STEP_NOT_DELIVERED, message="keine Rulings-Datei")
    else:
        consumed |= set(ruling_files)
        _guarded(
            steps,
            "rulings",
            [path.name for path in ruling_files],
            lambda: _summary(rulings.import_rulings(store, ruling_files)),
        )


def _profile_step(store: StudioStore, steps: list[StepRecord], commander: str) -> None:
    """A default universe profile for the commander's source decks, once decks exist."""
    bound = int(
        store.connection.execute(
            "SELECT COUNT(*) FROM commander_binding WHERE kind = 'corpus_deck' "
            "AND commander_name = ?",
            (commander,),
        ).fetchone()[0]
    )
    if bound == 0:
        _record(steps, "universe_profile", STEP_NOT_DELIVERED, message="keine Quell-Decks")
        return
    profile = f"Alle Decks: {commander}"
    existing = {str(p["name"]) for p in universe.list_profiles(store)}
    if profile in existing:
        _record(steps, "universe_profile", STEP_OK, message="Profil besteht bereits")
        return
    _guarded(
        steps,
        "universe_profile",
        [],
        lambda: {
            "name": profile,
            "version": universe.save_profile(store, profile, {"commanders": [commander]})[
                "version"
            ],
        },
    )


def _report(
    store: StudioStore,
    commander: str,
    steps: list[StepRecord],
    folders: list[Path],
    consumed: set[Path],
    stopped_at: str | None,
    research: Path | None,
) -> dict[str, object]:
    readmes = [folder / "README.md" for folder in folders if (folder / "README.md").is_file()]
    layers, pool, collection = completeness.build_layers(store, commander, readmes=readmes)
    failed = [s for s in steps if s["status"] == STEP_FAILED]
    warnings = [
        f"{s['step']}: {s['message']}" for s in steps if s["status"] == STEP_FAILED and s["message"]
    ]
    if pool is None:
        warnings.append(
            "der Commander steht nicht in der Sammlung: die legalen Karten sind unbekannt"
        )
    return {
        "schema": completeness.REPORT_SCHEMA,
        "generated_at": now_utc(),
        "commander": commander,
        "commander_in_collection": pool is not None,
        "legal_pool_cards": pool,
        "collection_cards": collection,
        "legality": completeness.legality_details(store),
        "stopped_at": stopped_at,
        "steps": steps,
        "failed_steps": len(failed),
        "layers": layers,
        "unused_files": _unused_files(folders, consumed, aborted=stopped_at is not None),
        "warnings": warnings,
    }

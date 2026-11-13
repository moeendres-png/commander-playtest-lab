"""One checked import: every importer in the right order for one commander.

``import-all`` runs the existing importers (collection, public card facts, roles, rulings,
deck lists, usage signals, marks) inside the commander scoping of
``StudioStore.importing_for``, skips each step that was not given (``NOT_PROVIDED``) and
ends with the counts-only data report and a completeness table per data layer: rows, cards
of the commander's legal pool covered, pool size, and the status COMPLETE, PARTIAL or
MISSING. A layer with no row is MISSING, a layer that covers the whole pool is COMPLETE,
anything between is PARTIAL. Nothing here reads a network; a figure that cannot be told is
missing, never 0 covered.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TypedDict

from . import (
    builder,
    catalog,
    decklist_import,
    importers,
    repo_import,
    roles,
    rulings,
    signals,
    strength_view,
)
from .data_report import data_report
from .marks import import_owner_marks
from .store import BOUND_ELSEWHERE, StudioStore

NOT_PROVIDED = "NOT_PROVIDED"
IMPORTED = "IMPORTED"
FAILED = "FAILED"
SKIPPED = "SKIPPED_AFTER_ERROR"
COMPLETE = "COMPLETE"
PARTIAL = "PARTIAL"
MISSING = "MISSING"

EXIT_STEP_FAILED = 1
EXIT_POOL_MISMATCH = 3
EXIT_COMMANDER_UNKNOWN = 4
PRESENT = "PRESENT"


class StepResult(TypedDict):
    step: str
    status: str
    detail: str


class LayerResult(TypedDict):
    key: str
    layer: str
    rows: int
    covered: int
    pool: int | None
    status: str


class SignalRows(TypedDict):
    """Stored usage-signal rows: this commander's (own name plus commander-independent rows)
    and those of other commanders."""

    for_commander: int
    other_rows: int
    other_commanders: int


class ImportAllResult(TypedDict):
    commander: str
    steps: list[StepResult]
    failed: bool
    pool_size: int | None
    expected_pool: int | None
    pool_ok: bool
    signal_rows: SignalRows
    layers: list[LayerResult]
    data_report: dict[str, object]


_Action = Callable[[StudioStore], object]
_RESEARCH = Path(__file__).resolve().parents[3] / "data" / "research"
FROM_REPO_NEEDS_SCRYFALL = (
    "--from-repo braucht --scryfall <Datei>: die öffentlichen Kartenfakten (Scryfall-Oracle-"
    "Datei) liegen nicht im Repo und werden nicht heruntergeladen. Lade die Datei "
    "„Oracle Cards“ von scryfall.com/docs/api/bulk-data und gib sie mit --scryfall an."
)


def default_signal_folders() -> list[Path]:
    """Every folder under ``data/research`` that holds signal files, in name order, and
    ``data/research`` itself when it holds a counted deck-list file
    (``<slug>_decklist_inclusion_<date>.csv``)."""
    if not _RESEARCH.is_dir():
        return []
    folders = [
        path
        for path in sorted(_RESEARCH.iterdir())
        if path.is_dir() and signals.has_signal_files(path)
    ]
    if signals.has_decklist_files(_RESEARCH):
        folders.append(_RESEARCH)
    return folders


def default_rulings_files() -> list[Path]:
    """The curated rulings files of the collection package under ``data/research``."""
    folder = _RESEARCH / "deckbuilder_1655"
    if not folder.is_dir():
        return []
    return sorted(folder.glob("card_rulings_*.jsonl"))


def _status(rows: int, covered: int, pool: int) -> str:
    if rows <= 0 or pool <= 0:
        return MISSING
    return COMPLETE if covered >= pool else PARTIAL


def _count(store: StudioStore, sql: str, params: Sequence[object] = ()) -> int:
    return int(store.connection.execute(sql, tuple(params)).fetchone()[0])


def _summary(result: object) -> str:
    """A short, count-only line of an importer result."""
    if isinstance(result, dict):
        numbers = {
            key: value
            for key, value in result.items()
            if isinstance(value, int) and not isinstance(value, bool)
        }
        if numbers:
            return ", ".join(f"{key}={value}" for key, value in list(numbers.items())[:6])
    return ""


def _deck_hits(card: dict[str, object]) -> int:
    decks = card["decks"]
    return int(decks.get("all", 0)) if isinstance(decks, dict) else 0


def completeness(store: StudioStore, commander: str) -> tuple[int | None, list[LayerResult]]:
    """The pool size of ``commander`` (None when it is not in the collection) and one entry
    per data layer."""
    layers: list[LayerResult] = []
    try:
        pool = builder.pool_cards(store, [commander], with_signals=False)
    except KeyError:
        pool = None
    raw = pool["cards"] if pool is not None else []
    cards = [dict(card) for card in raw] if isinstance(raw, list) else []
    size = len(cards) if pool is not None else None
    total = size or 0

    def add(key: str, layer: str, rows: int, covered: int) -> None:
        layers.append(
            {
                "key": key,
                "layer": layer,
                "rows": rows,
                "covered": covered,
                "pool": size,
                "status": _status(rows, covered, total),
            }
        )

    add("inventory", "Sammlung (Bestand)", _count(store, "SELECT COUNT(*) FROM inventory"), total)
    add(
        "scryfall",
        "Kartenfakten (Scryfall)",
        _count(store, "SELECT COUNT(*) FROM scryfall_card"),
        sum(1 for card in cards if card["fact_source"] == "scryfall"),
    )
    add(
        "roles",
        "Rollen",
        _count(store, "SELECT COUNT(*) FROM card_role"),
        sum(1 for card in cards if card["roles"]),
    )
    with_rulings = {
        str(row[0])
        for row in store.connection.execute(
            "SELECT DISTINCT f.card_id FROM card_fact f "
            "JOIN card_ruling r ON r.oracle_id = f.oracle_id"
        )
    }
    add(
        "rulings",
        "Regeltexte (Rulings)",
        _count(store, "SELECT COUNT(*) FROM card_ruling"),
        sum(1 for card in cards if str(card["card_id"]) in with_rulings),
    )
    _repo_layers(store, cards, add)
    binding = builder.corpus_binding(store, [commander])
    bound = binding["bound_decks"]
    add(
        "decklists",
        "Quelldecks (Decklisten)",
        bound if isinstance(bound, int) else 0,
        sum(1 for card in cards if _deck_hits(card) > 0),
    )
    try:
        coverage = strength_view.signal_coverage(store, commander)
    except KeyError:
        coverage = {}
    for signal, item in coverage.items():
        add(f"signal:{signal}", f"Signal {signal}", item["rows"], item["pool_cards_with_value"])
    # Marks are optional per card: present (with the count) or not provided, never partial.
    marked = sum(1 for card in cards if card["favorite"] or card["excluded"] or card["note"])
    layers.append(
        {
            "key": "marks",
            "layer": "Markierungen",
            "rows": marked,
            "covered": marked,
            "pool": size,
            "status": PRESENT if marked else NOT_PROVIDED,
        }
    )
    return size, layers


def _repo_layers(
    store: StudioStore,
    cards: list[dict[str, object]],
    add: Callable[[str, str, int, int], None],
) -> None:
    """The layers ``--from-repo`` fills: corpus decks, EDHREC observations, Playgroup atlas."""
    db = store.connection
    ids = {str(card["card_id"]) for card in cards}
    in_corpus = {
        str(row[0])
        for row in db.execute(
            "SELECT DISTINCT f.card_id FROM card_fact f JOIN corpus_deck_card k "
            "ON k.oracle_id = f.oracle_id"
        )
    }
    add(
        "corpus",
        "Korpus (Decks, alle)",
        _count(store, "SELECT COUNT(*) FROM corpus_deck"),
        len(ids & in_corpus),
    )
    observed = {
        str(row[0])
        for row in db.execute("SELECT DISTINCT card_id FROM observation WHERE card_id IS NOT NULL")
    }
    add(
        "observations",
        "EDHREC-Beobachtungen (Themen)",
        _count(store, "SELECT COUNT(*) FROM observation"),
        len(ids & observed),
    )
    atlas = {
        str(row[0])
        for row in db.execute(
            "SELECT DISTINCT f.card_id FROM card_fact f JOIN playgroup_card_atlas a "
            "ON a.card_id = f.card_id OR (a.oracle_id != '' AND a.oracle_id = f.oracle_id)"
        )
    }
    add(
        "playgroup",
        "Playgroup-Atlas",
        _count(store, "SELECT COUNT(*) FROM playgroup_card_atlas"),
        len(ids & atlas),
    )


def signal_rows(store: StudioStore, commander: str) -> SignalRows:
    """Stored signal rows split into this commander's and the other commanders' (counts)."""
    own = _count(
        store, "SELECT COUNT(*) FROM card_signal WHERE commander_name IN (?, '')", (commander,)
    )
    other = _count(
        store, "SELECT COUNT(*) FROM card_signal WHERE commander_name NOT IN (?, '')", (commander,)
    )
    names = _count(
        store,
        "SELECT COUNT(DISTINCT commander_name) FROM card_signal WHERE commander_name NOT IN (?, '')",
        (commander,),
    )
    return {"for_commander": own, "other_rows": other, "other_commanders": names}


_FLAG = {
    "inventory": "",
    "scryfall": ' --scryfall "<Datei>"',
    "roles": ' --roles "<Datei>"',
    "rulings": ' --rulings "<Datei>"',
    "decklists": ' --decklists "<Ordner>"',
    "marks": ' --marks "<Datei>"',
}
_FROM_REPO_LAYERS = frozenset({"corpus", "observations", "playgroup"})


def import_command(layer_key: str, commander: str) -> str:
    """The exact ``import-all`` call that fills one layer (angle brackets: your path)."""
    if layer_key in _FROM_REPO_LAYERS:
        return (
            f'python -m commander_lab.studio import-all --commander "{commander}" '
            '--from-repo --scryfall "<Scryfall-Datei>"'
        )
    flag = _FLAG.get(layer_key, ' --signals "<Ordner>"' if layer_key.startswith("signal:") else "")
    return (
        f'python -m commander_lab.studio import-all --commander "{commander}" '
        f'--inventory "<Sammlung.xlsx>"{flag}'
    )


def layer_overview(store: StudioStore, commander: str) -> dict[str, object]:
    """What the pages show when data is missing: per layer its state and the import call."""
    size, layers = completeness(store, commander)
    return {
        "commander": commander,
        "pool_size": size,
        "layers": [{**item, "command": import_command(item["key"], commander)} for item in layers],
        "signals_command": import_command("signal:", commander),
        "doc": "docs/STUDIO_DECKBUILDER.md, Abschnitt „Alles importieren“",
    }


def _each(
    paths: Sequence[Path], load: Callable[[StudioStore, Path], Mapping[str, object]]
) -> Callable[[StudioStore], object]:
    """One step over several files: the integer counts of every file, summed."""

    def run_all(store: StudioStore) -> object:
        totals: dict[str, int] = {}
        for path in paths:
            for key, value in load(store, path).items():
                if isinstance(value, int) and not isinstance(value, bool):
                    totals[key] = totals.get(key, 0) + value
        return {"files": len(paths), **totals}

    return run_all


def _inventory_action(
    args: argparse.Namespace, repo: repo_import.RepoFiles | None
) -> Callable[[StudioStore], object]:
    def load(store: StudioStore) -> object:
        if args.inventory:
            return importers.import_inventory_workbook(store, args.inventory)
        if repo is None or repo.collection_dir is None:
            raise ValueError("keine Sammlungsdatei: --inventory <Datei> oder --from-repo")
        with tempfile.TemporaryDirectory() as folder:
            workbook = Path(folder) / "collection.xlsx"
            repo_import.build_inventory_workbook(repo.collection_dir, workbook)
            return importers.import_inventory_workbook(store, workbook)

    return load


def _steps(
    args: argparse.Namespace,
    signal_folders: list[Path],
    rulings_files: list[Path],
    repo: repo_import.RepoFiles | None = None,
) -> list[tuple[str, bool, Callable[[StudioStore], object]]]:
    commander: str = args.commander
    # Explicit arguments win over the repository files of the same step.
    role_files = [Path(args.roles)] if args.roles else (repo.roles if repo else [])
    plan: list[tuple[str, bool, Callable[[StudioStore], object]]] = [
        ("Sammlung", True, _inventory_action(args, repo)),
        (
            "Scryfall-Kartenfakten",
            bool(args.scryfall),
            lambda store: catalog.import_scryfall_oracle(store, args.scryfall),
        ),
        (
            "Rollen",
            bool(role_files),
            _each(role_files, lambda store, path: roles.import_roles(store, path)),
        ),
        (
            "Regeltexte",
            bool(rulings_files),
            lambda store: rulings.import_rulings(store, rulings_files),
        ),
        (
            "Decklisten",
            bool(args.decklists),
            lambda store: decklist_import.import_decklists(
                store, args.decklists, format=args.decklist_format, commander=commander
            ),
        ),
    ]
    if repo is not None:
        corpus = repo.corpus_dir
        use_corpus = corpus is not None and not args.decklists
        plan.append(
            (
                "Decklisten-Korpus (Repo)",
                use_corpus,
                lambda store: repo_import.import_corpus(store, corpus or Path()),
            )
        )
        plan.append(
            (
                "Oracle-Zuordnung des Korpus",
                use_corpus,
                lambda store: {
                    key: value
                    for key, value in repo_import.map_corpus_oracle_ids(store.connection).items()
                    if isinstance(value, int)
                },
            )
        )
        plan.append(
            (
                "EDHREC-Beobachtungen (Repo)",
                bool(repo.edhrec_parts),
                _each(
                    repo.edhrec_parts,
                    lambda store, path: importers.import_edhrec_table(store, path),
                ),
            )
        )
        plan.append(
            (
                "Playgroup-Atlas (Repo)",
                bool(repo.playgroup_parts),
                _each(
                    repo.playgroup_parts,
                    lambda store, path: importers.import_playgroup_atlas(store, path),
                ),
            )
        )
    for folder in signal_folders:

        def read(store: StudioStore, folder: Path = folder) -> object:
            return signals.import_signals(store, folder, commander=commander)

        plan.append((f"Signale {folder.name}", True, read))
    if not signal_folders:
        plan.append(("Signale", False, lambda store: {}))
    plan.append(
        ("Markierungen", bool(args.marks), lambda store: import_owner_marks(store, args.marks))
    )
    return plan


def run(args: argparse.Namespace, store: StudioStore) -> ImportAllResult:
    """Run the import and return the full result (steps, pool, layers, data report)."""
    commander = str(args.commander).strip()
    if not commander:
        raise ValueError("a commander name is required")
    args.commander = commander
    repo: repo_import.RepoFiles | None = None
    if getattr(args, "from_repo", False):
        if not args.scryfall:
            raise ValueError(FROM_REPO_NEEDS_SCRYFALL)
        repo = repo_import.RepoFiles.discover(_RESEARCH)
        if not args.inventory and repo.collection_dir is None:
            raise ValueError(
                f"--from-repo: keine Sammlung im Repo ({repo_import.COLLECTION_FOLDER} fehlt); "
                "gib --inventory <Datei> an"
            )
    elif not args.inventory:
        raise ValueError("--inventory <Datei> fehlt (oder --from-repo)")
    if args.signals is None:
        signal_folders = default_signal_folders()
    else:
        signal_folders = [Path(folder) for folder in args.signals]
    if args.rulings is None:
        rulings_files = default_rulings_files()
    else:
        rulings_files = [Path(file) for file in args.rulings]
    steps: list[StepResult] = []
    failed = False
    for name, provided, action in _steps(args, signal_folders, rulings_files, repo):
        if not provided:
            steps.append({"step": name, "status": NOT_PROVIDED, "detail": ""})
            continue
        if failed:
            steps.append({"step": name, "status": SKIPPED, "detail": "an earlier step failed"})
            continue
        try:
            with store.importing_for(commander):
                result = action(store)
            steps.append({"step": name, "status": IMPORTED, "detail": _summary(result)})
        except sqlite3.IntegrityError as error:
            detail = (
                f"belongs to another commander than {commander!r}"
                if BOUND_ELSEWHERE in str(error)
                else str(error)
            )
            steps.append({"step": name, "status": FAILED, "detail": detail})
            failed = True
        except (ValueError, OSError, KeyError) as error:
            steps.append({"step": name, "status": FAILED, "detail": str(error) or repr(error)})
            failed = True
    size, layers = completeness(store, commander)
    expected = args.expect_pool
    return {
        "commander": commander,
        "steps": steps,
        "failed": failed,
        "pool_size": size,
        "expected_pool": expected,
        "pool_ok": expected is None or size == expected,
        "signal_rows": signal_rows(store, commander),
        "layers": layers,
        "data_report": data_report(store),
    }


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    cells = [[str(item) for item in row] for row in rows]
    widths = [max(len(h), *(len(row[i]) for row in cells)) for i, h in enumerate(headers)]

    def line(items: Sequence[str]) -> str:
        return "  ".join(item.ljust(widths[i]) for i, item in enumerate(items)).rstrip()

    return "\n".join([line(headers), line(["-" * w for w in widths]), *(line(r) for r in cells)])


def render(result: ImportAllResult) -> str:
    """Steps, data report and completeness table as text."""
    steps = result["steps"]
    layers = result["layers"]
    pool = result["pool_size"]
    parts = [
        f"Import für {result['commander']}",
        _table(
            ["Schritt", "Status", "Angaben"],
            [(s["step"], s["status"], s["detail"]) for s in steps],
        ),
        "",
        "Datenbericht (nur Zählungen):",
        json.dumps(result["data_report"], indent=2, ensure_ascii=False),
        "",
        "Vollständigkeit je Schicht (Karten des legalen Pools: abgedeckt / Poolgröße):",
        _table(
            ["Schicht", "Zeilen", "Pool abgedeckt", "Status"],
            [
                (
                    layer["layer"],
                    layer["rows"],
                    "unbekannt"
                    if layer["pool"] is None
                    else f"{layer['covered']} / {layer['pool']}",
                    layer["status"],
                )
                for layer in layers
            ],
        ),
        "",
        f"Poolgröße: {'unbekannt (Commander nicht in der Sammlung)' if pool is None else pool}",
    ]
    rows = result["signal_rows"]
    parts.append(
        f"Signalzeilen gespeichert: für {result['commander']} {rows['for_commander']} "
        f"(mit den Zeilen ohne Commander), für andere Commander {rows['other_rows']} "
        f"({rows['other_commanders']} Commander). Zeilen anderer Commander werden "
        "gespeichert, aber nur bei diesen Commandern angezeigt."
    )
    if result["expected_pool"] is not None:
        verdict = "stimmt" if result["pool_ok"] else "STIMMT NICHT"
        parts.append(f"Erwartete Poolgröße {result['expected_pool']}: {verdict}")
    return "\n".join(parts)


def run_command(args: argparse.Namespace) -> int:
    """The ``import-all`` command; returns the process exit code."""
    store = StudioStore.open(args.data)
    try:
        try:
            result = run(args, store)
        except ValueError as error:
            raise SystemExit(f"import-all: {error}") from None
        print(render(result))
        if result["failed"]:
            print("import-all: ein Schritt ist fehlgeschlagen.", file=sys.stderr)
            return EXIT_STEP_FAILED
        if result["pool_size"] is None:
            print(
                f"import-all: Der Commander „{result['commander']}“ steht nicht in der "
                "Sammlung, die Poolgröße ist unbekannt. Prüfe den Namen und die Sammlungsdatei.",
                file=sys.stderr,
            )
            return EXIT_COMMANDER_UNKNOWN
        if not result["pool_ok"]:
            print(
                f"import-all: Poolgröße {result['pool_size']}, erwartet {result['expected_pool']}.",
                file=sys.stderr,
            )
            return EXIT_POOL_MISMATCH
        return 0
    finally:
        store.close()

"""Command line of the Studio store: ``python -m commander_lab.studio <command>``."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from . import catalog, decklist_import, importers, roles, signals, tiers, universe
from .builder import list_commanders
from .data_report import data_report
from .decks import lab_snapshot, validate_revision
from .images import fetch_images
from .launch import (
    DEFAULT_GAMES_PER_JVM,
    MAX_GAMES_PER_JVM,
    MAX_WORKERS,
    MIN_GAMES_PER_JVM,
    MIN_WORKERS,
    checked_series_settings,
)
from .marks import import_owner_marks
from .queries import corpus_inclusion, legal_pool
from .store import BOUND_ELSEWHERE, LEGACY_COMMANDER, StudioStore

_SOURCE_DATA_COMMANDS = (
    "import-corpus-register",
    "import-decklists",
    "import-edhrec",
    "import-edhrec-cardrecs",
    "import-edhrec-delta",
    "import-edhrec-manifest",
    "import-hub",
    "import-simulation",
)


# These importers commit file by file; all others write one transaction.
_PER_FILE_COMMANDS = ("import-edhrec-delta", "import-simulation")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="commander_lab.studio", description=__doc__)
    parser.add_argument("--data", help="Studio data folder (default: from the environment)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "import-inventory",
        "import-corpus-register",
        "import-edhrec",
        "import-edhrec-cardrecs",
        "import-edhrec-delta",
        "import-hub",
    ):
        commands.add_parser(name).add_argument("path")
    corpus_cards = commands.add_parser(
        "import-corpus-cards",
        help="source-deck card rows from one or several part files (one transaction)",
    )
    corpus_cards.add_argument("paths", nargs="+")
    corpus_cards.add_argument(
        "--allow-deck-move",
        action="store_true",
        help="a deck that an earlier import took from another part file now lives in this file",
    )
    scryfall = commands.add_parser("import-scryfall")
    scryfall.add_argument("path")
    scryfall.add_argument("--disambiguation")
    sim = commands.add_parser("import-simulation")
    sim.add_argument("path")
    sim.add_argument("--engine-pin", default="f4d12f6e80")
    sim.add_argument("--pilot-policy", default="tuned")
    lab_deck = commands.add_parser("import-lab-deck")
    lab_deck.add_argument("path")
    lab_deck.add_argument("--deck-id")
    lab_deck.add_argument("--name")
    lab_deck.add_argument("--branch", default="main")
    selection = commands.add_parser("import-selection")
    selection.add_argument("path")
    selection.add_argument("--deck-id", required=True)
    selection.add_argument("--name", required=True)
    selection.add_argument("--commander", action="append", required=True)
    pool = commands.add_parser("pool")
    pool.add_argument("--commander", action="append", required=True)
    check = commands.add_parser("check")
    check.add_argument("revision_id")
    check.add_argument("--allow-unowned", action="store_true")
    export = commands.add_parser("export")
    export.add_argument("revision_id")
    export.add_argument("--out", required=True)
    inclusion = commands.add_parser("inclusion")
    inclusion.add_argument("card_name")
    inclusion.add_argument("--group")
    decklists = commands.add_parser(
        "import-decklists",
        help="complete public deck lists (normalized per-deck JSON files of one folder)",
    )
    decklists.add_argument("path")
    decklists.add_argument("--format", choices=("edhrec", "archidekt"), required=True)
    import_signals = commands.add_parser(
        "import-signals",
        help="usage signals for the strength index (EDHREC, Spellbook, tournament lists)",
    )
    import_signals.add_argument("folder")
    import_signals.add_argument(
        "--commander",
        default=LEGACY_COMMANDER,
        help="commander the tournament lists belong to (EDHREC signals carry their own)",
    )
    commands.add_parser("profiles", help="list the stored deck-universe profiles")
    save_profile = commands.add_parser(
        "save-profile", help="store a deck-universe profile (which decks count)"
    )
    save_profile.add_argument("name")
    save_profile.add_argument("--platform", action="append", dest="platforms")
    save_profile.add_argument("--cohort", action="append", dest="cohorts")
    save_profile.add_argument("--commander", action="append", dest="commanders")
    save_profile.add_argument("--date-from")
    save_profile.add_argument("--date-to")
    save_profile.add_argument("--min-main-cards", type=int)
    save_profile.add_argument("--min-universe", type=int)
    universe_inclusion = commands.add_parser(
        "universe-inclusion", help="per-card deck counts over one deck universe"
    )
    universe_inclusion.add_argument("--profile")
    universe_inclusion.add_argument("--commander", default=LEGACY_COMMANDER)
    universe_inclusion.add_argument("--card", action="append", dest="cards")
    tiers_cmd = commands.add_parser(
        "tiers", help="card tiers as a pure function of one universe's inclusion counts"
    )
    tiers_cmd.add_argument("--profile")
    tiers_cmd.add_argument("--commander", default=LEGACY_COMMANDER)
    tiers_cmd.add_argument("--min-universe", type=int)
    tiers_cmd.add_argument("--limit", type=int, default=50)
    commander_help = (
        "commander this source data belongs to (default: the commander of the standard "
        "data packages); figures of two commanders are never counted together"
    )
    bind = commands.add_parser(
        "bind-commander", help="bind all source data without a commander to this commander"
    )
    bind.add_argument("--commander", required=True)
    commands.add_parser("commanders", help="commanders with saved decks or source data")
    inclusion.add_argument("--commander", default=LEGACY_COMMANDER, help=commander_help)
    cohort = commands.add_parser("import-cohort")
    cohort.add_argument("path")
    cohort.add_argument("--name", required=True)
    images = commands.add_parser("fetch-images")
    images.add_argument("--commander", action="append", required=True)
    marks = commands.add_parser("import-marks")
    marks.add_argument("path")
    pg_atlas = commands.add_parser(
        "import-playgroup-atlas",
        help="import Playgroup.gg Card Atlas records (HTML, JSON, JSONL, or TSV/CSV)",
    )
    pg_atlas.add_argument("path", help="path to HTML, JSON, JSONL, or TSV/CSV Playgroup file")
    pg_atlas.add_argument("--source-title", help="optional custom source title")
    pg_atlas.add_argument("--snapshot-date", help="optional snapshot date (YYYY-MM-DD)")
    edhrec_manifest = commands.add_parser("import-edhrec-manifest")
    edhrec_manifest.add_argument("path")
    edhrec_manifest.add_argument("--raw-folder")
    fetch_roles = commands.add_parser("fetch-roles")
    fetch_roles.add_argument("--identity", required=True, help="color identity, for example WUG")
    fetch_roles.add_argument("--out", required=True, help="role file to write, then imported")
    replace_help = "let a full snapshot remove claims that the new snapshot no longer lists"
    fetch_roles.add_argument("--replace-scope", action="store_true", help=replace_help)
    import_roles = commands.add_parser("import-roles")
    import_roles.add_argument("path")
    import_roles.add_argument("--replace-scope", action="store_true", help=replace_help)
    owner_marks = commands.add_parser(
        "import-owner-marks",
        help="merge favorites, exclusions and notes from a marks file (never a rating)",
    )
    owner_marks.add_argument("path")
    labels = commands.add_parser(
        "check-role-labels", help="compare the role query slugs with a list of tagger labels"
    )
    labels.add_argument("path", help="JSON list or one label per line")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true", help="open the browser")
    play = commands.add_parser(
        "play", help="play one simulated game on the rules engine and record it"
    )
    play.add_argument(
        "--deck", action="append", required=True, help="deck snapshot per seat (2 to 6 times)"
    )
    play.add_argument("--seed", type=int, required=True)
    play.add_argument("--game-id", default=None)
    play.add_argument("--max-decisions", type=int, default=50_000)
    play.add_argument(
        "--style",
        type=float,
        default=None,
        help="AI pilot style from 0.0 (aggressive) to 1.0 (control). Defaults to 0.5 (balanced).",
    )
    play.add_argument(
        "--seat-style",
        action="append",
        default=None,
        help="Seat-specific style in seat:style format (e.g. 1:0.0 or 2:1.0).",
    )
    chunk = commands.add_parser(
        "play-batch",
        help="play several games in one rules-engine process (used by simulation series)",
    )
    chunk.add_argument("--deck", action="append", required=True)
    chunk.add_argument(
        "--game", action="append", required=True, help="SEED:GAME_ID, once per game, in order"
    )
    chunk.add_argument("--max-decisions", type=int, default=50_000)
    chunk.add_argument("--style", type=float, default=None)
    chunk.add_argument("--private-card-repository", action="store_true")
    sim = commands.add_parser(
        "simulate",
        help="run a batch simulation series of several games, several per engine process",
    )
    sim.add_argument("--revision", required=True, help="candidate deck revision id (e.g. rev@...)")
    sim.add_argument(
        "--pod",
        default="precon",
        choices=["precon", "mixed", "optimized"],
        help="pod preset",
    )
    sim.add_argument("--count", type=int, default=10, help="number of games to simulate")
    sim.add_argument("--base-seed", type=int, default=1000, help="starting random seed")
    sim.add_argument("--seed-step", type=int, default=1, help="seed increment per game")
    sim.add_argument("--style", type=float, default=None, help="AI pilot style from 0.0 to 1.0")
    sim.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"games played at once, {MIN_WORKERS} to {MAX_WORKERS} (default: min(4, cpu count - 1))",
    )
    sim.add_argument(
        "--games-per-jvm",
        type=int,
        default=None,
        help=f"games one engine process plays, {MIN_GAMES_PER_JVM} to {MAX_GAMES_PER_JVM} "
        f"(default: {DEFAULT_GAMES_PER_JVM})",
    )
    commands.add_parser("games")
    outcomes = commands.add_parser(
        "card-outcomes",
        help="per-card win rate with the card in the first dealt hand versus not (simulated games)",
    )
    outcomes.add_argument("--deck-id", required=True)
    outcomes.add_argument("--games-dir", help="folder of game logs (default: the Studio games)")
    outcomes.add_argument("--min-exposed", type=int, default=100)
    outcomes.add_argument("--out", help="write the full table as JSON to this file")
    outcomes.add_argument(
        "--allow-mixed", action="store_true", help="pool mixed engine commits or pilots"
    )
    commands.add_parser("status")
    commands.add_parser(
        "data-report", help="counts-only report on what the store has, lacks and does not know"
    )
    sources_cmd = commands.add_parser(
        "sources", help="print or write the evidence sources inventory and gap matrix (P0)"
    )
    sources_cmd.add_argument("--out", help="optional output path to write source_inventory.json")
    sources_cmd.add_argument(
        "--verified-only",
        action="store_true",
        help="filter the evidence sources output to only VERIFIED sources",
    )
    sources_cmd.add_argument(
        "--gap-report",
        action="store_true",
        help="calculate and export the 801-card pool gap matrix",
    )
    sources_cmd.add_argument(
        "--gap-out",
        help="optional output path for gap matrix JSON (default: data/research/chulane_legal_pool_gap_matrix.json)",
    )
    sources_cmd.add_argument(
        "--example-report",
        action="store_true",
        help="generate and print a concrete sample report with representative cards for each coverage grade (P0)",
    )
    for name in _SOURCE_DATA_COMMANDS:
        commands.choices[name].add_argument(
            "--commander", default=LEGACY_COMMANDER, help=commander_help
        )
    return parser


def _card_outcomes(args: argparse.Namespace) -> int:
    import sys

    from . import card_outcomes
    from .games import games_folder
    from .store import studio_data_dir

    folder = (
        Path(args.games_dir)
        if args.games_dir
        else games_folder(Path(args.data).resolve() if args.data else studio_data_dir())
    )
    try:
        table = card_outcomes.outcomes_for_folder(
            folder,
            deck_id=args.deck_id,
            min_exposed=args.min_exposed,
            allow_mixed=args.allow_mixed,
        )
    except ValueError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(card_outcomes.format_table(table))
    return 0


def _games(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .games import list_games
    from .store import studio_data_dir

    folder = Path(args.data).resolve() if args.data else studio_data_dir()
    result: object
    if args.command == "play":
        from .play import play_recorded_game

        seat_styles = {}
        if args.seat_style:
            for item in args.seat_style:
                parts = item.split(":", 1)
                if len(parts) == 2:
                    seat_styles[int(parts[0])] = float(parts[1])

        result = play_recorded_game(
            folder,
            [Path(path) for path in args.deck],
            seed=args.seed,
            game_id=args.game_id,
            style=args.style,
            seat_styles=seat_styles or None,
            max_decisions=args.max_decisions,
        )
    else:
        result = [
            {key: game[key] for key in ("game_id", "frames", "running", "result")}
            for game in list_games(folder)
        ]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _play_batch(args: argparse.Namespace) -> int:
    import signal

    from .play_batch import SeriesGame, play_recorded_games
    from .store import studio_data_dir

    folder = Path(args.data).resolve() if args.data else studio_data_dir()
    games: list[SeriesGame] = []
    for item in args.game:
        seed, _, game_id = item.partition(":")
        if not game_id:
            raise SystemExit(f"--game needs SEED:GAME_ID, got {item!r}")
        games.append(SeriesGame(int(seed), game_id))

    def _stop(_signal: int, _frame: object) -> None:
        # a cancelled series ends this process; leaving the with-blocks shuts the engine down
        raise SystemExit(143)

    signal.signal(signal.SIGTERM, _stop)

    def _report(summary: dict[str, object]) -> None:
        print(json.dumps({"game_id": summary["game_id"], "status": summary["status"]}), flush=True)

    summaries = play_recorded_games(
        folder,
        [Path(path) for path in args.deck],
        games,
        style=args.style,
        max_decisions=args.max_decisions,
        private_card_repository=args.private_card_repository,
        on_game=_report,
    )
    return 0 if all(item["status"] == "finished" for item in summaries) else 1


def _serve(data: str | None, port: int, open_browser: bool) -> int:
    import threading
    import webbrowser

    import uvicorn

    from .web import create_app

    StudioStore.open(data).close()
    address = f"http://127.0.0.1:{port}/"
    print(f"Commander Studio: {address}  (stop with Ctrl+C)")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(address,)).start()
    uvicorn.run(create_app(data), host="127.0.0.1", port=port, log_level="warning")
    return 0


def _read_labels(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    if text.lstrip().startswith("["):
        loaded = json.loads(text)
        if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
            raise SystemExit(f"{path}: expected a JSON list of strings")
        return [str(item) for item in loaded]
    return text.splitlines()


def _run(args: argparse.Namespace, store: StudioStore) -> object:
    """Run one store command and return its printable result."""
    result: object
    if args.command == "bind-commander":
        added = store.bind_unbound(args.commander, basis="OWNER_DECLARED")
        result = {"commander": args.commander, "commander_bindings_added": added}
    elif args.command == "commanders":
        result = list_commanders(store)
    elif args.command == "import-inventory":
        result = importers.import_inventory_workbook(store, args.path)
    elif args.command == "import-corpus-register":
        result = importers.import_corpus_register(store, args.path)
    elif args.command == "import-corpus-cards":
        result = importers.import_corpus_card_parts(
            store, args.paths, allow_deck_move=args.allow_deck_move
        )
    elif args.command == "import-edhrec":
        result = importers.import_edhrec_table(store, args.path)
    elif args.command == "import-edhrec-manifest":
        result = importers.import_edhrec_capture_manifest(
            store, args.path, raw_folder=args.raw_folder
        )
    elif args.command == "import-marks":
        result = importers.import_card_marks(store, args.path)
    elif args.command == "import-playgroup-atlas":
        result = importers.import_playgroup_atlas(
            store, args.path, source_title=args.source_title, snapshot_date=args.snapshot_date
        )
    elif args.command == "import-edhrec-cardrecs":
        result = importers.import_edhrec_cardrecs_csv(store, args.path)
    elif args.command == "import-edhrec-delta":
        result = importers.import_edhrec_delta_jsonl(store, args.path)
    elif args.command == "import-hub":
        result = importers.import_hub_corpus(store, args.path)
    elif args.command == "import-signals":
        try:
            result = signals.import_signals(store, args.folder, commander=args.commander)
        except ValueError as error:
            raise SystemExit(f"import-signals: {error}") from None
    elif args.command == "import-scryfall":
        result = catalog.import_scryfall_oracle(
            store, args.path, disambiguation_path=args.disambiguation
        )
    elif args.command == "import-simulation":
        result = importers.import_simulation_report(
            store,
            args.path,
            engine_pin=args.engine_pin,
            pilot_policy=args.pilot_policy,
        )
    elif args.command == "import-lab-deck":
        result = importers.import_lab_deck_snapshot(
            store,
            args.path,
            deck_id=args.deck_id,
            name=args.name,
            branch=args.branch,
        )
    elif args.command == "import-cohort":
        result = catalog.import_cohort(store, args.path, cohort=args.name)
    elif args.command == "fetch-images":
        pool = legal_pool(store, args.commander)
        result = fetch_images(store, [str(row["card_id"]) for row in pool])
    elif args.command == "fetch-roles":
        result = roles.import_roles(
            store,
            roles.fetch_role_file(args.identity, args.out),
            allow_scope_replace=args.replace_scope,
        )
    elif args.command == "import-roles":
        result = roles.import_roles(store, args.path, allow_scope_replace=args.replace_scope)
    elif args.command == "import-owner-marks":
        result = import_owner_marks(store, args.path)
    elif args.command == "import-selection":
        result = importers.import_studio_selection(
            store, args.path, deck_id=args.deck_id, name=args.name,
            commander_names=args.commander,
        )  # fmt: skip
    elif args.command == "pool":
        pool = legal_pool(store, args.commander)
        result = {
            "legal": len(pool),
            "available": sum(1 for row in pool if row["available"] > 0),
        }
    elif args.command == "check":
        issues = validate_revision(store, args.revision_id, owned_only=not args.allow_unowned)
        result = {
            "revision_id": args.revision_id,
            "errors": sum(1 for issue in issues if issue.severity == "error"),
            "by_code": dict(Counter(issue.code for issue in issues)),
            "issues": [issue.message for issue in issues],
        }
    elif args.command == "export":
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(lab_snapshot(store, args.revision_id), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        result = {"written": args.out}
    elif args.command == "data-report":
        result = data_report(store)
    elif args.command == "inclusion":
        result = corpus_inclusion(store, args.card_name, [args.commander], play_group=args.group)
    elif args.command == "import-decklists":
        result = decklist_import.import_decklists(
            store, args.path, format=args.format, commander=args.commander
        )
    elif args.command == "profiles":
        result = {"profiles": universe.list_profiles(store)}
    elif args.command == "save-profile":
        spec = {
            "platforms": args.platforms or [],
            "cohorts": args.cohorts or [],
            "commanders": args.commanders or [],
            "date_from": args.date_from,
            "date_to": args.date_to,
            "min_main_cards": args.min_main_cards,
            "min_universe": args.min_universe,
        }
        result = universe.save_profile(store, args.name, spec)
    elif args.command == "universe-inclusion":
        result = universe.inclusion(
            store,
            profile=args.profile,
            card_names=args.cards,
            commander_names=[args.commander],
        )
    elif args.command == "tiers":
        if args.limit < 0:
            raise ValueError("--limit must not be negative")
        counted = universe.inclusion(store, profile=args.profile, commander_names=[args.commander])
        params = tiers.TierParams(
            min_universe=args.min_universe
            if args.min_universe is not None
            else counted["spec"].get("min_universe", tiers.TierParams().min_universe)
        )
        snapshot = universe.snapshot_id(
            store, profile=args.profile, commander_names=[args.commander]
        )
        result = {
            "profile": args.profile,
            "commander": args.commander,
            "universe_snapshot": snapshot,
            "denominator": counted["denominator"],
            "denominator_by_platform": counted["denominator_by_platform"],
            "denominator_by_bracket": counted["denominator_by_bracket"],
            "tiers": tiers.tiers_for_universe(counted, universe_snapshot=snapshot, params=params)[
                : args.limit
            ],
        }
    else:
        result = {
            table: store.count(table)
            for table in ("source", "card", "inventory", "deck", "deck_revision",
                          "corpus_deck", "corpus_deck_card", "observation",
                          "scryfall_card", "corpus_cohort", "neutral_board_row",
                          "simulation_run", "universe_profile")
        }  # fmt: skip
    return result


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "serve":
        return _serve(args.data, args.port, args.open)
    if args.command == "card-outcomes":
        return _card_outcomes(args)
    if args.command in {"play", "games"}:
        return _games(args)
    if args.command == "play-batch":
        return _play_batch(args)
    if args.command == "simulate":
        import time

        from .simulations import SimulationBatchManager
        from .store import studio_data_dir

        folder = Path(args.data).resolve() if args.data else studio_data_dir()
        try:
            checked_series_settings(args.workers, args.games_per_jvm)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        store = StudioStore.open(folder)
        try:
            mgr = SimulationBatchManager()
            batch = mgr.start_batch(
                store,
                folder,
                revision_id=args.revision,
                pod=args.pod,
                games_count=args.count,
                base_seed=args.base_seed,
                seed_step=args.seed_step,
                style=args.style,
                workers=args.workers,
                games_per_jvm=args.games_per_jvm,
            )
            try:
                while batch.status in {"pending", "running"}:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                batch.cancel()
                raise
            print(json.dumps(batch.to_dict(), indent=2, ensure_ascii=False))
            return 0 if batch.status == "completed" else 1
        finally:
            store.close()
    if args.command == "check-role-labels":
        print(json.dumps(roles.check_role_labels(_read_labels(args.path)), indent=2))
        return 0
    if args.command == "sources":
        from .sources import (
            SourceStatus,
            calculate_pool_gap_matrix,
            generate_gap_example_report,
            source_inventory_payload,
            write_gap_matrix_json,
            write_source_inventory_json,
        )

        data_folder = args.data
        if not data_folder and not os.environ.get("COMMANDER_LAB_STUDIO_DATA"):
            default_user_dir = Path.home() / ".local/share/commander-studio"
            if default_user_dir.is_dir():
                data_folder = str(default_user_dir)

        if getattr(args, "gap_report", False):
            store = StudioStore.open(data_folder)
            matrix = calculate_pool_gap_matrix(store)
            default_gap_path = Path("data/research/chulane_legal_pool_gap_matrix.json")
            target_path = Path(args.gap_out) if getattr(args, "gap_out", None) else default_gap_path
            written = write_gap_matrix_json(store, target_path, payload=matrix)
            summary = {
                "written": str(written),
                "total_cards": matrix["total_cards"],
                "corpus_denominator": matrix["corpus_denominator"],
                "summary_counts": matrix["summary_counts"],
            }
            print(json.dumps(summary, indent=2))
            return 0

        if getattr(args, "example_report", False):
            store = StudioStore.open(data_folder)
            matrix = calculate_pool_gap_matrix(store)
            report = generate_gap_example_report(matrix)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0

        status_filter: SourceStatus | None = (
            "VERIFIED" if getattr(args, "verified_only", False) else None
        )

        if getattr(args, "out", None):
            written = write_source_inventory_json(args.out, status=status_filter)
            print(json.dumps({"written": str(written)}, indent=2))
        else:
            print(
                json.dumps(
                    source_inventory_payload(status=status_filter),
                    indent=2,
                    ensure_ascii=False,
                )
            )
        return 0
    store = StudioStore.open(args.data)
    try:
        result: object
        if args.command in _SOURCE_DATA_COMMANDS:
            # Source data is always bound to one commander: every row this import writes
            # is bound to it, and a key that belongs to another commander is refused.
            if args.command == "import-hub" and store.other_commanders(args.commander):
                # The hub import replaces the whole deck corpus and all neutral rows.
                raise SystemExit(
                    "import-hub: refused. The hub import replaces all source decks and "
                    "neutral rows, and this store holds source data of another commander "
                    f"than {args.commander!r}."
                )
            before = store.count("commander_binding")
            try:
                with store.importing_for(args.commander):
                    result = _run(args, store)
            except sqlite3.IntegrityError as error:
                if BOUND_ELSEWHERE not in str(error):
                    raise
                kept = (
                    f"Nothing of that file was written; files of the folder imported before "
                    f"it stay imported for {args.commander!r}."
                    if args.command in _PER_FILE_COMMANDS
                    else "Nothing was imported."
                )
                raise SystemExit(
                    f"{args.command}: stopped. The import writes a deck, cohort, run or "
                    f"neutral source that is bound to another commander than "
                    f"{args.commander!r}. {kept}"
                ) from None
            except ValueError as error:
                raise SystemExit(f"{args.command}: {error}") from None
            if isinstance(result, dict):
                added = store.count("commander_binding") - before
                result = {
                    **result,
                    "commander": args.commander,
                    "commander_bindings_added": added,
                }
        else:
            result = _run(args, store)
            if args.command == "import-corpus-cards" and isinstance(result, dict):
                # Card rows can show that a deck belongs to another commander than the
                # one its register import declared; such a deck is counted for nobody.
                released = store.release_contradicted_bindings()
                result = {**result, "commander_bindings_released": released}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())

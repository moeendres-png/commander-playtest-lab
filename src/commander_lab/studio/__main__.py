"""Command line of the Studio store: ``python -m commander_lab.studio <command>``."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from . import catalog, importers, roles
from .data_report import data_report
from .decks import lab_snapshot, validate_revision
from .images import fetch_images
from .marks import import_owner_marks
from .queries import corpus_inclusion, legal_pool
from .store import StudioStore


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
    cohort = commands.add_parser("import-cohort")
    cohort.add_argument("path")
    cohort.add_argument("--name", required=True)
    images = commands.add_parser("fetch-images")
    images.add_argument("--commander", action="append", required=True)
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
    commands.add_parser("games")
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
    return parser


def _games(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .games import list_games
    from .store import studio_data_dir

    folder = Path(args.data).resolve() if args.data else studio_data_dir()
    result: object
    if args.command == "play":
        from .play import play_recorded_game

        result = play_recorded_game(
            folder,
            [Path(path) for path in args.deck],
            seed=args.seed,
            game_id=args.game_id,
            max_decisions=args.max_decisions,
        )
    else:
        result = [
            {key: game[key] for key in ("game_id", "frames", "running", "result")}
            for game in list_games(folder)
        ]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "serve":
        return _serve(args.data, args.port, args.open)
    if args.command in {"play", "games"}:
        return _games(args)
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
        if args.command == "import-inventory":
            result = importers.import_inventory_workbook(store, args.path)
        elif args.command == "import-corpus-register":
            result = importers.import_corpus_register(store, args.path)
        elif args.command == "import-corpus-cards":
            result = importers.import_corpus_card_parts(
                store, args.paths, allow_deck_move=args.allow_deck_move
            )
        elif args.command == "import-edhrec":
            result = importers.import_edhrec_table(store, args.path)
        elif args.command == "import-edhrec-cardrecs":
            result = importers.import_edhrec_cardrecs_csv(store, args.path)
        elif args.command == "import-edhrec-delta":
            result = importers.import_edhrec_delta_jsonl(store, args.path)
        elif args.command == "import-hub":
            result = importers.import_hub_corpus(store, args.path)
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
                json.dumps(lab_snapshot(store, args.revision_id), indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            result = {"written": args.out}
        elif args.command == "data-report":
            result = data_report(store)
        elif args.command == "inclusion":
            result = corpus_inclusion(store, args.card_name, play_group=args.group)
        else:
            result = {
                table: store.count(table)
                for table in ("source", "card", "inventory", "deck", "deck_revision",
                              "corpus_deck", "corpus_deck_card", "observation",
                              "scryfall_card", "corpus_cohort", "neutral_board_row",
                              "simulation_run")
            }  # fmt: skip
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())

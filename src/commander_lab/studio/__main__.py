"""Command line of the Studio store: ``python -m commander_lab.studio <command>``."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from . import catalog, importers, roles
from .decks import lab_snapshot, validate_revision
from .images import fetch_images
from .queries import corpus_inclusion, legal_pool
from .store import StudioStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="commander_lab.studio", description=__doc__)
    parser.add_argument("--data", help="Studio data folder (default: from the environment)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "import-inventory",
        "import-corpus-register",
        "import-corpus-cards",
        "import-edhrec",
        "import-edhrec-cardrecs",
        "import-edhrec-delta",
        "import-hub",
    ):
        commands.add_parser(name).add_argument("path")
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
    commands.add_parser("import-roles").add_argument("path")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true", help="open the browser")
    commands.add_parser("status")
    return parser


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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "serve":
        return _serve(args.data, args.port, args.open)
    store = StudioStore.open(args.data)
    try:
        result: object
        if args.command == "import-inventory":
            result = importers.import_inventory_workbook(store, args.path)
        elif args.command == "import-corpus-register":
            result = importers.import_corpus_register(store, args.path)
        elif args.command == "import-corpus-cards":
            result = importers.import_corpus_cards(store, args.path)
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
            result = roles.import_roles(store, roles.fetch_role_file(args.identity, args.out))
        elif args.command == "import-roles":
            result = roles.import_roles(store, args.path)
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
            Path(args.out).write_text(
                json.dumps(lab_snapshot(store, args.revision_id), indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            result = {"written": args.out}
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

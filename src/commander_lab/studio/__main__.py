"""Command line of the Studio store: ``python -m commander_lab.studio <command>``."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from . import importers
from .decks import lab_snapshot, validate_revision
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
    ):
        commands.add_parser(name).add_argument("path")
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
    commands.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
                              "corpus_deck", "corpus_deck_card", "observation")
            }  # fmt: skip
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())

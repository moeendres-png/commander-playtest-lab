"""Local Commander deckbuilding tool. Run: python -m commander_lab.studio"""
from __future__ import annotations

import argparse
import json

from . import catalog, importers
from .commander_cache import cache_commander
from .data_report import data_report
from .store import StudioStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mtg-deckbuilder")
    parser.add_argument("--data", default=None, help="external folder for private SQLite/cache")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for command in ("import-inventory", "import-scryfall", "import-marks"):
        sub.add_parser(command).add_argument("path")
    sub.add_parser("normalization-report")
    cc = sub.add_parser("cache-commander")
    cc.add_argument("commander", nargs="+", help="one or two full English commander names")
    sr = sub.add_parser("serve")
    sr.add_argument("--port", type=int, default=8765)
    sub.add_parser("sync-scryfall")
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        import uvicorn
        from .web import create_app
        uvicorn.run(create_app(args.data), host="127.0.0.1", port=args.port)
        return 0
    if args.cmd == "sync-scryfall":
        from .scryfall_sync import sync_scryfall
        print(json.dumps(sync_scryfall(args.data), ensure_ascii=False, indent=2))
        return 0
    store = StudioStore.open(args.data)
    try:
        if args.cmd == "import-inventory":
            result = importers.import_inventory_workbook(store, args.path)
        elif args.cmd == "import-scryfall":
            result = catalog.import_scryfall_oracle(store, args.path)
        elif args.cmd == "import-marks":
            result = importers.import_card_marks(store, args.path)
        elif args.cmd == "normalization-report":
            db = store.connection
            total = store.count("card")
            linked = db.execute(
                "SELECT COUNT(*) FROM card c JOIN scryfall_card s ON c.oracle_id = s.oracle_id"
            ).fetchone()[0]
            unresolved = [r[0] for r in db.execute(
                "SELECT c.oracle_name FROM card c LEFT JOIN scryfall_card s "
                "ON c.oracle_id = s.oracle_id WHERE s.oracle_id IS NULL ORDER BY c.oracle_name"
            )]
            result = {"card_identities": total, "linked_to_scryfall": linked,
                      "unresolved_count": len(unresolved), "unresolved": unresolved}
        elif args.cmd == "cache-commander":
            result = cache_commander(store, args.commander)
        else:
            parser.error("unsupported command")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())

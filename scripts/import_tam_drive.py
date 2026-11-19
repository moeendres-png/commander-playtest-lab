"""Local CLI importer for downloaded TAM Google Drive datasets into the Studio SQLite store.

Reads locally downloaded CSV files only (no web scraping, no raw decks committed to the repo).
Supports ``--tam91-dir``, ``--tam381-dir``, and ``--edhrec78-dir`` independently or together and
prints a structured JSON report with ``n/N`` counts and SHA-256 provenance.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from commander_lab.studio.store import DATABASE_NAME, StudioStore  # noqa: E402
from commander_lab.studio.tam_import import (  # noqa: E402
    TAM_COMMANDER_NAME,
    import_tam_91,
    import_tam_381,
    import_tam_edhrec_views,
)


def _find_single(folder: Path, patterns: Sequence[str], label: str) -> Path:
    if not folder.is_dir():
        raise FileNotFoundError(f"{label}: directory does not exist: {folder}")
    for pattern in patterns:
        matches = sorted(p for p in folder.glob(pattern) if p.is_file())
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = ", ".join(m.name for m in matches)
            raise ValueError(f"{label}: multiple files match {pattern!r} in {folder}: {names}")
    tried = ", ".join(patterns)
    raise FileNotFoundError(f"{label}: no file matching [{tried}] in {folder}")


def _open_store(db_arg: Path | None) -> StudioStore:
    if db_arg is None:
        return StudioStore.open()
    if db_arg.suffix in {".sqlite3", ".db"}:
        if db_arg.name != DATABASE_NAME:
            raise ValueError(
                f"--db file must be named {DATABASE_NAME!r} or point to a store directory: {db_arg}"
            )
        return StudioStore.open(db_arg.parent)
    return StudioStore.open(db_arg)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=(
            "Studio data directory (or path to studio.sqlite3). "
            "Defaults to COMMANDER_LAB_STUDIO_DATA / COMMANDER_LAB_OWNER_DATA."
        ),
    )
    parser.add_argument(
        "--tam91-dir",
        type=Path,
        default=None,
        help="Local folder containing TAM_STUDIO_{DECKREGISTER,MAINBOARD,COMMANDER}_91_*.csv",
    )
    parser.add_argument(
        "--tam381-dir",
        type=Path,
        default=None,
        help="Local folder containing TAM_CHANDRA_381_STUDIO_REVIEW_*.csv",
    )
    parser.add_argument(
        "--edhrec78-dir",
        type=Path,
        default=None,
        help="Local folder containing EDHREC_78_THEMEN_QUELLEN_UND_NENNER.csv and cardrecs CSV",
    )
    parser.add_argument(
        "--commander",
        default=TAM_COMMANDER_NAME,
        help=f"Commander name for commander_binding (default: {TAM_COMMANDER_NAME!r})",
    )
    args = parser.parse_args(argv)

    if args.tam91_dir is None and args.tam381_dir is None and args.edhrec78_dir is None:
        parser.error("at least one of --tam91-dir, --tam381-dir, --edhrec78-dir is required")

    commander = str(args.commander).strip()
    if not commander:
        parser.error("--commander must not be blank")

    store = _open_store(args.db)
    report: dict[str, object] = {
        "commander": commander,
        "db_path": str(store.path) if store.path is not None else ":memory:",
    }
    try:
        if args.tam91_dir is not None:
            reg = _find_single(
                args.tam91_dir, ("TAM_STUDIO_DECKREGISTER_91_*.csv",), "tam91 register"
            )
            main_csv = _find_single(
                args.tam91_dir, ("TAM_STUDIO_MAINBOARD_91_*.csv",), "tam91 mainboard"
            )
            cmd_csv = _find_single(
                args.tam91_dir, ("TAM_STUDIO_COMMANDER_91_*.csv",), "tam91 commander"
            )
            report["tam_91"] = import_tam_91(
                store, reg, main_csv, cmd_csv, commander_name=commander
            )

        if args.tam381_dir is not None:
            reg381 = _find_single(
                args.tam381_dir,
                ("TAM_CHANDRA_381_STUDIO_REVIEW_REGISTER.csv", "TAM_CHANDRA_381_*REGISTER*.csv"),
                "tam381 register",
            )
            elig381 = _find_single(
                args.tam381_dir,
                (
                    "TAM_CHANDRA_381_STUDIO_REVIEW_ELIGIBILITY.csv",
                    "TAM_CHANDRA_381_*ELIGIBILITY*.csv",
                ),
                "tam381 eligibility",
            )
            main381 = _find_single(
                args.tam381_dir,
                ("TAM_CHANDRA_381_STUDIO_REVIEW_MAINBOARD.csv", "TAM_CHANDRA_381_*MAINBOARD*.csv"),
                "tam381 mainboard",
            )
            cmd381 = _find_single(
                args.tam381_dir,
                (
                    "TAM_CHANDRA_381_STUDIO_REVIEW_COMMANDERS.csv",
                    "TAM_CHANDRA_381_*COMMANDER*.csv",
                ),
                "tam381 commander",
            )
            report["tam_381"] = import_tam_381(
                store, reg381, elig381, main381, cmd381, commander_name=commander
            )

        if args.edhrec78_dir is not None:
            src_csv = _find_single(
                args.edhrec78_dir,
                ("EDHREC_78_THEMEN_QUELLEN_UND_NENNER.csv", "EDHREC_78_*QUELLEN*.csv"),
                "edhrec78 sources",
            )
            recs_csv = _find_single(
                args.edhrec78_dir,
                ("EDHREC_78_THEMEN_16023_CARDRECS_*.csv", "EDHREC_78_*CARDRECS*.csv"),
                "edhrec78 cardrecs",
            )
            report["edhrec_78"] = import_tam_edhrec_views(
                store, src_csv, recs_csv, commander_name=commander
            )
    finally:
        store.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

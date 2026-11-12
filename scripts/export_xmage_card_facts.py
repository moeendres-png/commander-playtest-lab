#!/usr/bin/env python3
"""Export the card facts the Structural model needs from a supplied XMage card database.

The Structural simulator used to know creature power, finishers and commander stats only
from hand-curated tables, so every other card was a 0-power creature or an inert filler.
XMage is the rules authority of the full-game lane; its card repository is the one fact
source that covers every card a full game can play. This script reads it with the H2
shell that ships with the engine build and writes the facts for the cards named in the
project's decks and collection:

    python scripts/export_xmage_card_facts.py \\
        --db .runtime/engine/db/cards.h2 \\
        --h2-jar ~/.m2/repository/com/h2database/h2/1.4.197/h2-1.4.197.jar

Use --all-cards to export all database names without reading deck or collection files.
--engine-commit records a caller declaration, not proof of the database's identity.

The database is created by the engine bridge on first start. Copy it first if a bridge
is running; H2 file databases allow one process at a time.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commander_lab.engine.structural.card_facts import (  # noqa: E402
    CARD_FACTS_PATH,
    CARD_FACTS_SCHEMA_VERSION,
    engine_lookup_key,
)

DECK_GLOBS = (
    "data/decks/*.json",
    "data/decks/deckbau/*.json",
    "data/decks/precons/*.json",
    "data/decks/opponents/*/current/deck.json",
    "data/opponents/*_precon.json",
    "data/opponents/official_precon_profiles.json",
    "data/coverage_decks/collection/*.json",
)
COLLECTION = "data/collections/owner_collection_2026-10-12.txt"
PILOT_KNOWLEDGE = "data/cards/pilot_card_knowledge.json"
DEFAULT_H2_JAR = "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
QUERY = (
    "SELECT NAME, MIN(POWER) P, MIN(TOUGHNESS) T, MIN(STARTINGLOYALTY) L, "
    "MIN(MANAVALUE) MV, MIN(TYPES) TY, MIN(SUBTYPES) ST, MIN(SUPERTYPES) SP, "
    "MIN(MANACOSTS) MC, MIN(RULES) R FROM CARD WHERE NAME IS NOT NULL GROUP BY NAME"
)


def _names_in(value: object) -> Iterable[str]:
    if isinstance(value, dict):
        name = value.get("oracle_name")
        if isinstance(name, str):
            yield name
        for key in ("commanders",):
            names = value.get(key)
            if isinstance(names, list):
                yield from (item for item in names if isinstance(item, str))
        for item in value.values():
            yield from _names_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from _names_in(item)


def listed_names(path: Path) -> list[str]:
    text = (path if path.is_absolute() else ROOT / path).read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and line.strip() != "oracle_name"
    ]


def wanted_names(root: Path, extra_files: Iterable[Path] = ()) -> set[str]:
    names: set[str] = set()
    for pattern in DECK_GLOBS:
        for path in sorted(root.glob(pattern)):
            names.update(_names_in(json.loads(path.read_text(encoding="utf-8"))))
    for catalog_rel in (PILOT_KNOWLEDGE, CARD_FACTS_PATH):
        catalog_path = root / catalog_rel
        if catalog_path.is_file():
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            cards_obj = payload.get("cards")
            if isinstance(cards_obj, dict):
                names.update(str(k) for k in cards_obj)
            missing_obj = payload.get("missing")
            if isinstance(missing_obj, list):
                names.update(str(k) for k in missing_obj if isinstance(k, str))
    collection = root / COLLECTION
    if collection.is_file():
        names.update(listed_names(collection))
    for path in extra_files:
        names.update(listed_names(path))
    return names


def _split(value: str) -> list[str]:
    return [part for part in value.split("@@@") if part] if value else []


def _number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def export(db: Path, h2_jar: Path, out_csv: Path) -> str:
    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch) / "cards.h2.mv.db"
        shutil.copyfile(db, copy)
        with copy.open("rb") as copied_db:
            digest = hashlib.file_digest(copied_db, "sha256").hexdigest()
        url = f"jdbc:h2:file:{Path(scratch) / 'cards.h2'}"
        sql = f"CALL CSVWRITE('{out_csv}', '{QUERY}')"
        subprocess.run(
            [
                "java",
                "-cp",
                str(h2_jar),
                "org.h2.tools.Shell",
                "-url",
                url,
                "-user",
                "",
                "-password",
                "",
                "-sql",
                sql,
            ],
            check=True,
            capture_output=True,
        )
        return digest


def build_facts(rows: Iterable[dict[str, str]], names: set[str] | None) -> dict[str, object]:
    by_key: dict[str, dict[str, str]] = {}
    exact: dict[str, dict[str, str]] = {}
    for row in rows:
        if row["NAME"] in exact and exact[row["NAME"]] != row:
            raise ValueError("conflicting XMage rows for the same name")
        exact[row["NAME"]] = row
        by_key[engine_lookup_key(row["NAME"])] = row
        if " // " in row["NAME"]:
            by_key.setdefault(engine_lookup_key(row["NAME"].split(" // ")[0]), row)
    cards: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    for name in sorted(exact if names is None else names):
        row = exact[name] if names is None else by_key.get(engine_lookup_key(name))
        if row is None and " // " in name:
            row = by_key.get(engine_lookup_key(name.split(" // ")[0]))
        if row is None:
            missing.append(name)
            continue
        types = _split(row["TY"])
        cards[name] = {
            "engine_name": row["NAME"],
            "mana_value": _number(row["MV"]) or 0.0,
            "mana_cost": "".join(_split(row["MC"])),
            "types": types,
            "subtypes": _split(row["ST"]),
            "supertypes": _split(row["SP"]),
            "power": _number(row["P"]) if "CREATURE" in types else None,
            "toughness": _number(row["T"]) if "CREATURE" in types else None,
            "loyalty": _number(row["L"]) if "PLANESWALKER" in types else None,
            "rules": _split(row["R"]),
        }
    return {
        "schema_version": CARD_FACTS_SCHEMA_VERSION,
        "source": "supplied XMage card repository (engine bridge cards.h2)",
        "card_count": len(cards),
        "missing": missing,
        "cards": cards,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=ROOT / ".runtime/engine/db/cards.h2.mv.db")
    parser.add_argument("--h2-jar", type=Path, default=ROOT / DEFAULT_H2_JAR)
    parser.add_argument("--out", type=Path, default=ROOT / CARD_FACTS_PATH)
    parser.add_argument("--all-cards", action="store_true", help="export all database names")
    parser.add_argument(
        "--record-provenance",
        action="store_true",
        help="record copied database digest and export time",
    )
    parser.add_argument(
        "--engine-commit", help="caller-declared engine source commit (not verified from database)"
    )
    parser.add_argument("--engine-source-url", help="caller-declared engine repository URL")
    parser.add_argument(
        "--names-file",
        type=Path,
        action="append",
        default=[],
        help="plain card list, one name per line",
    )
    args = parser.parse_args()
    if args.all_cards and args.names_file:
        parser.error("--all-cards cannot be combined with --names-file")
    if args.engine_commit and (
        len(args.engine_commit) != 40
        or any(c not in "0123456789abcdefABCDEF" for c in args.engine_commit)
    ):
        parser.error("--engine-commit must be a 40-character hexadecimal commit")
    with tempfile.TemporaryDirectory() as scratch:
        out_csv = Path(scratch) / "facts.csv"
        db_sha256 = export(args.db, args.h2_jar, out_csv)
        csv.field_size_limit(10**8)
        with out_csv.open(encoding="utf-8", newline="") as handle:
            names = None if args.all_cards else wanted_names(ROOT, args.names_file)
            facts = build_facts(csv.DictReader(handle), names)
    if args.record_provenance or args.engine_commit or args.engine_source_url:
        facts["provenance"] = {
            "database_sha256": db_sha256,
            "exported_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            **(
                {"declared_engine_commit": args.engine_commit.lower()} if args.engine_commit else {}
            ),
            **(
                {"declared_engine_source_url": args.engine_source_url}
                if args.engine_source_url
                else {}
            ),
        }
    args.out.write_text(
        json.dumps(facts, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{facts['card_count']} cards, {len(facts['missing'])} without XMage facts")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

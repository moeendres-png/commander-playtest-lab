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
import math
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
    apply_retained_lookup,
    engine_lookup_key,
    fact_name_index,
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
    "SELECT NAME, POWER P, TOUGHNESS T, STARTINGLOYALTY L, MANAVALUE MV, "
    "TYPES TY, SUBTYPES ST, SUPERTYPES SP, MANACOSTS MC, RULES R, "
    "SPLITCARDHALF H, FLIPCARDNAME F, SECONDSIDENAME S, SPELLOPTIONCARDNAME O, "
    "DOUBLEFACEDSECONDSIDENAME D FROM CARD WHERE NAME IS NOT NULL"
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


def _row_facts(row: dict[str, str]) -> dict[str, object]:
    mana_value = _number(row["MV"])
    if mana_value is None or not math.isfinite(mana_value) or mana_value < 0:
        raise ValueError("engine row has invalid mana value")
    types = _split(row["TY"])
    return {
        "engine_name": row["NAME"],
        "mana_value": mana_value,
        "mana_cost": "".join(_split(row["MC"])),
        "types": types,
        "subtypes": _split(row["ST"]),
        "supertypes": _split(row["SP"]),
        "power": _number(row["P"]) if "CREATURE" in types else None,
        "toughness": _number(row["T"]) if "CREATURE" in types else None,
        "loyalty": _number(row["L"]) if "PLANESWALKER" in types else None,
        "rules": _split(row["R"]),
    }


def build_facts(rows: Iterable[dict[str, str]], names: set[str] | None) -> dict[str, object]:
    fields = ("P", "T", "L", "MV", "TY", "ST", "SP", "MC", "R", "H", "F", "S", "O", "D")
    grouped: dict[str, dict[tuple[str, ...], dict[str, str]]] = {}
    for row in rows:
        if row["H"].casefold() not in {"true", "false"}:
            raise ValueError("engine row has invalid split-half flag")
        grouped.setdefault(row["NAME"], {})[tuple(row[field] for field in fields)] = row
    exact: dict[str, dict[str, object]] = {}
    source_rows: dict[str, dict[str, str]] = {}
    ambiguous: list[str] = []
    half_only: list[str] = []
    for name, candidates in grouped.items():
        if len(candidates) != 1:
            ambiguous.append(name)
            continue
        row = next(iter(candidates.values()))
        if row["H"].casefold() == "true":
            half_only.append(name)
            continue
        exact[name] = _row_facts(row)
        source_rows[name] = row
    aliases_by_key: dict[str, set[str]] = {}
    alias_spelling: dict[str, str] = {}
    for name, row in source_rows.items():
        if " // " in name:
            continue
        for field in ("F", "S", "O", "D"):
            face = row[field]
            if not face or face == name or " // " in face:
                continue
            alias = f"{name} // {face}"
            key = engine_lookup_key(alias)
            aliases_by_key.setdefault(key, set()).add(name)
            alias_spelling[key] = min(alias_spelling.get(key, alias), alias)
    normalized: dict[str, set[str]] = {}
    for name in exact:
        normalized.setdefault(engine_lookup_key(name), set()).add(name)
    ambiguous_keys = {engine_lookup_key(name) for name in ambiguous}
    for key, targets in aliases_by_key.items():
        if len(targets) > 1 and key not in normalized:
            ambiguous.append(alias_spelling[key])
            ambiguous_keys.add(key)
    aliases = {
        alias_spelling[key]: next(iter(targets))
        for key, targets in aliases_by_key.items()
        if len(targets) == 1 and key not in normalized and key not in ambiguous_keys
    }
    # An exact whole-card key takes precedence over a generated alias.
    index: dict[str, set[str]] = {key: set(targets) for key, targets in normalized.items()}
    for alias, target in aliases.items():
        index.setdefault(engine_lookup_key(alias), set()).add(target)
    front_targets: dict[str, set[str]] = {}
    for name in exact:
        if " // " in name:
            front_targets.setdefault(engine_lookup_key(name.split(" // ")[0]), set()).add(name)
    for key, targets in front_targets.items():
        index.setdefault(key, targets)
    half_keys = {engine_lookup_key(name) for name in half_only}
    cards: dict[str, dict[str, object]] = dict(exact) if names is None else {}
    missing: list[str] = []
    subset_ambiguous: list[str] = []
    for name in sorted(names or ()):
        key = engine_lookup_key(name)
        if key in ambiguous_keys:
            continue
        targets = index.get(key, set())
        if name in exact:
            targets = {name}
        if len(targets) > 1:
            # A searched front shared by several whole cards has no unambiguous
            # whole-card fact; account for it instead of dropping it silently.
            subset_ambiguous.append(name)
            continue
        if not targets:
            if key in half_keys:
                # The name exists only as a split half: present in the engine
                # data, but without whole-card facts of its own.
                subset_ambiguous.append(name)
            else:
                missing.append(name)
            continue
        target = next(iter(targets))
        cards[name] = exact[target]
    if subset_ambiguous:
        ambiguous = sorted({*ambiguous, *subset_ambiguous})
    aliases = {alias: target for alias, target in aliases.items() if target in cards}
    return {
        "schema_version": CARD_FACTS_SCHEMA_VERSION,
        "source": "supplied XMage card repository (engine bridge cards.h2)",
        "card_count": len(cards),
        "missing": missing,
        "ambiguous": sorted(ambiguous),
        "excluded_split_halves": sorted(half_only),
        "aliases": dict(sorted(aliases.items())),
        "cards": cards,
    }


def retain_catalog(facts: dict[str, object], path: Path) -> None:
    """Keep prior public names only when their entire row matches the fresh engine row."""
    with path.open("rb") as handle:
        raw = handle.read()
    prior = json.loads(raw)
    if not isinstance(prior, dict) or prior.get("schema_version") != CARD_FACTS_SCHEMA_VERSION:
        raise ValueError("retained catalog has an unsupported schema")
    previous = prior.get("cards")
    cards = facts["cards"]
    aliases = facts["aliases"]
    if (
        not isinstance(previous, dict)
        or not isinstance(cards, dict)
        or not isinstance(aliases, dict)
    ):
        raise ValueError("retained catalog has invalid cards")
    alias_index = {engine_lookup_key(alias): target for alias, target in aliases.items()}
    normalized_names: dict[str, set[str]] = {}
    split_fronts: dict[str, set[str]] = {}
    for engine_name in cards:
        normalized_names.setdefault(engine_lookup_key(engine_name), set()).add(engine_name)
        if " // " in engine_name:
            split_fronts.setdefault(engine_lookup_key(engine_name.split(" // ")[0]), set()).add(
                engine_name
            )
    ambiguous_keys = {engine_lookup_key(name) for name in facts["ambiguous"]}
    for name, row in previous.items():
        if not isinstance(name, str) or not isinstance(row, dict):
            raise ValueError("retained catalog contains an invalid fact")
        engine_name = row.get("engine_name")
        if not isinstance(engine_name, str) or cards.get(engine_name) != row:
            raise ValueError("retained fact does not match a fresh unambiguous engine row")
        name_key = engine_lookup_key(name)
        if name_key in normalized_names and normalized_names[name_key] != {engine_name}:
            raise ValueError("retained name collides with a different fresh engine identity")
        attested_front = (
            " // " not in name
            and name_key not in ambiguous_keys
            and split_fronts.get(name_key) == {engine_name}
        )
        if (
            name_key != engine_lookup_key(engine_name)
            and alias_index.get(name_key) != engine_name
            and not attested_front
        ):
            raise ValueError("retained name is not attested by fresh engine identity metadata")
        if name in cards and cards[name] != row:
            raise ValueError("retained name collides with a different fresh engine row")
    prior_index = {engine_lookup_key(name): name for name in previous}
    for name in previous:
        if " // " in name:
            prior_index.setdefault(engine_lookup_key(name.split(" // ")[0]), name)
    if set(prior_index) & ambiguous_keys:
        raise ValueError("retained lookup conflicts with an ambiguous fresh engine identity")
    fresh_index = fact_name_index(set(cards), aliases)
    for key, target in prior_index.items():
        existing = fresh_index.get(key)
        if existing is not None and cards[existing] != previous[target]:
            raise ValueError("retained lookup conflicts with a different fresh engine fact")
    cards.update(previous)
    index = fact_name_index(set(cards), aliases)
    apply_retained_lookup(index, cards, prior_index)
    facts["retained_lookup"] = dict(sorted(prior_index.items()))
    facts["card_count"] = len(cards)
    facts["retained_catalog"] = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "card_count": len(previous),
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
        "--retain-catalog", type=Path, help="retain verified names from a prior public catalog"
    )
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
    if args.retain_catalog and not args.all_cards:
        parser.error("--retain-catalog requires --all-cards")
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
    if args.retain_catalog:
        retain_catalog(facts, args.retain_catalog)
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

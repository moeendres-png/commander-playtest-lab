"""S1, offline: validate one S1 run folder and write ``derived/validation.json``.

Counts rows, checks that no price field is left (recursive key count, expected 0), checks the
collection against the oracle cards, rulings, tags and default cards, and (with ``--db``, a store
COPY opened read only) compares the (set, number) pairs of the collection's printings with the
default-cards bulk WITHOUT the language, which is the figure the acceptance recalculated
(1.646 of 1.650 on 2026-11-18; the version of the script that included the language gave 417 and
was not reproducible). The four unmatched pairs are listed and checked against the set code
mapping. The comparison WITH the language is reported as information only.

Hard checks (status PASS or FAIL): collection ids all present, forbidden fields 0, no pair with
more than one match, all mapping entries resolve exactly one printing. Everything else is a dated
reference value (Scryfall changes daily) and has no verdict.
"""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common

FORBIDDEN = common.PRICE_KEYS | common.PERSON_KEYS


def _status(ok: bool | None) -> str:
    return "UNKNOWN" if ok is None else ("PASS" if ok else "FAIL")


def validate(run_dir: Path, ids: set[str], db_path: Path | None, immutable: bool) -> dict[str, Any]:
    derived = run_dir / "derived"
    out: dict[str, Any] = {}

    rows = 0
    present: set[str] = set()
    forbidden: dict[str, int] = {}
    keys: collections.Counter[str] = collections.Counter()
    for card in common.iter_jsonl(derived / "oracle_cards.jsonl"):
        rows += 1
        keys.update(card.keys())
        if card.get("oracle_id") in ids:
            present.add(card["oracle_id"])
        common.count_keys(card, FORBIDDEN, forbidden)
    out["oracle_cards"] = {
        "rows": rows,
        "collection_ids_present": len(present),
        "collection_ids_total": len(ids),
        "top_level_key_count": len(keys),
    }

    ruling_count: collections.Counter[str] = collections.Counter()
    total = 0
    for ruling in common.iter_jsonl(derived / "rulings.jsonl"):
        total += 1
        ruling_count[ruling.get("oracle_id")] += 1
        common.count_keys(ruling, FORBIDDEN, forbidden)
    out["rulings"] = {
        "rulings_total": total,
        "distinct_oracle_ids_all": len(ruling_count),
        "collection_cards_with_ruling": sum(1 for oid in ids if ruling_count.get(oid)),
        "collection_rulings_total": sum(ruling_count.get(oid, 0) for oid in ids),
    }

    tags = 0
    tagged: set[str] = set()
    for node in common.iter_jsonl(derived / "oracle_tags.jsonl"):
        tags += 1
        for tagging in node.get("taggings") or []:
            if tagging.get("oracle_id") in ids:
                tagged.add(tagging["oracle_id"])
        common.count_keys(node, FORBIDDEN, forbidden)
    out["oracle_tags"] = {
        "tags": tags,
        "collection_cards_tagged": len(tagged),
        "collection_ids_total": len(ids),
    }

    by_pair: collections.Counter[tuple[Any, Any]] = collections.Counter()
    by_pair_lang: collections.Counter[tuple[Any, Any, Any]] = collections.Counter()
    default_rows = 0
    for card in common.iter_jsonl(derived / "default_cards.jsonl"):
        default_rows += 1
        common.count_keys(card, FORBIDDEN, forbidden)
        by_pair[(card.get("set"), card.get("collector_number"))] += 1
        by_pair_lang[(card.get("set"), card.get("collector_number"), card.get("lang"))] += 1
    default: dict[str, Any] = {"rows": default_rows}
    mapping_ok: bool | None = None
    multi_ok: bool | None = None
    mapping_file = derived / "set_code_mapping.json"
    mapping = common.read_json(mapping_file)["mapping"] if mapping_file.exists() else []
    resolved = [
        m for m in mapping if by_pair.get((m["scryfall_set"], m["collector_number_scryfall"])) == 1
    ]
    if db_path is not None:
        connection = sqlite3.connect(common.sqlite_uri(db_path, immutable=immutable), uri=True)
        try:
            db_rows = [
                tuple(r)
                for r in connection.execute(
                    "SELECT set_code, collector_number, lang FROM card_printing "
                    "WHERE set_code IS NOT NULL AND collector_number IS NOT NULL"
                )
            ]
        finally:
            connection.close()
        pairs = sorted({(s, n) for s, n, _ in db_rows})
        exactly_one = [p for p in pairs if by_pair.get(p) == 1]
        zero = [p for p in pairs if by_pair.get(p, 0) == 0]
        multi = [p for p in pairs if by_pair.get(p, 0) > 1]
        default.update(
            db_printing_rows=len(db_rows),
            db_distinct_set_number_pairs=len(pairs),
            pairs_matching_exactly_one=len(exactly_one),
            pairs_matching_zero=len(zero),
            pairs_matching_more_than_one=len(multi),
            zero_pairs=[list(p) for p in zero],
            info_rows_matching_exactly_one_with_lang=sum(
                1 for s, n, lang in db_rows if by_pair_lang.get((s, n, lang)) == 1
            ),
            note="Set + number WITHOUT language; the with-language figure is information only",
        )
        multi_ok = not multi
        zero_set = {tuple(p) for p in zero}
        mapped_from = {(m["collection_set_code"], m["collector_number"]) for m in mapping}
        mapping_ok = len(resolved) == len(mapping) and zero_set <= mapped_from
    default.update(
        mapping_entries=len(mapping), mapping_entries_resolving_exactly_one=len(resolved)
    )
    out["default_cards"] = default

    out["forbidden_key_counts"] = {key: forbidden.get(key, 0) for key in sorted(FORBIDDEN)}
    out["checks"] = {
        "collection_ids_all_in_oracle_cards": _status(len(present) == len(ids)),
        "forbidden_fields_zero": _status(not forbidden),
        "no_set_number_pair_with_several_printings": _status(multi_ok),
        "unmatched_pairs_all_covered_by_mapping": _status(mapping_ok),
    }
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--collection-ids", type=Path, required=True)
    parser.add_argument("--db", type=Path, help="store COPY for the printing comparison")
    parser.add_argument("--immutable", action="store_true")
    args = parser.parse_args(argv)
    run_dir = common.assert_outside_repository(args.run_dir)
    try:
        result = validate(
            run_dir, common.read_id_file(args.collection_ids), args.db, args.immutable
        )
    except (common.WaveError, OSError, sqlite3.Error) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    target = run_dir / "derived" / "validation.json"
    common.write_json(target, result)
    common.update_manifest(
        run_dir,
        {"validation_summary": result["checks"]},
        [common.derived_entry(target, run_dir, kind="pruefbericht")],
    )
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if all(v != "FAIL" for v in result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

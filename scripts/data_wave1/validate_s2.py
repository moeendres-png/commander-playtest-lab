"""S2, offline: validate the derived variants and compute the coverage of the collection.

Input: a run folder with ``derived/variants_wug.jsonl`` (``derive_s2_variants.py``) and the
collection id file (``export_collection_ids.py``). Output: ``derived/variants_wug_coverage_counts.json``
and ``derived/validation.json``.

Coverage (population N = white-blue-green variants that are commander legal with status OK; cards =
distinct Oracle ids per variant): how many variants are fully buildable from the collection, how many
miss exactly one card, how many contain at least one collection card, and the same for variants that
contain the commander "Chulane, Teller of Tales" (found by name in the data). This is the honest
number for the builder, not "4 of 31.544": most variants need 3 to 4 cards and only 5 percent of the
cards used by the variants are in the collection.

Reference check (``--reference``, default ``data/meta/spellbook_combos.json`` of the repo, read only):
card sets per combo id are compared with the repo's hand-kept list. The id is read in full
(``[\\d-]+``: ids with four or more segments and the ending ``--N``); cutting it at three segments
produced twelve false differences in the first version.

Hard checks (PASS or FAIL): no forbidden key in the derived rows, every derived row has an id. All
counts are dated reference values (the source changes daily) and carry no verdict.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common

CHULANE_NAME = "Chulane, Teller of Tales"
DEFAULT_REFERENCE = common.REPO_ROOT / "data" / "meta" / "spellbook_combos.json"
COMBO_ID = re.compile(r"/combo/([\d-]+)")


def coverage(rows: list[dict[str, Any]], ids: set[str]) -> dict[str, Any]:
    population = [r for r in rows if r["commander_legal"] and r["status"] == "OK"]
    chulane_id: str | None = None
    for row in rows:
        for card in row["cards"]:
            if card.get("name") == CHULANE_NAME and card.get("oracle_id"):
                chulane_id = card["oracle_id"]
                break
        if chulane_id:
            break
    missing: collections.Counter[str] = collections.Counter()
    at_least_one = near_without_requires = near_total = 0
    near_missing_cards: set[str] = set()
    chulane: collections.Counter[str] = collections.Counter()
    chulane_total = 0
    commander_uses = commander_variants = 0
    all_cards: set[str] = set()
    shares: list[float] = []
    for row in population:
        oracle_ids = {c["oracle_id"] for c in row["cards"] if c["oracle_id"]}
        all_cards |= oracle_ids
        lacking = len(oracle_ids - ids)
        missing[">=4" if lacking >= 4 else str(lacking)] += 1
        shares.append(1 - lacking / len(oracle_ids) if oracle_ids else 0.0)
        if oracle_ids & ids:
            at_least_one += 1
        if lacking == 1:
            near_total += 1
            if not row.get("requires"):
                near_without_requires += 1
            near_missing_cards |= oracle_ids - ids
        if chulane_id and chulane_id in oracle_ids:
            chulane_total += 1
            chulane[
                "missing_0" if lacking == 0 else "missing_1" if lacking == 1 else "missing_2plus"
            ] += 1
        forced = sum(1 for c in row["cards"] if c.get("must_be_commander"))
        commander_uses += forced
        commander_variants += forced > 0
    sizes: collections.Counter[int] = collections.Counter(
        len({c["oracle_id"] for c in r["cards"]}) for r in rows
    )
    shares.sort()
    n = len(population)
    return {
        "population": "WUG variants, commander legal and status OK",
        "N": n,
        "wug_rows": len(rows),
        "wug_cards_distinct_in_N": len(all_cards),
        "wug_cards_distinct_in_N_in_collection": len(all_cards & ids),
        "missing_cards_distribution_N": {k: missing[k] for k in ("0", "1", "2", "3", ">=4")},
        "buildable_complete": missing["0"],
        "buildable_missing_1": missing["1"],
        "complete_or_missing_1": missing["0"] + missing["1"],
        "missing_1_without_requires": near_without_requires,
        "missing_1_distinct_missing_cards": len(near_missing_cards),
        "at_least_1_collection_card": at_least_one,
        "at_least_1_collection_card_share": round(at_least_one / n, 4) if n else None,
        "mean_collection_share_per_variant": round(sum(shares) / n, 4) if n else None,
        "median_collection_share_per_variant": shares[n // 2] if n else None,
        "with_chulane": {
            "oracle_id_found": chulane_id is not None,
            "variants_in_N": chulane_total,
            "complete": chulane["missing_0"],
            "missing_1": chulane["missing_1"],
            "missing_2plus": chulane["missing_2plus"],
        },
        "must_be_commander": {
            "uses_in_N": commander_uses,
            "variants_in_N": commander_variants,
            "uses_all_wug_rows": sum(
                1 for r in rows for c in r["cards"] if c.get("must_be_commander")
            ),
            "note": "for Chulane decks exclude variants that force a foreign commander",
        },
        "variant_size_distinct_cards_all_wug": {str(k): v for k, v in sorted(sizes.items())},
    }


def reference_check(rows: list[dict[str, Any]], reference: Path) -> dict[str, Any]:
    by_id = {r["id"]: r for r in rows}
    combos = common.read_json(reference)["combos"]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for combo in combos:
        match = COMBO_ID.search(combo.get("source_url") or "")
        if match:
            grouped.setdefault(match.group(1), []).append(combo)
    found = [key for key in grouped if key in by_id]
    equal: list[str] = []
    different: list[str] = []
    for key in found:
        reference_cards = {name for combo in grouped[key] for name in combo.get("cards", [])}
        bulk_cards = {card["name"] for card in by_id[key]["cards"]}
        (equal if reference_cards == bulk_cards else different).append(key)
    return {
        "reference_file": "data/meta/spellbook_combos.json (read only)",
        "ref_combos": len(combos),
        "ref_ids_full_regex": len(grouped),
        "ref_ids_found_in_wug": len(found),
        "card_set_equal": len(equal),
        "card_set_differs": len(different),
        "differing_ids": sorted(different),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--collection-ids", type=Path, required=True)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    args = parser.parse_args(argv)
    run_dir = common.assert_outside_repository(args.run_dir)
    try:
        rows = list(common.iter_jsonl(run_dir / "derived" / "variants_wug.jsonl"))
        ids = common.read_id_file(args.collection_ids)
        cover = coverage(rows, ids)
        forbidden: dict[str, int] = {}
        for row in rows:
            common.count_keys(row, common.SPELLBOOK_FORBIDDEN_KEYS, forbidden)
        result: dict[str, Any] = {
            "forbidden_key_counts": {
                k: forbidden.get(k, 0) for k in sorted(common.SPELLBOOK_FORBIDDEN_KEYS)
            },
            "reference_check": (
                reference_check(rows, args.reference)
                if args.reference.is_file()
                else "UNKNOWN: no reference file"
            ),
        }
        result["checks"] = {
            "forbidden_fields_zero": "PASS" if not forbidden else "FAIL",
            "every_row_has_an_id": "PASS" if all(r.get("id") for r in rows) else "FAIL",
        }
    except (common.WaveError, OSError, KeyError, json.JSONDecodeError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    derived = run_dir / "derived"
    common.write_json(derived / "variants_wug_coverage_counts.json", cover)
    common.write_json(derived / "validation.json", result)
    common.update_manifest(
        run_dir,
        {
            "coverage_for_builder": cover,
            "reference_check": result["reference_check"],
            "validation_summary": result["checks"],
        },
        [
            common.derived_entry(
                derived / "variants_wug_coverage_counts.json", run_dir, kind="zaehlung"
            ),
            common.derived_entry(derived / "validation.json", run_dir, kind="pruefbericht"),
        ],
    )
    print(json.dumps({"coverage": cover, **result}, ensure_ascii=False, indent=1))
    return 0 if all(v != "FAIL" for v in result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

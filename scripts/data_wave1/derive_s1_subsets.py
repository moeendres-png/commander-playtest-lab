"""S1, offline: derive the collection subsets from the full derived files of one S1 run.

Input: a run folder written by ``fetch_s1_scryfall.py`` (``derived/*.jsonl``) and the id file of
``export_collection_ids.py``. No network. Output, all inside the run folder under ``derived/``:

* ``oracle_cards_collection_subset.jsonl``: oracle cards of the collection.
* ``card_rulings_1655.jsonl``: the rulings of the collection, lines unchanged. The name is the
  file name ``import-rulings`` stores its rulings under; the importer does NOT filter on the
  collection and replaces only files of the same name, so only this subset is imported.
* ``collection_subset_oracle_tags.jsonl``: all tag nodes (the hierarchy stays complete), with the
  taggings reduced to the collection.
* ``collection_subset_default_cards.jsonl``: all printings of the collection's cards (matched by
  ``oracle_id`` or ``card_faces[].oracle_id``).
* ``set_code_mapping.json``: documentation of the 4 collection-source set codes that Scryfall
  spells differently (used by ``validate_s1.py``).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common

SET_CODE_MAPPING: list[dict[str, str]] = [
    {
        "collection_set_code": "xcmr",
        "collector_number": "456",
        "collection_lang": "en",
        "card_name": "Wear // Tear",
        "scryfall_set": "cmr",
        "collector_number_scryfall": "456",
        "reason": "x prefix = extras sub-set of the collection source (Commander Legends)",
    },
    {
        "collection_set_code": "xdmc",
        "collector_number": "68",
        "collection_lang": "de",
        "card_name": "Tor Wauki the Younger",
        "scryfall_set": "dmc",
        "collector_number_scryfall": "68",
        "reason": "x prefix = extras sub-set (Dominaria United Commander); the collection holds "
        "the German printing, the default bulk only the English one",
    },
    {
        "collection_set_code": "xmh2",
        "collector_number": "381",
        "collection_lang": "en",
        "card_name": "Blacksmith's Skill",
        "scryfall_set": "mh2",
        "collector_number_scryfall": "381",
        "reason": "x prefix = extras sub-set (Modern Horizons 2)",
    },
    {
        "collection_set_code": "sch",
        "collector_number": "189",
        "collection_lang": "en",
        "card_name": "Lavinia, Azorius Renegade",
        "scryfall_set": "prna",
        "collector_number_scryfall": "189",
        "reason": "store championship promo, spelled prna (Ravnica Allegiance Promos) by Scryfall",
    },
]


def derive_subsets(run_dir: Path, ids: set[str]) -> dict[str, Any]:
    derived = run_dir / "derived"
    result: dict[str, Any] = {"collection_ids": len(ids)}

    # oracle cards: lines unchanged
    rows_in = rows_out = 0
    seen: set[str] = set()
    with (
        (derived / "oracle_cards.jsonl").open("r", encoding="utf-8") as reader,
        common.open_text_out(derived / "oracle_cards_collection_subset.jsonl") as writer,
    ):
        for line in reader:
            if not line.strip():
                continue
            rows_in += 1
            oracle_id = json.loads(line).get("oracle_id")
            if oracle_id in ids:
                writer.write(line if line.endswith("\n") else line + "\n")
                rows_out += 1
                seen.add(oracle_id)
    result["oracle_cards"] = {
        "rows_in": rows_in,
        "rows_out": rows_out,
        "distinct_collection_oracle_ids_present": len(seen),
    }

    # rulings: lines unchanged
    rows_in = rows_out = 0
    keys: set[tuple[Any, Any, Any]] = set()
    cards: set[str] = set()
    with (
        (derived / "rulings.jsonl").open("r", encoding="utf-8") as reader,
        common.open_text_out(derived / "card_rulings_1655.jsonl") as writer,
    ):
        for line in reader:
            if not line.strip():
                continue
            rows_in += 1
            ruling = json.loads(line)
            if ruling.get("oracle_id") in ids:
                writer.write(line if line.endswith("\n") else line + "\n")
                rows_out += 1
                keys.add((ruling["oracle_id"], ruling["published_at"], ruling["comment"]))
                cards.add(ruling["oracle_id"])
    result["rulings"] = {
        "rows_in": rows_in,
        "rows_out": rows_out,
        "distinct_oracle_id_published_at_comment": len(keys),
        "cards_with_ruling": len(cards),
    }

    # oracle tags: all nodes, taggings reduced to the collection
    rows_in = rows_out = taggings_in = taggings_out = nodes_with = 0
    tagged: set[str] = set()
    with (
        (derived / "oracle_tags.jsonl").open("r", encoding="utf-8") as reader,
        common.open_text_out(derived / "collection_subset_oracle_tags.jsonl") as writer,
    ):
        for line in reader:
            if not line.strip():
                continue
            rows_in += 1
            node = json.loads(line)
            taggings = node.get("taggings") or []
            taggings_in += len(taggings)
            kept = [item for item in taggings if item.get("oracle_id") in ids]
            taggings_out += len(kept)
            nodes_with += bool(kept)
            tagged.update(item["oracle_id"] for item in kept)
            node["taggings"] = kept
            writer.write(common.compact_json(node) + "\n")
            rows_out += 1
    result["oracle_tags"] = {
        "rows_in": rows_in,
        "rows_out": rows_out,
        "taggings_in": taggings_in,
        "taggings_out": taggings_out,
        "nodes_with_collection_tagging": nodes_with,
        "collection_cards_tagged": len(tagged),
    }

    # default cards: lines unchanged
    rows_in = rows_out = via_face = 0
    present: set[str] = set()
    with (
        (derived / "default_cards.jsonl").open("r", encoding="utf-8") as reader,
        common.open_text_out(derived / "collection_subset_default_cards.jsonl") as writer,
    ):
        for line in reader:
            if not line.strip():
                continue
            rows_in += 1
            card = json.loads(line)
            card_ids = set()
            if card.get("oracle_id"):
                card_ids.add(card["oracle_id"])
            for face in card.get("card_faces") or []:
                if face.get("oracle_id"):
                    card_ids.add(face["oracle_id"])
            hit = card_ids & ids
            if hit:
                if card.get("oracle_id") not in ids:
                    via_face += 1
                writer.write(line if line.endswith("\n") else line + "\n")
                rows_out += 1
                present.update(hit)
    result["default_cards"] = {
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rows_matched_only_via_card_faces": via_face,
        "distinct_collection_oracle_ids_present": len(present),
    }

    common.write_json(
        derived / "set_code_mapping.json",
        {
            "description": "4 collection-source set codes mapped to Scryfall set codes; "
            "documentation and check aid only, no change to a workbook or store",
            "mapping": SET_CODE_MAPPING,
        },
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True, help="S1 run folder")
    parser.add_argument("--collection-ids", type=Path, required=True, help="id file")
    args = parser.parse_args(argv)
    run_dir = common.assert_outside_repository(args.run_dir)
    try:
        ids = common.read_id_file(args.collection_ids)
        result = derive_subsets(run_dir, ids)
    except (common.WaveError, OSError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    derived_dir = run_dir / "derived"
    entries = []
    rules = {
        "oracle_cards_collection_subset.jsonl": ("oracle_cards", "oracle_id in the collection ids"),
        "card_rulings_1655.jsonl": ("rulings", "lines unchanged, oracle_id in the collection ids"),
        "collection_subset_oracle_tags.jsonl": (
            "oracle_tags",
            "all tag nodes, taggings only for the collection ids",
        ),
        "collection_subset_default_cards.jsonl": (
            "default_cards",
            "all printings whose oracle_id (or card_faces[].oracle_id) is in the collection ids",
        ),
    }
    for name, (label, rule) in rules.items():
        entries.append(
            common.derived_entry(
                derived_dir / name,
                run_dir,
                source_label=label,
                kind="teilmenge",
                rule=rule,
            )
        )
    entries.append(
        common.derived_entry(derived_dir / "set_code_mapping.json", run_dir, kind="doku")
    )
    common.update_manifest(run_dir, {"subset_summary": result}, entries)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

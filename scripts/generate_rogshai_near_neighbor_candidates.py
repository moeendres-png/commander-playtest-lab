from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

BASE_CANDIDATE = "C016"

VARIANTS = (
    {
        "candidate_id": "N001",
        "candidate_label": "C016 Mana 30 — +Chart +Think Twice +Aether Spellbomb",
        "axis": "mana",
        "remove": ["Island", "Island", "Island"],
        "add": ["Chart a Course", "Think Twice", "Aether Spellbomb"],
        "expected_land_count": 30,
    },
    {
        "candidate_id": "N002",
        "candidate_label": "C016 Mana 31 — +Chart +Think Twice",
        "axis": "mana",
        "remove": ["Island", "Island"],
        "add": ["Chart a Course", "Think Twice"],
        "expected_land_count": 31,
    },
    {
        "candidate_id": "N003",
        "candidate_label": "C016 Mana 32 — +Chart",
        "axis": "mana",
        "remove": ["Island"],
        "add": ["Chart a Course"],
        "expected_land_count": 32,
    },
    {
        "candidate_id": "N004",
        "candidate_label": "C016 Mana 32 — +Boros Signet",
        "axis": "mana",
        "remove": ["Island"],
        "add": ["Boros Signet"],
        "expected_land_count": 32,
    },
    {
        "candidate_id": "N005",
        "candidate_label": "C016 Mana 34 — +Island -Royal Scions",
        "axis": "mana",
        "remove": ["The Royal Scions"],
        "add": ["Island"],
        "expected_land_count": 34,
    },
    {
        "candidate_id": "N006",
        "candidate_label": "C016 Protection — Blacksmith Skill to Chart",
        "axis": "protection",
        "remove": ["Blacksmith's Skill"],
        "add": ["Chart a Course"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N007",
        "candidate_label": "C016 Protection — Slip Out the Back to Chart",
        "axis": "protection",
        "remove": ["Slip Out the Back"],
        "add": ["Chart a Course"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N008",
        "candidate_label": "C016 Protection — Esior to Chart",
        "axis": "protection",
        "remove": ["Esior, Wardwing Familiar"],
        "add": ["Chart a Course"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N009",
        "candidate_label": "C016 Protection — Swiftfoot Boots over Royal Scions",
        "axis": "protection",
        "remove": ["The Royal Scions"],
        "add": ["Swiftfoot Boots"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N010",
        "candidate_label": "C016 Protection — Dive Down over Royal Scions",
        "axis": "protection",
        "remove": ["The Royal Scions"],
        "add": ["Dive Down"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N011",
        "candidate_label": "C016 Protection — Lightning Greaves over Stave Off",
        "axis": "protection",
        "remove": ["Stave Off"],
        "add": ["Lightning Greaves"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N012",
        "candidate_label": "C016 Conversion — Jeska to Chart",
        "axis": "conversion",
        "remove": ["Jeska, Thrice Reborn"],
        "add": ["Chart a Course"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N013",
        "candidate_label": "C016 Conversion — Kediss to Chart",
        "axis": "conversion",
        "remove": ["Kediss, Emberclaw Familiar"],
        "add": ["Chart a Course"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N014",
        "candidate_label": "C016 Conversion — Duelist Heritage to Chart",
        "axis": "conversion",
        "remove": ["Duelist's Heritage"],
        "add": ["Chart a Course"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N015",
        "candidate_label": "C016 Conversion — Combat Research to Chart",
        "axis": "conversion",
        "remove": ["Combat Research"],
        "add": ["Chart a Course"],
        "expected_land_count": 33,
    },
    {
        "candidate_id": "N016",
        "candidate_label": "C016 Conversion — Sunhome to Island",
        "axis": "conversion",
        "remove": ["Sunhome, Fortress of the Legion"],
        "add": ["Island"],
        "expected_land_count": 33,
    },
)

FOCUS_COMPARISONS = (
    {"a": "N001", "b": "N002", "question": "30_vs_31_land_boundary", "a_slot": "Aether Spellbomb", "b_slot": "Island"},
    {"a": "N002", "b": "N003", "question": "31_vs_32_land", "a_slot": "Think Twice", "b_slot": "Island"},
    {"a": "N003", "b": "C016", "question": "32_vs_33_land_cantrip", "a_slot": "Chart a Course", "b_slot": "Island"},
    {"a": "N004", "b": "C016", "question": "32_vs_33_land_rock", "a_slot": "Boros Signet", "b_slot": "Island"},
    {"a": "N003", "b": "N004", "question": "cantrip_vs_rock_at_32", "a_slot": "Chart a Course", "b_slot": "Boros Signet"},
    {"a": "N005", "b": "C016", "question": "34_vs_33_land", "a_slot": "Island", "b_slot": "The Royal Scions"},
    {"a": "C016", "b": "N006", "question": "blacksmith_skill_vs_draw", "a_slot": "Blacksmith's Skill", "b_slot": "Chart a Course"},
    {"a": "C016", "b": "N007", "question": "slip_out_the_back_vs_draw", "a_slot": "Slip Out the Back", "b_slot": "Chart a Course"},
    {"a": "C016", "b": "N008", "question": "esior_vs_draw", "a_slot": "Esior, Wardwing Familiar", "b_slot": "Chart a Course"},
    {"a": "N009", "b": "C016", "question": "swiftfoot_boots_vs_value", "a_slot": "Swiftfoot Boots", "b_slot": "The Royal Scions"},
    {"a": "N010", "b": "C016", "question": "dive_down_vs_value", "a_slot": "Dive Down", "b_slot": "The Royal Scions"},
    {"a": "C016", "b": "N011", "question": "stave_off_vs_lightning_greaves", "a_slot": "Stave Off", "b_slot": "Lightning Greaves"},
    {"a": "C016", "b": "N012", "question": "jeska_vs_draw", "a_slot": "Jeska, Thrice Reborn", "b_slot": "Chart a Course"},
    {"a": "C016", "b": "N013", "question": "kediss_vs_draw", "a_slot": "Kediss, Emberclaw Familiar", "b_slot": "Chart a Course"},
    {"a": "C016", "b": "N014", "question": "duelist_heritage_vs_draw", "a_slot": "Duelist's Heritage", "b_slot": "Chart a Course"},
    {"a": "C016", "b": "N015", "question": "combat_research_vs_draw", "a_slot": "Combat Research", "b_slot": "Chart a Course"},
    {"a": "C016", "b": "N016", "question": "sunhome_vs_basic_island", "a_slot": "Sunhome, Fortress of the Legion", "b_slot": "Island"},
)

LAND_NAMES = {
    "Command Tower", "Exotic Orchard", "Adarkar Wastes", "Battlefield Forge", "Shivan Reef",
    "Cascade Bluffs", "Clifftop Retreat", "Glacial Fortress", "Sulfur Falls", "Port Town",
    "Prairie Stream", "Frostboil Snarl", "Scorched Geyser", "Fabled Passage", "Skycloud Expanse",
    "Sunhome, Fortress of the Legion", "Ferrous Lake", "Mystic Monastery", "Irrigated Farmland",
    "Spire of Industry", "Mystic Sanctuary", "Reliquary Tower", "Evolving Wilds", "Terramorphic Expanse",
    "Plains", "Island", "Mountain",
}


def apply_swap(mainboard: list[str], remove: list[str], add: list[str]) -> list[str]:
    result = list(mainboard)
    for name in remove:
        try:
            result.remove(name)
        except ValueError as exc:
            raise SystemExit(f"cannot remove missing card {name}") from exc
    result.extend(add)
    if len(result) != 98:
        raise SystemExit(f"variant mainboard has {len(result)} cards, expected 98")
    return result


def one_slot_difference(a: list[str], b: list[str]) -> tuple[list[str], list[str]]:
    ca, cb = Counter(a), Counter(b)
    a_only = list((ca - cb).elements())
    b_only = list((cb - ca).elements())
    return a_only, b_only


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit-output", required=True)
    args = parser.parse_args()

    base_payload = json.loads(Path(args.base).read_text(encoding="utf-8"))
    rows = base_payload.get("candidates")
    if not isinstance(rows, list) or len(rows) != 48:
        raise SystemExit("base population must contain 48 candidates")
    if [row["candidate_id"] for row in rows] != [f"C{i:03d}" for i in range(1, 49)]:
        raise SystemExit("base IDs must be C001..C048")
    parent = next(row for row in rows if row["candidate_id"] == BASE_CANDIDATE)
    if len(parent["mainboard"]) != 98:
        raise SystemExit("C016 parent malformed")
    parent_land_count = sum(name in LAND_NAMES for name in parent["mainboard"])
    if parent_land_count != 33:
        raise SystemExit(f"C016 expected 33 lands, got {parent_land_count}")

    out_rows = copy.deepcopy(rows)
    for row in out_rows:
        row["land_count"] = sum(name in LAND_NAMES for name in row["mainboard"])
        row["theorycraft_only"] = False
        row["creates_physical_reservation"] = False
    variant_by_id: dict[str, dict] = {}
    for spec in VARIANTS:
        mainboard = apply_swap(parent["mainboard"], spec["remove"], spec["add"])
        land_count = sum(name in LAND_NAMES for name in mainboard)
        if land_count != spec["expected_land_count"]:
            raise SystemExit(f"{spec['candidate_id']} land count {land_count} != {spec['expected_land_count']}")
        row = {
            "candidate_id": spec["candidate_id"],
            "candidate_label": spec["candidate_label"],
            "source_v3_deck_hash": None,
            "commander_names": list(parent["commander_names"]),
            "mainboard": mainboard,
            "v5_patch_applied": False,
            "parent_candidate_id": BASE_CANDIDATE,
            "near_neighbor_axis": spec["axis"],
            "swap_out": list(spec["remove"]),
            "swap_in": list(spec["add"]),
            "land_count": land_count,
            "theorycraft_only": True,
            "creates_physical_reservation": False,
        }
        out_rows.append(row)
        variant_by_id[spec["candidate_id"]] = row

    if len(out_rows) != 64:
        raise SystemExit("combined population must contain 64 candidates")
    if len({tuple(sorted(row["mainboard"])) for row in out_rows}) != 64:
        raise SystemExit("exact mainboard duplicate detected")

    focus_audit = []
    all_by_id = {row["candidate_id"]: row for row in out_rows}
    for pair in FOCUS_COMPARISONS:
        a = all_by_id[pair["a"]]
        b = all_by_id[pair["b"]]
        a_only, b_only = one_slot_difference(a["mainboard"], b["mainboard"])
        if len(a_only) != 1 or len(b_only) != 1:
            raise SystemExit(f"focus pair {pair['a']}/{pair['b']} is not exactly one replacement slot: {a_only} vs {b_only}")
        if a_only[0] != pair["a_slot"] or b_only[0] != pair["b_slot"]:
            raise SystemExit(f"focus pair card mismatch for {pair['question']}: {a_only} vs {b_only}")
        focus_audit.append({**pair, "a_only": a_only, "b_only": b_only, "replacement_slots": 1})

    output_payload = {
        "schema_version": "rogshai-near-neighbor-candidates-1.0.0",
        "source_candidate_set_id": base_payload.get("source_candidate_set_id"),
        "source_sha256": base_payload.get("source_sha256"),
        "candidate_count": 64,
        "existing_candidate_count": 48,
        "new_theorycraft_candidate_count": 16,
        "base_candidate": BASE_CANDIDATE,
        "pre_gameplay_elimination": 0,
        "candidates": out_rows,
        "focus_comparisons": list(FOCUS_COMPARISONS),
    }
    audit = {
        "schema_version": "rogshai-near-neighbor-candidate-audit-1.0.0",
        "status": "PASS",
        "candidate_count": 64,
        "existing_candidate_count": 48,
        "new_candidate_count": 16,
        "exact_duplicate_count": 0,
        "focus_pair_count": len(focus_audit),
        "all_focus_pairs_exactly_one_replacement_slot": True,
        "base_candidate_land_count": parent_land_count,
        "new_land_counts": {cid: row["land_count"] for cid, row in variant_by_id.items()},
        "focus_pairs": focus_audit,
        "canonical_mutation": False,
        "physical_reservation_created": False,
    }
    Path(args.output).write_text(json.dumps(output_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.audit_output).write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

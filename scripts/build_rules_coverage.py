#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ALLOWED_COVERAGE = {
    "external_engine_verified",
    "external_engine_partial",
    "tactical_only",
    "structural_only",
    "unsupported",
    "provider_disagreement",
}

REQUESTED_GOLDEN = {
    "korvold_sacrifice_cost_and_trigger": (
        ["Korvold, Fae-Cursed King", "Zuran Orb"],
        ["korvold_etb_sacrifice_generates_value", "zuran_orb_sacrifice_is_cost"],
    ),
    "korvold_multiple_sacrifices": (
        ["Korvold, Fae-Cursed King"],
        ["korvold_etb_sacrifice_generates_value"],
    ),
    "korvold_land_sacrifice": (
        ["Korvold, Fae-Cursed King", "Zuran Orb"],
        ["zuran_orb_sacrifice_is_cost"],
    ),
    "korvold_land_recursion": (
        ["Ramunap Excavator", "Splendid Reclamation", "Aftermath Analyst"],
        [
            "ramunap_uses_land_play",
            "splendid_reclamation_returns_tapped",
            "aftermath_analyst_sacrifices_and_returns_lands",
        ],
    ),
    "korvold_mazirek": (["Mazirek, Kraul Death Priest"], ["mazirek_counters_all_your_creatures"]),
    "korvold_szarel": (["Szarel, Genesis Shepherd"], []),
    "korvold_mirkwood_bats": (
        ["Mirkwood Bats"],
        ["mirkwood_bats_counts_created_and_sacrificed_tokens"],
    ),
    "korvold_mayhem_devil": (["Mayhem Devil"], ["mayhem_devil_triggers_for_any_player"]),
    "korvold_massacre_wurm": (["Massacre Wurm"], ["massacre_wurm_counts_opponent_deaths"]),
    "korvold_commander_tax": (["Korvold, Fae-Cursed King"], ["commander_tax_third_cast"]),
    "korvold_boardwipe_rebuild": (
        ["Splendid Reclamation", "Aftermath Analyst"],
        ["splendid_reclamation_returns_tapped", "aftermath_analyst_sacrifices_and_returns_lands"],
    ),
    "korvold_graveyard_hate": (
        ["Bojuka Bog", "Rakdos Charm"],
        ["bojuka_bog_exiles_target_graveyard", "rakdos_charm_graveyard_mode"],
    ),
    "korvold_replacement_effects": (
        ["Academy Manufactor"],
        ["academy_manufactor_replaces_each_token"],
    ),
    "korvold_simultaneous_triggers": (
        ["Mazirek, Kraul Death Priest", "Mirkwood Bats"],
        ["apnap_trigger_order_four_player"],
    ),
    "rogshai_partner_command_zone": (
        ["Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"],
        ["commander_damage_not_combined"],
    ),
    "rogshai_rograkh_resource": (["Rograkh, Son of Rohgahh"], []),
    "rogshai_ishai_opponent_spells": (
        ["Ishai, Ojutai Dragonspeaker"],
        ["ishai_only_opponent_spells_trigger"],
    ),
    "rogshai_combat_research": (["Combat Research"], ["combat_research_draw_trigger"]),
    "rogshai_curiosity": (["Curiosity"], []),
    "rogshai_staggering_insight": (
        ["Staggering Insight"],
        ["staggering_insight_draw_and_lifelink"],
    ),
    "rogshai_duelists_heritage": (["Duelist's Heritage"], ["double_strike_counts_both_hits"]),
    "rogshai_double_strike": (
        ["Duelist's Heritage", "Ishai, Ojutai Dragonspeaker"],
        ["double_strike_counts_both_hits"],
    ),
    "rogshai_jeska_triple": (
        ["Jeska, Thrice Reborn", "Ishai, Ojutai Dragonspeaker"],
        ["jeska_triples_commander_combat_damage"],
    ),
    "rogshai_ishai_commander_damage": (
        ["Ishai, Ojutai Dragonspeaker"],
        ["commander_damage_exactly_twenty_one"],
    ),
    "rogshai_kediss_not_commander_damage": (
        ["Kediss, Emberclaw Familiar", "Ishai, Ojutai Dragonspeaker"],
        ["kediss_damage_is_not_commander_damage"],
    ),
    "rogshai_sunhome": (["Sunhome, Fortress of the Legion"], []),
    "rogshai_protection_counter": (
        ["Boros Charm", "Counterspell"],
        ["boros_charm_protects_from_destroy_wipe", "countered_commander_can_return_to_command"],
    ),
    "rogshai_stack_priority": (
        [],
        ["stack_resolves_last_in_first_out", "apnap_trigger_order_four_player"],
    ),
    "rogshai_separate_partner_tax": (
        ["Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"],
        ["commander_tax_third_cast"],
    ),
    "opponent_kaervek_trigger_survives_counter": (
        ["Kaervek the Merciless", "Counterspell"],
        ["kaervek_trigger_survives_counter"],
    ),
    "opponent_minus_counters_vs_indestructible": (
        ["Bastion Protector", "Toxic Deluge"],
        ["indestructible_fails_minus_toughness", "zero_toughness_is_not_destroy"],
    ),
    "opponent_blight_proliferate": ([], []),
    "opponent_elf_etb_lords": (["High Perfect Morcant"], []),
    "opponent_wakanda_artifact_equipment": ([], []),
    "opponent_dance_evoke_recursion": ([], []),
    "opponent_doctor_doom_artifact_villain": (["Doctor Doom, King of Latveria"], []),
    "opponent_cosmic_spiderman_legends": (["Cosmic Spider-Man"], []),
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")


def canonical_opponent_name(text: str) -> str:
    # Canonical opponent sheets may preserve a localized printed name in a trailing
    # parenthetical.  The machine registry uses the English Oracle name only.
    if " (" in text and text.endswith(")"):
        return text.split(" (", 1)[0].strip()
    return text.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts/phase12_14")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    out = (root / args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    canonical_dir = root / "data/canonical_import/2026-08-07"
    canonical = load(canonical_dir / "deck_lists.json")
    inventory = load(canonical_dir / "inventory.json")
    opponents = load(canonical_dir / "opponents.json")
    validation = load(root / "data/rules/validation_registry.json")
    critical = load(root / "data/rules/project_critical_interactions.json")
    role_data = load(root / "data/cards/structural_role_profiles.json")
    package_data = load(root / "data/packages/package_registry.json")
    oracle_data = load(root / "data/cards/oracle_subset.json")

    roles = {p["oracle_name"]: p.get("roles", []) for p in role_data.get("profiles", [])}
    oracle = {c["oracle_name"]: c for c in oracle_data.get("cards", [])}
    tactical_cards = validation.get("cards", {})
    interactions = {i["interaction_id"]: i for i in critical.get("interactions", [])}
    packages: dict[str, set[str]] = defaultdict(set)
    for pkg in package_data.get("packages", []):
        for key in (
            "core_cards",
            "support_cards",
            "optional_cards",
            "enablers",
            "payoffs",
            "finishers",
        ):
            for card in pkg.get(key, []):
                name = card if isinstance(card, str) else card.get("oracle_name")
                if name:
                    packages[name].add(pkg.get("package_id", "unknown"))

    records: dict[str, dict[str, Any]] = {}

    # Entire active physical inventory is in scope for future candidate generation.
    for row in inventory.get("cards", []):
        name = row["oracle_name"]
        rec = records.setdefault(
            name, {"oracle_name": name, "deck_versions": [], "source_status": []}
        )
        rec["inventory_candidate"] = True
        rec["inventory_quantity"] = row.get("quantity")
        rec["inventory_metadata"] = {
            "language": row.get("language"),
            "edition": row.get("edition"),
            "condition": row.get("condition"),
            "box_or_location": row.get("box_or_location"),
            "current_deck_use": row.get("current_deck_use"),
            "commander_legality": row.get("commander_legality"),
            "color_identity": row.get("color_identity"),
        }
        rec["source_status"].append(row.get("verification_status") or "inventory")

    deck_map = {
        "01_Korvold_100": "korvold/current-2026-08-07",
        "02_RogShai_100": "rogshai/current-2026-08-07",
        "03_Kaervek_100": "kaervek/maintained-2026-08-07",
    }
    for sheet, deck_version in deck_map.items():
        for row in canonical["decks"][sheet]:
            name = row["Oracle-Name"]
            rec = records.setdefault(
                name, {"oracle_name": name, "deck_versions": [], "source_status": []}
            )
            rec["deck_versions"].append(deck_version)
            rec["source_status"].append(row.get("physischer Status"))
            rec.setdefault("canonical_role", row.get("Primärrolle"))

    # Exact known opponent lists and confirmed partial cores from the canonical opponent workbook.
    opponent_versions: list[str] = []
    for deck in opponents.get("decks", []):
        deck_version = f"opponent/{slug(deck['deck'])}/drive-2026-08-02"
        opponent_versions.append(deck_version)
        for row in deck.get("cards", []):
            name = canonical_opponent_name(row["oracle_name"])
            rec = records.setdefault(
                name, {"oracle_name": name, "deck_versions": [], "source_status": []}
            )
            rec["deck_versions"].append(deck_version)
            rec["source_status"].append(deck.get("data_status"))
            rec.setdefault("opponent_sources", []).append(
                "data/canonical_import/2026-08-07/opponents.json"
            )
        # Provisional opponent completion cards remain explicit synthetic assumptions.
        # They are useful for rules-coverage scoping but are never counted as hard-known slots.
        for row in deck.get("provisional_cards", []):
            name = canonical_opponent_name(row["oracle_name"])
            rec = records.setdefault(
                name, {"oracle_name": name, "deck_versions": [], "source_status": []}
            )
            rec["deck_versions"].append(f"{deck_version}/provisional-completion")
            rec["source_status"].append("synthetic_assumption")
            rec.setdefault("opponent_sources", []).append(
                "data/canonical_import/2026-08-07/opponents.json"
            )

    # Preserve additional explicitly provenance-marked ensemble assumptions as assumptions, never confirmed cards.
    for path in sorted((root / "data/opponent_ensembles").glob("*-v1.json")):
        ensemble = load(path)
        for variant in ensemble.get("variants", []):
            for key, label in (("known_cards", "known"), ("assumed_cards", "synthetic_assumption")):
                for name in variant.get(key, []):
                    rec = records.setdefault(
                        name, {"oracle_name": name, "deck_versions": [], "source_status": []}
                    )
                    rec["deck_versions"].append(
                        f"{ensemble['ensemble_id']}/{variant['variant_id']}"
                    )
                    rec["source_status"].append(label)
                    rec.setdefault("opponent_sources", []).append(str(path.relative_to(root)))

    coverage: list[dict[str, Any]] = []
    for name in sorted(records):
        rec = records[name]
        tact = tactical_cards.get(name, {})
        # Per-card structural support means a card has an actual role/profile or an explicit canonical deck role.
        structural = bool(roles.get(name) or rec.get("canonical_role"))
        tactical = int(tact.get("tactical_passed", 0)) > 0
        status = "tactical_only" if tactical else "structural_only" if structural else "unsupported"
        evidence: list[str] = []
        if tactical:
            evidence.append("data/rules/validation_registry.json")
        if rec.get("inventory_candidate"):
            evidence.append("data/canonical_import/2026-08-07/inventory.json")
        if any(v.startswith(("korvold/", "rogshai/", "kaervek/")) for v in rec["deck_versions"]):
            evidence.append("data/canonical_import/2026-08-07/deck_lists.json")
        evidence.extend(rec.get("opponent_sources", []))
        oc = oracle.get(name, {})
        item = {
            "oracle_name": name,
            "oracle_id": oc.get("oracle_id"),
            "deck_versions": sorted(set(rec["deck_versions"])),
            "roles": roles.get(
                name, [rec.get("canonical_role")] if rec.get("canonical_role") else []
            ),
            "packages": sorted(packages.get(name, set())),
            "structural_support": structural,
            "tactical_oracle_support": tactical,
            "xmage_recognized": False,
            "xmage_rules_verified": False,
            "forge_recognized": False,
            "forge_rules_verified": False,
            "multiplayer_targeting_verified": False,
            "commander_interaction_verified": False,
            "replay_verified": False,
            "known_provider_bug": None,
            "fallback_policy": "tactical_oracle"
            if tactical
            else "structural_only"
            if structural
            else "unsupported",
            "coverage_status": status,
            "inventory_candidate": bool(rec.get("inventory_candidate")),
            "inventory_quantity": rec.get("inventory_quantity"),
            "inventory_metadata": rec.get("inventory_metadata"),
            "source_status": sorted({str(v) for v in rec.get("source_status", []) if v}),
            "evidence_files": sorted(set(evidence)),
        }
        assert item["coverage_status"] in ALLOWED_COVERAGE
        coverage.append(item)

    scenarios: list[dict[str, Any]] = []
    for scenario_id, (cards, ids) in REQUESTED_GOLDEN.items():
        found = [i for i in ids if i in interactions]
        tactical = bool(found) and all(
            any(i in tactical_cards.get(card, {}).get("interaction_ids", []) for card in cards)
            if cards
            else True
            for i in found
        )
        if not cards and found:
            tactical = True
        supported = bool(cards or found)
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "cards": cards,
                "interaction_ids": found,
                "structural_support": supported,
                "tactical_oracle_support": tactical,
                "xmage_verified": False,
                "forge_verified": False,
                "external_replay_verified": False,
                "coverage_status": "tactical_only"
                if tactical
                else "structural_only"
                if supported
                else "unsupported",
                "evidence_files": ["data/rules/project_critical_interactions.json"]
                if found
                else [],
            }
        )

    all_versions = sorted({v for r in coverage for v in r["deck_versions"]})
    deck_stats: dict[str, Any] = {}
    for deck in all_versions:
        rows = [r for r in coverage if deck in r["deck_versions"]]
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            counts[row["coverage_status"]] += 1
        deck_stats[deck] = {"unique_oracle_names": len(rows), "coverage": dict(counts)}

    counts: dict[str, int] = defaultdict(int)
    for row in coverage:
        counts[row["coverage_status"]] += 1
    scenario_counts: dict[str, int] = defaultdict(int)
    for row in scenarios:
        scenario_counts[row["coverage_status"]] += 1

    card_registry = {
        "schema_version": 2,
        "generated_from_read_only_canonical_drive_snapshot": True,
        "source_drive_files": {
            "decks": canonical.get("source_drive_file_id"),
            "inventory": inventory.get("source_drive_file_id"),
            "opponents": opponents.get("source_drive_file_id"),
        },
        "external_engine_execution_status": "blocked",
        "cards": coverage,
        "coverage_counts": dict(counts),
        "inventory_candidate_count": sum(1 for r in coverage if r["inventory_candidate"]),
        "deck_statistics": deck_stats,
    }
    scenario_registry = {
        "schema_version": 2,
        "external_engine_execution_status": "blocked",
        "scenarios": scenarios,
        "coverage_counts": dict(scenario_counts),
    }
    unsupported = [r for r in coverage if r["coverage_status"] == "unsupported"]
    differences = {
        "schema_version": 2,
        "status": "not_run",
        "provider_comparisons": [],
        "reason": "No real XMage or Forge process could be executed in the current runtime.",
    }
    card_text = json.dumps(card_registry, indent=2, ensure_ascii=False) + "\n"
    scenario_text = json.dumps(scenario_registry, indent=2, ensure_ascii=False) + "\n"
    unsupported_text = (
        json.dumps({"schema_version": 2, "cards": unsupported}, indent=2, ensure_ascii=False) + "\n"
    )
    difference_text = json.dumps(differences, indent=2) + "\n"

    (out / "CARD_RULES_COVERAGE.json").write_text(card_text)
    # Keep explicit names for the user-requested registries/corpus as first-class artifacts.
    (out / "RULES_SCENARIO_REGISTRY.json").write_text(scenario_text)
    (out / "GOLDEN_RULES_SCENARIOS.json").write_text(scenario_text)
    (out / "GOLDEN_RULES_CORPUS.json").write_text(scenario_text)
    (out / "UNSUPPORTED_CARD_REGISTER.json").write_text(unsupported_text)
    (out / "PROVIDER_DIFFERENCE_REGISTER.json").write_text(difference_text)
    (root / "data/rules/card_rules_coverage.json").write_text(card_text)
    (root / "data/rules/rules_scenario_registry.json").write_text(scenario_text)
    (root / "data/rules/golden_rules_scenarios.json").write_text(scenario_text)
    (root / "data/rules/golden_rules_corpus.json").write_text(scenario_text)
    (root / "data/rules/unsupported_card_register.json").write_text(unsupported_text)
    (root / "data/rules/provider_difference_register.json").write_text(difference_text)
    print(
        json.dumps(
            {
                "cards": len(coverage),
                "inventory_candidates": card_registry["inventory_candidate_count"],
                "coverage_counts": dict(counts),
                "scenarios": len(scenarios),
                "scenario_counts": dict(scenario_counts),
                "deck_statistics": deck_stats,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

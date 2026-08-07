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
    "korvold_sacrifice_cost_and_trigger": (["Korvold, Fae-Cursed King", "Zuran Orb"], ["korvold_etb_sacrifice_generates_value", "zuran_orb_sacrifice_is_cost"]),
    "korvold_multiple_sacrifices": (["Korvold, Fae-Cursed King"], ["korvold_etb_sacrifice_generates_value"]),
    "korvold_land_sacrifice": (["Korvold, Fae-Cursed King", "Zuran Orb"], ["zuran_orb_sacrifice_is_cost"]),
    "korvold_land_recursion": (["Ramunap Excavator", "Splendid Reclamation", "Aftermath Analyst"], ["ramunap_uses_land_play", "splendid_reclamation_returns_tapped", "aftermath_analyst_sacrifices_and_returns_lands"]),
    "korvold_mazirek": (["Mazirek, Kraul Death Priest"], ["mazirek_counters_all_your_creatures"]),
    "korvold_szarel": (["Szarel, Genesis Shepherd"], []),
    "korvold_mirkwood_bats": (["Mirkwood Bats"], ["mirkwood_bats_counts_created_and_sacrificed_tokens"]),
    "korvold_mayhem_devil": (["Mayhem Devil"], ["mayhem_devil_triggers_for_any_player"]),
    "korvold_massacre_wurm": (["Massacre Wurm"], ["massacre_wurm_counts_opponent_deaths"]),
    "korvold_commander_tax": (["Korvold, Fae-Cursed King"], ["commander_tax_third_cast"]),
    "korvold_boardwipe_rebuild": (["Splendid Reclamation", "Aftermath Analyst"], ["splendid_reclamation_returns_tapped", "aftermath_analyst_sacrifices_and_returns_lands"]),
    "korvold_graveyard_hate": (["Bojuka Bog", "Rakdos Charm"], ["bojuka_bog_exiles_target_graveyard", "rakdos_charm_graveyard_mode"]),
    "korvold_replacement_effects": (["Academy Manufactor"], ["academy_manufactor_replaces_each_token"]),
    "korvold_simultaneous_triggers": (["Mazirek, Kraul Death Priest", "Mirkwood Bats"], ["apnap_trigger_order_four_player"]),
    "rogshai_partner_command_zone": (["Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"], ["commander_damage_not_combined"]),
    "rogshai_rograkh_resource": (["Rograkh, Son of Rohgahh"], []),
    "rogshai_ishai_opponent_spells": (["Ishai, Ojutai Dragonspeaker"], ["ishai_only_opponent_spells_trigger"]),
    "rogshai_combat_research": (["Combat Research"], ["combat_research_draw_trigger"]),
    "rogshai_curiosity": (["Curiosity"], []),
    "rogshai_staggering_insight": (["Staggering Insight"], ["staggering_insight_draw_and_lifelink"]),
    "rogshai_duelists_heritage": (["Duelist's Heritage"], ["double_strike_counts_both_hits"]),
    "rogshai_double_strike": (["Duelist's Heritage", "Ishai, Ojutai Dragonspeaker"], ["double_strike_counts_both_hits"]),
    "rogshai_jeska_triple": (["Jeska, Thrice Reborn", "Ishai, Ojutai Dragonspeaker"], ["jeska_triples_commander_combat_damage"]),
    "rogshai_ishai_commander_damage": (["Ishai, Ojutai Dragonspeaker"], ["commander_damage_exactly_twenty_one"]),
    "rogshai_kediss_not_commander_damage": (["Kediss, Emberclaw Familiar", "Ishai, Ojutai Dragonspeaker"], ["kediss_damage_is_not_commander_damage"]),
    "rogshai_sunhome": (["Sunhome, Fortress of the Legion"], []),
    "rogshai_protection_counter": (["Boros Charm", "Counterspell"], ["boros_charm_protects_from_destroy_wipe", "countered_commander_can_return_to_command"]),
    "rogshai_stack_priority": ([], ["stack_resolves_last_in_first_out", "apnap_trigger_order_four_player"]),
    "rogshai_separate_partner_tax": (["Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"], ["commander_tax_third_cast"]),
    "opponent_kaervek_trigger_survives_counter": (["Kaervek the Merciless", "Counterspell"], ["kaervek_trigger_survives_counter"]),
    "opponent_minus_counters_vs_indestructible": (["Bastion Protector", "Toxic Deluge"], ["indestructible_fails_minus_toughness", "zero_toughness_is_not_destroy"]),
    "opponent_blight_proliferate": ([], []),
    "opponent_elf_etb_lords": (["High Perfect Morcant"], []),
    "opponent_wakanda_artifact_equipment": ([], []),
    "opponent_dance_evoke_recursion": ([], []),
    "opponent_doctor_doom_artifact_villain": (["Doctor Doom"], []),
    "opponent_cosmic_spiderman_legends": (["Cosmic Spider-Man"], []),
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts/phase12_14")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    out = (root / args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    canonical = load(root / "data/canonical_import/2026-08-07/deck_lists.json")
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
        for key in ("core_cards", "support_cards", "optional_cards", "enablers", "payoffs", "finishers"):
            for card in pkg.get(key, []):
                name = card if isinstance(card, str) else card.get("oracle_name")
                if name:
                    packages[name].add(pkg.get("package_id", "unknown"))

    records: dict[str, dict[str, Any]] = {}
    deck_map = {
        "01_Korvold_100": "korvold/current-2026-08-07",
        "02_RogShai_100": "rogshai/current-2026-08-07",
        "03_Kaervek_100": "kaervek/maintained-2026-08-07",
    }
    for sheet, deck_version in deck_map.items():
        for row in canonical["decks"][sheet]:
            name = row["Oracle-Name"]
            rec = records.setdefault(name, {"oracle_name": name, "deck_versions": [], "source_status": []})
            rec["deck_versions"].append(deck_version)
            rec["source_status"].append(row.get("physischer Status"))
            rec.setdefault("canonical_role", row.get("Primärrolle"))

    opponent_sources: dict[str, list[str]] = defaultdict(list)
    profiles = load(root / "data/opponents/current_structural_profiles.json")
    for profile in profiles.get("profiles", []):
        name = profile.get("commander")
        if name:
            rec = records.setdefault(name, {"oracle_name": name, "deck_versions": [], "source_status": []})
            rec["deck_versions"].append(profile["deck_id"])
            rec["source_status"].append(profile.get("source_status"))
            opponent_sources[name].append("data/opponents/current_structural_profiles.json")
    for path in sorted((root / "data/opponent_ensembles").glob("*-v1.json")):
        ensemble = load(path)
        for variant in ensemble.get("variants", []):
            for key, label in (("known_cards", "known"), ("assumed_cards", "synthetic_assumption")):
                for name in variant.get(key, []):
                    rec = records.setdefault(name, {"oracle_name": name, "deck_versions": [], "source_status": []})
                    rec["deck_versions"].append(f"{ensemble['ensemble_id']}/{variant['variant_id']}")
                    rec["source_status"].append(label)
                    opponent_sources[name].append(str(path.relative_to(root)))

    coverage: list[dict[str, Any]] = []
    for name in sorted(records):
        rec = records[name]
        tact = tactical_cards.get(name, {})
        structural = bool(roles.get(name) or rec.get("canonical_role") or rec.get("deck_versions"))
        tactical = int(tact.get("tactical_passed", 0)) > 0
        status = "tactical_only" if tactical else "structural_only" if structural else "unsupported"
        evidence = ["data/rules/validation_registry.json"] if tactical else []
        if name in opponent_sources:
            evidence.extend(opponent_sources[name])
        if any(v.startswith(("korvold/", "rogshai/", "kaervek/")) for v in rec["deck_versions"]):
            evidence.append("data/canonical_import/2026-08-07/deck_lists.json")
        oc = oracle.get(name, {})
        item = {
            "oracle_name": name,
            "oracle_id": oc.get("oracle_id"),
            "deck_versions": sorted(set(rec["deck_versions"])),
            "roles": roles.get(name, [rec.get("canonical_role")] if rec.get("canonical_role") else []),
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
            "fallback_policy": "tactical_oracle" if tactical else "structural_only" if structural else "unsupported",
            "coverage_status": status,
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
            if cards else True
            for i in found
        )
        # Interaction-only stack/APNAP cases are validated by the tactical corpus.
        if not cards and found:
            tactical = True
        scenarios.append({
            "scenario_id": scenario_id,
            "cards": cards,
            "interaction_ids": found,
            "structural_support": bool(cards or found),
            "tactical_oracle_support": tactical,
            "xmage_verified": False,
            "forge_verified": False,
            "external_replay_verified": False,
            "coverage_status": "tactical_only" if tactical else "structural_only" if (cards or found) else "unsupported",
            "evidence_files": ["data/rules/project_critical_interactions.json"] if found else [],
        })

    deck_stats: dict[str, Any] = {}
    for deck in deck_map.values():
        rows = [r for r in coverage if deck in r["deck_versions"]]
        counts = defaultdict(int)
        for row in rows:
            counts[row["coverage_status"]] += 1
        deck_stats[deck] = {"unique_oracle_names": len(rows), "coverage": dict(counts)}

    card_registry = {
        "schema_version": 1,
        "generated_from_read_only_canonical_drive_snapshot": True,
        "external_engine_execution_status": "blocked",
        "cards": coverage,
        "deck_statistics": deck_stats,
    }
    scenario_registry = {
        "schema_version": 1,
        "external_engine_execution_status": "blocked",
        "scenarios": scenarios,
    }
    unsupported = [r for r in coverage if r["coverage_status"] == "unsupported"]
    differences = {
        "schema_version": 1,
        "status": "not_run",
        "provider_comparisons": [],
        "reason": "No real XMage or Forge execution was available.",
    }
    (out / "CARD_RULES_COVERAGE.json").write_text(json.dumps(card_registry, indent=2, ensure_ascii=False) + "\n")
    (out / "GOLDEN_RULES_SCENARIOS.json").write_text(json.dumps(scenario_registry, indent=2, ensure_ascii=False) + "\n")
    (out / "UNSUPPORTED_CARD_REGISTER.json").write_text(json.dumps({"cards": unsupported}, indent=2, ensure_ascii=False) + "\n")
    (out / "PROVIDER_DIFFERENCE_REGISTER.json").write_text(json.dumps(differences, indent=2) + "\n")
    (root / "data/rules/card_rules_coverage.json").write_text(json.dumps(card_registry, indent=2, ensure_ascii=False) + "\n")
    (root / "data/rules/golden_rules_scenarios.json").write_text(json.dumps(scenario_registry, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"cards": len(coverage), "scenarios": len(scenarios), "deck_statistics": deck_stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

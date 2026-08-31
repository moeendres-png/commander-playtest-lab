#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ws25_generate_forge_broad_provider as ws25


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


def render(source: str, forge_commit: str, forge_tree: str) -> tuple[str, dict]:
    java, mapping = ws25.render_ws25(source, forge_commit, forge_tree)

    java = replace_once(
        java,
        '                labels.add("PLAYER");',
        '                labels.add("PLAYER:" + p.getName());',
        "semantic starting-player labels",
    )
    java = replace_once(
        java,
        "        Broker broker = new Broker(in, out, 100000);",
        "        String stopAfter = System.getenv(\"COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY\");\n"
        "        int stopAfterPriority = stopAfter == null ? 100000 : Integer.parseInt(stopAfter);\n"
        "        Broker broker = new Broker(in, out, stopAfterPriority);",
        "priority stop configuration",
    )
    java = replace_once(
        java,
        '            Deck deck = new Deck("WS23-SEAT-" + i);\n'
        "            deck.getMain().add(PaperCard.FAKE_CARD, 40);",
        '            Deck deck = new Deck("FINALIST-SEAT-" + i);\n'
        '            forge.StaticData cardData = forge.StaticData.instance();\n'
        '            PaperCard mountain = cardData.getOrLoadCommonCard("Mountain", "10E", 1, false);\n'
        '            PaperCard commander = cardData.getOrLoadCommonCard("Rograkh, Son of Rohgahh", "CMR", 1, false);\n'
        '            if (mountain == null || commander == null) throw new ControlledStop("FINALIST_CANONICAL_DECK_CARD_MISSING");\n'
        "            deck.getMain().add(mountain, 99);\n"
        "            deck.getOrCreate(forge.deck.DeckSection.Commander).add(commander, 1);",
        "canonical commander deck construction",
    )
    java = replace_once(
        java,
        "    static String sessionSnapshot(Game game) {",
        "    static String singleCommandName(Player player) {\n"
        "        java.util.List<Card> command = new java.util.ArrayList<>(player.getCardsIn(ZoneType.Command));\n"
        "        if (command.size() != 1) return null;\n"
        "        return command.get(0).getName();\n"
        "    }\n\n"
        "    static String sessionSnapshot(Game game) {",
        "command snapshot helper",
    )
    java = replace_once(
        java,
        '                .append(",\\\"library_count\\\":").append(p.getCardsIn(ZoneType.Library).size())\n'
        '                .append("}");',
        '                .append(",\\\"library_count\\\":").append(p.getCardsIn(ZoneType.Library).size())\n'
        '                .append(",\\\"command_count\\\":").append(p.getCardsIn(ZoneType.Command).size())\n'
        '                .append(",\\\"commander\\\":").append(esc(singleCommandName(p)))\n'
        '                .append("}");',
        "native command-zone snapshot",
    )

    mapping = dict(mapping)
    mapping["schema_version"] = "finalist-forge-provider-overlay/1.0.0"
    mapping["base_schema_version"] = "ws25-player-controller-broad-mapping/1.0.0"
    mapping["canonical_natural_start_deck"] = {
        "commander": "Rograkh, Son of Rohgahh",
        "mainboard": {"Mountain": 99},
        "card_loading": "StaticData.getOrLoadCommonCard with explicit native print sets in GPL-side JVM",
        "prints": {"Mountain": "10E:1", "Rograkh, Son of Rohgahh": "CMR:1"},
    }
    mapping["semantic_starting_player_labels"] = True
    mapping["rules_seed_source"] = "COMMANDER_LAB_FORGE_RULES_SEED via Ws23ForgeBootstrap"
    mapping["stop_after_priority_source"] = "COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"
    return java, mapping


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player-controller", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--forge-commit", required=True)
    ap.add_argument("--forge-tree", required=True)
    args = ap.parse_args()

    source = args.player_controller.read_text(encoding="utf-8")
    java, mapping = render(source, args.forge_commit, args.forge_tree)
    out = args.output_dir
    java_dir = out / "java" / "forge" / "game" / "player"
    java_dir.mkdir(parents=True, exist_ok=True)
    (java_dir / "Ws23ForgeVerticalProvider.java").write_text(java, encoding="utf-8")
    (out / "finalist_forge_provider_mapping.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "abstract_method_count": mapping["abstract_method_count"],
        "player_count_range": mapping["player_count_range"],
        "schema_version": mapping["schema_version"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

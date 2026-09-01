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
        'return broker.chooseBoolean("mulliganKeepHand", player, "KEEP", "MULLIGAN");',
        'return broker.chooseBoolean("mulliganKeepHand", this.player, "KEEP", "MULLIGAN");',
        "mulligan decision actor",
    )
    java = replace_once(
        java,
        '''        <T> T chooseObject(String kind, Player actor, java.util.List<T> options, boolean optional) {
            java.util.List<String> labels = new ArrayList<>();
            if (optional) labels.add("NONE");
            for (int i = 0; i < options.size(); i++) labels.add("NATIVE_OPTION");
            String id = choose(kind, actor, labels);
            int idx = Integer.parseInt(id.substring(1));
            if (optional) {
                if (idx == 0) return null;
                idx--;
            }
            return options.get(idx);
        }
''',
        '''        <T> T chooseObject(String kind, Player actor, java.util.List<T> options, boolean optional) {
            if (!optional) {
                if (options.isEmpty()) throw new ControlledStop("FINALIST_ZERO_NATIVE_OPTIONS:" + kind);
                if (options.size() == 1) {
                    recordAutomatic("SINGLE_NATIVE_OPTION:" + kind);
                    return options.get(0);
                }
            }
            java.util.List<String> labels = new ArrayList<>();
            if (optional) labels.add("NONE");
            for (int i = 0; i < options.size(); i++) labels.add("NATIVE_OPTION");
            String id = choose(kind, actor, labels);
            int idx = Integer.parseInt(id.substring(1));
            if (optional) {
                if (idx == 0) return null;
                idx--;
            }
            return options.get(idx);
        }
''',
        "mandatory singleton object choice",
    )
    java = replace_once(
        java,
        '''        @Override
        public void playSpellAbilityNoStack(SpellAbility effectSA, boolean mayChoseNewTargets) {
            throw failClosed("playSpellAbilityNoStack");
        }''',
        '''        @Override
        public void playSpellAbilityNoStack(SpellAbility effectSA, boolean mayChoseNewTargets) {
            PlaySpellAbility.playSpellAbilityNoStack(this, player, effectSA, !mayChoseNewTargets);
        }''',
        "native no-stack ability execution",
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
        "        for (int i = 1; i <= requestedPlayers; i++) {",
        '        String finalistLanguagesDirectory = System.getenv("COMMANDER_LAB_FORGE_LANG_DIR");\n'
        '        if (finalistLanguagesDirectory == null || finalistLanguagesDirectory.isBlank()) throw new ControlledStop("FINALIST_FORGE_LANG_DIR_MISSING");\n'
        '        java.nio.file.Path finalistLanguages = java.nio.file.Path.of(finalistLanguagesDirectory).toAbsolutePath().normalize();\n'
        '        java.nio.file.Path finalistRoot = finalistLanguages.getParent().getParent().getParent();\n'
        '        forge.CardStorageReader finalistReader = new forge.CardStorageReader(finalistRoot.resolve("forge-gui/res/cardsfolder").toString(), null, true);\n'
        '        forge.card.CardRules finalistMountainRules = finalistReader.attemptToLoadCard("Mountain");\n'
        '        forge.card.CardRules finalistCommanderRules = finalistReader.attemptToLoadCard("Rograkh, Son of Rohgahh");\n'
        '        if (finalistMountainRules == null || finalistCommanderRules == null) throw new ControlledStop("FINALIST_CANONICAL_DECK_RULES_MISSING");\n'
        "        for (int i = 1; i <= requestedPlayers; i++) {",
        "headless direct card-rules loader",
    )
    java = replace_once(
        java,
        '            Deck deck = new Deck("WS23-SEAT-" + i);\n'
        "            deck.getMain().add(PaperCard.FAKE_CARD, 40);",
        '            Deck deck = new Deck("FINALIST-SEAT-" + i);\n'
        '            PaperCard mountain = new PaperCard(finalistMountainRules, "10E", forge.card.CardRarity.BasicLand);\n'
        '            PaperCard commander = new PaperCard(finalistCommanderRules, "CMR", forge.card.CardRarity.Uncommon);\n'
        "            deck.getMain().add(mountain, 99);\n"
        "            deck.getOrCreate(forge.deck.DeckSection.Commander).add(commander, 1);",
        "canonical commander deck construction",
    )
    java = replace_once(
        java,
        "            RegisteredPlayer rp = new RegisteredPlayer(deck);",
        "            RegisteredPlayer rp = RegisteredPlayer.forCommander(deck);",
        "native Commander registration",
    )
    java = replace_once(
        java,
        "    static String sessionSnapshot(Game game) {",
        "    static String singleCommanderName(Player player) {\n"
        "        java.util.List<Card> commanders = player.getCommanders();\n"
        "        if (commanders.size() != 1) return null;\n"
        "        return commanders.get(0).getName();\n"
        "    }\n\n"
        "    static String sessionSnapshot(Game game) {",
        "commander semantic snapshot helper",
    )
    java = replace_once(
        java,
        '                .append(",\\\"library_count\\\":").append(p.getCardsIn(ZoneType.Library).size())\n'
        '                .append("}");',
        '                .append(",\\\"library_count\\\":").append(p.getCardsIn(ZoneType.Library).size())\n'
        '                .append(",\\\"command_count\\\":").append(p.getCommanders().size())\n'
        '                .append(",\\\"commander\\\":").append(esc(singleCommanderName(p)))\n'
        '                .append("}");',
        "native commander semantic snapshot",
    )

    mapping = dict(mapping)
    callbacks = []
    for callback in mapping.get("callbacks", []):
        callback = dict(callback)
        if callback.get("name") == "playSpellAbilityNoStack":
            callback["classification"] = "RULES_AUTOMATIC_NONDISCRETIONARY"
        callbacks.append(callback)
    mapping["callbacks"] = callbacks
    mapping["schema_version"] = "finalist-forge-provider-overlay/1.0.0"
    mapping["base_schema_version"] = "ws25-player-controller-broad-mapping/1.0.0"
    mapping["canonical_natural_start_deck"] = {
        "commander": "Rograkh, Son of Rohgahh",
        "mainboard": {"Mountain": 99},
        "card_loading": "CardStorageReader.attemptToLoadCard -> PaperCard in GPL-side JVM; no image-selection path",
        "prints": {"Mountain": "10E:BasicLand", "Rograkh, Son of Rohgahh": "CMR:Uncommon"},
        "registration": "RegisteredPlayer.forCommander",
    }
    mapping["commander_semantic_projection"] = "Player.getCommanders(); excludes Forge-owned Commander Effect object in ZoneType.Command"
    mapping["semantic_starting_player_labels"] = True
    mapping["mulligan_actor_binding"] = "controller-owned this.player; Forge MulliganService passes firstPlayer as the method argument"
    mapping["mandatory_singleton_object_choice"] = "zero native options fail closed; one mandatory native option resolves automatically; multiple options remain external"
    mapping["no_stack_execution"] = "PlaySpellAbility.playSpellAbilityNoStack; nested discretionary choices remain controller-mediated"
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

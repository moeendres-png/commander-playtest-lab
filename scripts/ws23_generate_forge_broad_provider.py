#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

base = importlib.import_module("ws23_generate_forge_vertical_provider")

EXTRA_EXTERNAL = {"chooseCardsToDiscardToMaximumHandSize"}


def broad_method_body(original, name: str) -> list[str]:
    if name == "chooseCardsToDiscardToMaximumHandSize":
        return [
            'if (numDiscard != 1) throw failClosed("chooseCardsToDiscardToMaximumHandSize:NUM_NOT_ONE");',
            "java.util.List<Card> hand = new java.util.ArrayList<>();",
            "for (Card card : player.getCardsIn(ZoneType.Hand)) hand.add(card);",
            'if (hand.isEmpty()) throw failClosed("chooseCardsToDiscardToMaximumHandSize:EMPTY");',
            'Card chosen = broker.chooseObject("discardToMaximumHandSize", player, hand, false);',
            "return new CardCollection(chosen);",
        ]
    return original(name)


def render_broad(source: str, forge_commit: str, forge_tree: str) -> tuple[str, dict]:
    original_body = base.method_body
    original_external = set(base.EXTERNALLY_IMPLEMENTED)
    try:
        base.method_body = lambda name: broad_method_body(original_body, name)
        base.EXTERNALLY_IMPLEMENTED |= EXTRA_EXTERNAL
        java, mapping = base.render(source, forge_commit, forge_tree)
    finally:
        base.method_body = original_body
        base.EXTERNALLY_IMPLEMENTED.clear()
        base.EXTERNALLY_IMPLEMENTED.update(original_external)

    old_rules = "        GameRules rules = new GameRules(GameType.Constructed);"
    new_rules = (
        "        GameRules rules = new GameRules(GameType.Constructed);\n"
        "        rules.addAppliedVariant(GameType.Commander);"
    )
    if old_rules not in java:
        raise RuntimeError("base GameRules construction changed")
    java = java.replace(old_rules, new_rules, 1)

    old_budget = "        Broker broker = new Broker(in, out, 16);"
    if old_budget not in java:
        raise RuntimeError("base broker construction changed")
    java = java.replace(old_budget, "        Broker broker = new Broker(in, out, 100000);", 1)

    old_loop = "        for (int i = 1; i <= 4; i++) {"
    new_loop = (
        '        String requestedPlayerCount = System.getenv("COMMANDER_LAB_FORGE_PLAYER_COUNT");\n'
        "        int requestedPlayers = requestedPlayerCount == null\n"
        "            ? 4 : Integer.parseInt(requestedPlayerCount);\n"
        "        if (requestedPlayers < 2 || requestedPlayers > 5) {\n"
        '            throw new ControlledStop("WS23_BROAD_PLAYER_COUNT_OUT_OF_RANGE");\n'
        "        }\n"
        "        for (int i = 1; i <= requestedPlayers; i++) {"
    )
    if old_loop not in java:
        raise RuntimeError("base player-count loop changed")
    java = java.replace(old_loop, new_loop, 1)

    mapping["schema_version"] = "ws23-player-controller-broad-mapping/1.0.0"
    mapping["support_scope"] = "BROAD_PLAYER_COUNT_LIFECYCLE"
    mapping["player_count_range"] = [2, 3, 4, 5]
    mapping["full_lifecycle_policy"] = "PASS_ONLY_IF_FORGE_GAME_RETURNED"
    mapping["cleanup_discard_policy"] = (
        "EXTERNAL_SINGLE_CARD_CHOICE_FROM_FORGE_OWN_HAND_OPTIONS_OTHER_COUNTS_FAIL_CLOSED"
    )
    return java, mapping


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player-controller", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--forge-commit", required=True)
    ap.add_argument("--forge-tree", required=True)
    args = ap.parse_args()

    source = args.player_controller.read_text(encoding="utf-8")
    java, mapping = render_broad(source, args.forge_commit, args.forge_tree)
    out = args.output_dir
    java_dir = out / "java" / "forge" / "game" / "player"
    java_dir.mkdir(parents=True, exist_ok=True)
    (java_dir / "Ws23ForgeVerticalProvider.java").write_text(java, encoding="utf-8")
    (out / "player_controller_broad_mapping.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "abstract_method_count": mapping["abstract_method_count"],
                "player_count_range": mapping["player_count_range"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

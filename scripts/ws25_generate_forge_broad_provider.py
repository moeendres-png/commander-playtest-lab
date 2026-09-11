#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

base = importlib.import_module("ws23_generate_forge_vertical_provider")

EXTRA_EXTERNAL = {
    "chooseCardsToDiscardToMaximumHandSize",
    "tuckCardsViaMulligan",
}


def choose_cards_body(kind: str, count_expr: str, source_expr: str, result_type: str) -> list[str]:
    return [
        f"int ws25Count = {count_expr};",
        f"java.util.List<Card> ws25Remaining = new java.util.ArrayList<>({source_expr});",
        f'if (ws25Count < 0 || ws25Count > ws25Remaining.size()) throw failClosed("{kind}:COUNT_OUT_OF_RANGE");',
        f"{result_type} ws25Chosen = new {result_type}();",
        "for (int ws25Index = 0; ws25Index < ws25Count; ws25Index++) {",
        f'    Card ws25Card = broker.chooseObject("{kind}", player, ws25Remaining, false);',
        "    if (!ws25Remaining.remove(ws25Card)) throw failClosed(\"WS25_CARD_SELECTION_STALE\");",
        "    ws25Chosen.add(ws25Card);",
        "}",
        "return ws25Chosen;",
    ]


def ws25_method_body(original, name: str) -> list[str]:
    if name == "chooseCardsToDiscardToMaximumHandSize":
        return choose_cards_body(
            "discardToMaximumHandSize",
            "numDiscard",
            "player.getCardsIn(ZoneType.Hand)",
            "CardCollection",
        )
    if name == "tuckCardsViaMulligan":
        return choose_cards_body(
            "tuckCardsViaMulligan",
            "cardsToReturn",
            "hand",
            "CardCollection",
        )
    return original(name)


def render_ws25(source: str, forge_commit: str, forge_tree: str) -> tuple[str, dict]:
    original_body = base.method_body
    original_external = set(base.EXTERNALLY_IMPLEMENTED)
    try:
        base.method_body = lambda name: ws25_method_body(original_body, name)
        base.EXTERNALLY_IMPLEMENTED |= EXTRA_EXTERNAL
        java, mapping = base.render(source, forge_commit, forge_tree)
    finally:
        base.method_body = original_body
        base.EXTERNALLY_IMPLEMENTED.clear()
        base.EXTERNALLY_IMPLEMENTED.update(original_external)

    replacements = (
        (
            "        GameRules rules = new GameRules(GameType.Constructed);",
            "        GameRules rules = new GameRules(GameType.Constructed);\n        rules.addAppliedVariant(GameType.Commander);",
            "GameRules construction",
        ),
        (
            "        Broker broker = new Broker(in, out, 16);",
            "        Broker broker = new Broker(in, out, 100000);",
            "broker construction",
        ),
        (
            "            if (idx == 0) return java.util.List.of();",
            "            if (idx == 0) return null;",
            "priority pass",
        ),
    )
    for old, new, label in replacements:
        if old not in java:
            raise RuntimeError(f"base {label} changed")
        java = java.replace(old, new, 1)

    old_main_streams = (
        "        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));\n"
        "        PrintWriter out = new PrintWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8), true);"
    )
    new_main_streams = (
        "        java.io.PrintStream protocolStdout = System.out;\n"
        "        System.setOut(System.err);\n"
        "        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));\n"
        "        PrintWriter out = new PrintWriter(new OutputStreamWriter(protocolStdout, StandardCharsets.UTF_8), true);"
    )
    if old_main_streams not in java:
        raise RuntimeError("base protocol stdout construction changed")
    java = java.replace(old_main_streams, new_main_streams, 1)

    old_loop = "        for (int i = 1; i <= 4; i++) {"
    new_loop = (
        '        String requestedPlayerCount = System.getenv("COMMANDER_LAB_FORGE_PLAYER_COUNT");\n'
        "        int requestedPlayers = requestedPlayerCount == null ? 4 : Integer.parseInt(requestedPlayerCount);\n"
        "        if (requestedPlayers < 2 || requestedPlayers > 5) {\n"
        '            throw new ControlledStop("WS25_BROAD_PLAYER_COUNT_OUT_OF_RANGE");\n'
        "        }\n"
        "        for (int i = 1; i <= requestedPlayers; i++) {"
    )
    if old_loop not in java:
        raise RuntimeError("base player-count loop changed")
    java = java.replace(old_loop, new_loop, 1)

    mapping["schema_version"] = "ws25-player-controller-broad-mapping/1.0.0"
    mapping["support_scope"] = "BROAD_PLAYER_COUNT_LIFECYCLE_PLUS_MULTI_CARD_CLEANUP_AND_MULLIGAN_TUCK"
    mapping["player_count_range"] = [2, 3, 4, 5]
    mapping["full_lifecycle_policy"] = "PASS_ONLY_IF_FORGE_GAME_RETURNED"
    mapping["priority_pass_semantics"] = "FORGE_PHASE_HANDLER_NULL_MEANS_PASS"
    mapping["protocol_stdout_exclusive"] = True
    mapping["cleanup_discard_policy"] = "EXTERNAL_EXACT_COUNT_SELECTION_FROM_FORGE_OWN_HAND_OPTIONS"
    mapping["mulligan_tuck_policy"] = "EXTERNAL_EXACT_COUNT_SELECTION_FROM_FORGE_PROVIDED_HAND_OPTIONS"
    return java, mapping


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player-controller", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--forge-commit", required=True)
    ap.add_argument("--forge-tree", required=True)
    args = ap.parse_args()

    source = args.player_controller.read_text(encoding="utf-8")
    java, mapping = render_ws25(source, args.forge_commit, args.forge_tree)
    out = args.output_dir
    java_dir = out / "java" / "forge" / "game" / "player"
    java_dir.mkdir(parents=True, exist_ok=True)
    (java_dir / "Ws23ForgeVerticalProvider.java").write_text(java, encoding="utf-8")
    (out / "player_controller_ws25_broad_mapping.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"abstract_method_count": mapping["abstract_method_count"], "player_count_range": mapping["player_count_range"]}, sort_keys=True))


if __name__ == "__main__":
    main()

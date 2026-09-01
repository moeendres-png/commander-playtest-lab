#!/usr/bin/env python3
"""Bind MICRO_REPLACEMENT overlay to exact pinned XMage Combat APIs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, observed {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = SCENARIO.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '        requireNative(combat.isAttacker(attackerId), "combat-attacker:" + attackerSemantic);\n'
        '        requireNative(combat.getDefenderId(attackerId).equals(defender.getId()), "combat-defender:" + defenderRef);\n'
        '        requireNative(combat.getGroups().size() == 1, "combat-group-cardinality");\n'
        '        requireNative(combat.getGroups().get(0).getBlockers().isEmpty(), "combat-unblocked");\n',
        '        requireNative(combat.getAttackers().contains(attackerId), "combat-attacker:" + attackerSemantic);\n'
        '        requireNative(combat.getGroups().size() == 1, "combat-group-cardinality");\n'
        '        requireNative(combat.getGroups().get(0).getDefenderId().equals(defender.getId()), "combat-defender:" + defenderRef);\n'
        '        requireNative(combat.getGroups().get(0).getAttackers().contains(attackerId), "combat-group-attacker");\n'
        '        requireNative(combat.getGroups().get(0).getBlockers().isEmpty(), "combat-unblocked");\n',
        "combat API validation",
    )
    text = replace_once(
        text,
        '    private static JsonObject findCardSpec(JsonObject scenario, String semantic) {\n',
        '    private static int playerSeatValue(String player, int playerCount) {\n'
        '        if (player == null || !player.matches("P[1-9][0-9]*")) {\n'
        '            throw fail("INVALID_PLAYER_IDENTITY: " + player);\n'
        '        }\n'
        '        int seat = Integer.parseInt(player.substring(1));\n'
        '        if (seat < 1 || seat > playerCount) throw fail("INVALID_PLAYER_IDENTITY: " + player);\n'
        '        return seat;\n'
        '    }\n\n'
        '    private static JsonObject findCardSpec(JsonObject scenario, String semantic) {\n',
        "player seat parser",
    )
    SCENARIO.write_text(text, encoding="utf-8")
    print("XMAGE_MICRO_REPLACEMENT_API_FIX=PASS")


if __name__ == "__main__":
    main()

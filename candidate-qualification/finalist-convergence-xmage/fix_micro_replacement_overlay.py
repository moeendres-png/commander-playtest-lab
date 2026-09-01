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
    # playerSeatValue(String,int) is already supplied by the MICRO_STACK overlay
    # applied immediately before this one; reusing it keeps one authority for
    # canonical Pn parsing and avoids duplicate generated methods.
    if text.count("private static int playerSeatValue(String player, int playerCount)") != 1:
        raise RuntimeError("existing player seat parser cardinality changed")
    SCENARIO.write_text(text, encoding="utf-8")
    print("XMAGE_MICRO_REPLACEMENT_API_FIX=PASS")


if __name__ == "__main__":
    main()

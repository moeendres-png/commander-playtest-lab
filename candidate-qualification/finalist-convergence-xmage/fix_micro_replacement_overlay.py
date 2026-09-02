#!/usr/bin/env python3
"""Bind finalist overlays to exact pinned XMage APIs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, observed {count}")
    return text.replace(old, new, 1)


def fix_micro_replacement(text: str) -> str:
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
    return text


def fix_ws05_control_duration(text: str) -> str:
    old = '''            JsonArray eligibleSemantic = new JsonArray();
            for (JsonElement item : eligible) {
'''
    new = '''            JsonArray eligibleSemantic = new JsonArray();

            // Frozen v1.0.1 does not mark the common baseline Bears as
            // controlled since the turn began.  Reconstruct that native XMage
            // control-duration state rather than filtering the creature from
            // Player.getAvailableAttackers(Game).  The temporary transition is
            // qualification-state loading only; both the permanent controller
            // and its native ability/continuous-effect controller state are
            // restored through checkControlChanged before legality is queried.
            Permanent baselineBears = game.getPermanent(nativeId(semanticMap, "obj:P1-bears"));
            if (baselineBears == null || !active.getId().equals(baselineBears.getControllerId())) {
                throw fail("NATIVE_VALIDATION_FAILED: baseline Bears missing or wrong controller");
            }
            UUID temporaryController = players.stream()
                    .map(Player::getId)
                    .filter(id -> !id.equals(active.getId()))
                    .findFirst()
                    .orElseThrow(() -> fail("NATIVE_VALIDATION_FAILED: no temporary control-state seat"));
            baselineBears.resetControl();
            baselineBears.setControllerId(temporaryController);
            requireNative(baselineBears.checkControlChanged(game), "baseline-bears-control-duration-reset");
            baselineBears.resetControl();
            requireNative(baselineBears.checkControlChanged(game), "baseline-bears-controller-restore");
            requireNative(active.getId().equals(baselineBears.getControllerId()), "baseline-bears-controller-final");
            requireNative(!baselineBears.wasControlledFromStartOfControllerTurn(), "baseline-bears-control-duration-final");
            requireNative(baselineBears.hasSummoningSickness(), "baseline-bears-summoning-sickness");
            requireNative(!baselineBears.canAttack(null, game), "baseline-bears-not-eligible");

            for (JsonElement item : eligible) {
'''
    return replace_once(text, old, new, "WS05 baseline Bears control duration")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--micro-replacement"
    text = SCENARIO.read_text(encoding="utf-8")
    if mode == "--micro-replacement":
        text = fix_micro_replacement(text)
        marker = "XMAGE_MICRO_REPLACEMENT_API_FIX=PASS"
    elif mode == "--ws05-control-duration":
        text = fix_ws05_control_duration(text)
        marker = "XMAGE_WS05_CONTROL_DURATION_FIX=PASS"
    else:
        raise RuntimeError(f"unsupported mode: {mode}")
    SCENARIO.write_text(text, encoding="utf-8")
    print(marker)


if __name__ == "__main__":
    main()

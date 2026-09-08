#!/usr/bin/env python3
"""Apply source-proven WS46 native-construction corrections before bridge build.

This patch is intentionally narrow and fail-closed.  It repairs only two
already-audited implementation defects in the newly added WS46 class:
1) bind immutable v1.0.4 extra-turn field names exactly;
2) derive combat eligibility from the already-bound native attacking Player,
   avoiding dependence on temporal-state installation order.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs46NativeConstructionState.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS46_NATIVE_CLASS_FIX_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '        JsonObject readback = readCombat(game, players, semanticMap);\n',
        '        JsonObject readback = readCombat(game, players, semanticMap, attacker);\n',
        "combat-readback-attacker-argument",
    )
    text = replace_once(
        text,
        '    private static JsonObject readCombat(\n'
        '            Game game,\n'
        '            List<? extends Player> players,\n'
        '            Map<UUID, String> semanticMap\n'
        '    ) {\n',
        '    private static JsonObject readCombat(\n'
        '            Game game,\n'
        '            List<? extends Player> players,\n'
        '            Map<UUID, String> semanticMap,\n'
        '            Player attackingPlayer\n'
        '    ) {\n',
        "combat-readback-signature",
    )
    text = replace_once(
        text,
        '''        Player attackingPlayer = game.getPlayer(game.getActivePlayerId());
        if (attackingPlayer == null) {
            JsonObject temporalAttacker = new JsonObject();
            // Native temporal state is applied by WS42 immediately after this
            // extension.  For construction legality discovery use Combat's own
            // attacker identity if active-player state is not yet installed.
            for (Player player : players) {
                for (UUID defender : combat.getDefenders()) {
                    if (player.getAvailableAttackers(defender, game).stream().anyMatch(p -> semanticMap.containsKey(p.getId()))) {
                        attackingPlayer = player;
                        break;
                    }
                }
                if (attackingPlayer != null) break;
            }
        }
''',
        '''        // The attacking player is the exact native Player bound from
        // the immutable temporal active-player snapshot in applyCombat().  Do
        // not depend on GameState.activePlayer installation order here.
''',
        "combat-remove-temporal-order-fallback",
    )

    text = replace_once(
        text,
        '            int sequence = requireInt(spec, "sequence");\n',
        '            int sequence = requireInt(spec, "resolution_sequence");\n',
        "extra-turn-sequence-key",
    )
    text = replace_once(
        text,
        '            String source = requireString(spec, "source");\n',
        '            String source = requireString(spec, "source_object");\n',
        "extra-turn-source-key",
    )
    text = replace_once(
        text,
        '            row.addProperty("sequence", Integer.parseInt(parts[1]));\n'
        '            row.addProperty("source", parts[2]);\n',
        '            row.addProperty("resolution_sequence", Integer.parseInt(parts[1]));\n'
        '            row.addProperty("source_object", parts[2]);\n',
        "extra-turn-readback-keys",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("WS46_NATIVE_CLASS_FIXES=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Wire WS42 qualification-only native snapshot extensions after WS39 overlays.

The extension restores only explicit requested snapshot fields through XMage
native APIs and performs independent readback validation. It does not implement
Magic legality or choose actions.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"
SESSION = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26QualificationSession.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS42_NATIVE_EXTENSION_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def patch_scenario() -> None:
    text = SCENARIO.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '            "commander_history", "stack_state"\n    );',
        '            "commander_history", "stack_state",\n'
        '            "ws42_combat_state", "ws42_extra_turn_creation",\n'
        '            "ws42_elimination_trigger", "ws42_zone_move_event",\n'
        '            "ws42_knowledge_state", "ws42_commander_damage_matrix",\n'
        '            "ws42_revealed_state"\n    );',
        "top-level-extension-keys",
    )

    text = replace_once(
        text,
        '            "semantic_id", "card_name", "tapped", "controller_seat", "face", "face_down",\n'
        '            "zone_position", "controlled_since_turn_began"\n'
        '    );',
        '            "semantic_id", "card_name", "tapped", "controller_seat", "face", "face_down",\n'
        '            "zone_position", "controlled_since_turn_began", "counters", "attached_to"\n'
        '    );',
        "card-extension-fields",
    )

    text = replace_once(
        text,
        '            "attached_to", "counters", "known_to", "native_object_id",\n'
        '            "mana", "priority_holder", "active_player", "turn", "phase", "step"\n',
        '            "known_to", "native_object_id",\n'
        '            "mana", "priority_holder", "active_player", "turn", "phase", "step"\n',
        "remove-native-extension-unsupported-fields",
    )

    old_controller = '''                    if (card.has("controller_seat") && !card.get("controller_seat").isJsonNull()
                            && integer(card, "controller_seat") != seat) {
                        throw fail("UNSUPPORTED_SCENARIO_DIMENSION: non-owner controller assignment");
                    }
'''
    new_controller = '''                    if (card.has("controller_seat") && !card.get("controller_seat").isJsonNull()) {
                        int controllerSeat = integer(card, "controller_seat");
                        if (controllerSeat < 1 || controllerSeat > players.size()) {
                            throw fail("INVALID_SCENARIO: controller_seat out of range");
                        }
                    }
'''
    text = replace_once(text, old_controller, new_controller, "controller-preflight")

    text = replace_once(
        text,
        '            if (life <= 0) throw fail("INVALID_SCENARIO: life must be positive");\n',
        '            if (life < 0) throw fail("INVALID_SCENARIO: negative life is outside WS42 contract");\n',
        "allow-zero-life-snapshot",
    )
    text = replace_once(
        text,
        '            reset.put(Zone.OUTSIDE, "life:" + life);\n',
        '            reset.put(Zone.OUTSIDE, "life:" + Math.max(life, 1));\n',
        "bootstrap-life-nonzero",
    )

    text = replace_once(
        text,
        '        applyStackState(scenario, game, players, semanticMap);\n'
        '        JsonObject validation = validateNative(game, players, bySeat, semanticMap, ledger);\n',
        '        JsonObject ws42NativeExtensionValidation = XmageWs42NativeStateExtension.applySnapshotDimensions(\n'
        '                scenario, game, players, semanticMap\n'
        '        );\n'
        '        applyStackState(scenario, game, players, semanticMap);\n'
        '        JsonObject validation = validateNative(game, players, bySeat, semanticMap, ledger);\n'
        '        validation.add("ws42_native_state_extension", ws42NativeExtensionValidation);\n',
        "apply-native-extension",
    )

    text = replace_once(
        text,
        '            requireNative(player.getId().equals(permanent.getControllerId()), "battlefield-controller:" + semantic);\n',
        '            // WS42 validates exact controller state in XmageWs42NativeStateExtension.\n'
        '            // The legacy validator assumed owner==controller and therefore cannot remain authoritative here.\n',
        "remove-owner-controller-assumption",
    )

    SCENARIO.write_text(text, encoding="utf-8")


def patch_session() -> None:
    text = SESSION.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '                JsonObject temporal = XmageWs26Scenario.applyTemporalState(configuredScenario, game, players);\n',
        '                JsonObject temporal = XmageWs42NativeStateExtension.applyTemporalState(\n'
        '                        configuredScenario, game, players\n'
        '                );\n',
        "temporal-extension",
    )
    SESSION.write_text(text, encoding="utf-8")


def main() -> int:
    patch_scenario()
    patch_session()
    print("WS42_NATIVE_STATE_EXTENSION_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

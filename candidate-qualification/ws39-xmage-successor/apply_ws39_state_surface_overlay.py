#!/usr/bin/env python3
"""WS-39 qualification-only native snapshot support for reusable state dimensions.

Run after the Primitive-A/WS34/WS36/WS39 provider overlays. This transform only
uses XMage native state primitives and readback. It does not implement Magic
legality or choose any player action.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS39_STATE_SURFACE_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new)


def main() -> int:
    text = SCENARIO.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "import mage.game.permanent.Permanent;\n",
        "import mage.game.permanent.Permanent;\nimport mage.game.permanent.PermanentImpl;\n",
        "permanent-impl-import",
    )
    text = replace_once(
        text,
        '    private static final Set<String> CARD = Set.of("semantic_id", "card_name", "tapped", "controller_seat", "face", "face_down");\n',
        '    private static final Set<String> CARD = Set.of(\n'
        '            "semantic_id", "card_name", "tapped", "controller_seat", "face", "face_down",\n'
        '            "zone_position", "controlled_since_turn_began"\n'
        '    );\n',
        "card-fields",
    )

    validation_old = '''                    if (!"battlefield".equals(zone) && booleanValue(card, "face_down", false)) {
                        throw fail("INVALID_SCENARIO: face_down only applies to battlefield");
                    }
'''
    validation_new = validation_old + '''                    if (card.has("zone_position")) {
                        if (!"library".equals(zone)) {
                            throw fail("INVALID_SCENARIO: zone_position only applies to library");
                        }
                        if (integer(card, "zone_position") < 0) {
                            throw fail("INVALID_SCENARIO: negative zone_position");
                        }
                    }
                    if (card.has("controlled_since_turn_began")) {
                        if (!"battlefield".equals(zone)) {
                            throw fail("INVALID_SCENARIO: controlled_since_turn_began only applies to battlefield");
                        }
                        booleanValue(card, "controlled_since_turn_began", false);
                    }
'''
    text = replace_once(text, validation_old, validation_new, "card-dimension-preflight")

    state_old = '''                permanent.setTapped(booleanValue(cardSpec, "tapped", false));
                permanent.setFaceDown(booleanValue(cardSpec, "face_down", false), game);
'''
    state_new = state_old + '''                if (booleanValue(cardSpec, "controlled_since_turn_began", false)) {
                    if (!(permanent instanceof PermanentImpl permanentImpl)) {
                        throw fail("NATIVE_STATE_LOAD_UNSUPPORTED_PERMANENT_IMPL:" + text(cardSpec, "semantic_id"));
                    }
                    permanentImpl.removeSummoningSickness();
                }
'''
    text = replace_once(text, state_old, state_new, "controlled-since-load")

    zone_old = '''    private static void validateZone(
            Game game,
            Player player,
            JsonArray specs,
            Zone expected,
            Map<UUID, String> semanticMap
    ) {
        for (JsonElement element : specs) {
            String semantic = text(element.getAsJsonObject(), "semantic_id");
            UUID id = nativeId(semanticMap, semantic);
            requireNative(expected == game.getState().getZone(id), "zone:" + semantic);
            Card card = game.getCard(id);
            requireNative(card != null && player.getId().equals(card.getOwnerId()), "owner:" + semantic);
        }
    }
'''
    zone_new = '''    private static void validateZone(
            Game game,
            Player player,
            JsonArray specs,
            Zone expected,
            Map<UUID, String> semanticMap
    ) {
        for (JsonElement element : specs) {
            JsonObject spec = element.getAsJsonObject();
            String semantic = text(spec, "semantic_id");
            UUID id = nativeId(semanticMap, semantic);
            requireNative(expected == game.getState().getZone(id), "zone:" + semantic);
            Card card = game.getCard(id);
            requireNative(card != null && player.getId().equals(card.getOwnerId()), "owner:" + semantic);
            if (expected == Zone.LIBRARY && spec.has("zone_position")) {
                int expectedPosition = integer(spec, "zone_position");
                int actualPosition = player.getLibrary().getCardList().indexOf(id);
                requireNative(actualPosition == expectedPosition, "library-position:" + semantic);
            }
        }
    }
'''
    text = replace_once(text, zone_old, zone_new, "library-position-readback")

    battlefield_old = '''            requireNative(permanent.isFaceDown(game) == booleanValue(spec, "face_down", false), "battlefield-face-down:" + semantic);
'''
    battlefield_new = battlefield_old + '''            if (spec.has("controlled_since_turn_began")) {
                requireNative(
                        permanent.wasControlledFromStartOfControllerTurn()
                                == booleanValue(spec, "controlled_since_turn_began", false),
                        "battlefield-controlled-since-turn-began:" + semantic
                );
            }
'''
    text = replace_once(
        text,
        battlefield_old,
        battlefield_new,
        "controlled-since-readback",
    )

    SCENARIO.write_text(text, encoding="utf-8")
    print("WS39_STATE_SURFACE_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

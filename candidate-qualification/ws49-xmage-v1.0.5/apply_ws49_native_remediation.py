#!/usr/bin/env python3
"""Apply only freshly source-audited WS-49 XMage/provider construction repairs.

Must run after the inherited WS39 state-surface and WS46 v1.0.4 construction
overlays.  No Magic legality or discretionary policy is implemented here.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs46NativeConstructionState.java"
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS49_REMEDIATION_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def patch_native_state() -> None:
    text = NATIVE.read_text(encoding="utf-8")

    # Keep the later source-audited immutable shape.  The superseded WS46 fix
    # script must not rename these to resolution_sequence/source_object.
    required = (
        'int sequence = requireInt(spec, "sequence");',
        'String source = requireString(spec, "source");',
        'row.addProperty("sequence", Integer.parseInt(parts[1]));',
        'row.addProperty("source", parts[2]);',
    )
    for token in required:
        if token not in text:
            raise SystemExit(f"WS49_EXTRA_TURN_IMMUTABLE_SHAPE_REGRESSION:{token}")
    forbidden = ('"resolution_sequence"', '"source_object"')
    for token in forbidden:
        if token in text:
            raise SystemExit(f"WS49_EXTRA_TURN_SUPERSEDED_SHAPE_PRESENT:{token}")

    # Bind combat eligibility readback to the exact native attacking Player
    # already selected from immutable temporal state.  No heuristic fallback.
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
    old_fallback = '''        Player attackingPlayer = game.getPlayer(game.getActivePlayerId());
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
'''
    text = replace_once(
        text,
        old_fallback,
        '''        // Exact native attacking Player is supplied by applyCombat().
        // No active-player/order/first-match fallback is permitted here.
''',
        "combat-remove-fallback",
    )

    # Immutable v1.0.5 elimination entry uses reason, not condition.  Keep the
    # native pre-SBA boundary check (life == 0 and !hasLost()) untouched.  Use
    # narrow one-token replacements so formatting cannot turn a valid source
    # block into an anchor miss while still requiring each old token exactly
    # once and failing closed on any unexpected implementation drift.
    text = replace_once(
        text,
        '        String condition = requireString(requested, "condition");\n',
        '        String reason = requireString(requested, "reason");\n',
        "elimination-reason-key",
    )
    text = replace_once(
        text,
        '        if (!"life_total_0".equals(condition)) {\n',
        '        if (!"life_total_0".equals(reason)) {\n',
        "elimination-reason-value",
    )
    text = replace_once(
        text,
        '            throw fail("WS46_ELIMINATION_CONDITION_UNSUPPORTED:" + condition);\n',
        '            throw fail("WS49_ELIMINATION_REASON_UNSUPPORTED:" + reason);\n',
        "elimination-reason-error",
    )
    text = replace_once(
        text,
        '        result.addProperty("condition", "life_total_0");\n',
        '        result.addProperty("reason", "life_total_0");\n',
        "elimination-readback-key",
    )

    NATIVE.write_text(text, encoding="utf-8")


def patch_face_down_exile() -> None:
    text = SCENARIO.read_text(encoding="utf-8")

    # The native Card state supports face-down outside battlefield.  Permit only
    # the immutable surfaces actually required here: battlefield and exile.
    text = replace_once(
        text,
        '                    if (!"battlefield".equals(zone) && booleanValue(card, "face_down", false)) {\n'
        '                        throw fail("INVALID_SCENARIO: face_down only applies to battlefield");\n'
        '                    }\n',
        '                    if (!Set.of("battlefield", "exile").contains(zone) && booleanValue(card, "face_down", false)) {\n'
        '                        throw fail("INVALID_SCENARIO: face_down only applies to battlefield or exile");\n'
        '                    }\n',
        "face-down-exile-preflight",
    )

    # After native zone placement, set the exact exiled Card state through the
    # XMage Card API, then independently query it in validateZone().
    text = replace_once(
        text,
        '            game.cheat(player.getId(), insertion, hand, battlefield, grave, List.of(), exile);\n',
        '''            game.cheat(player.getId(), insertion, hand, battlefield, grave, List.of(), exile);
            for (JsonElement element : optionalArray(zones, "exile")) {
                JsonObject exileSpec = element.getAsJsonObject();
                if (!booleanValue(exileSpec, "face_down", false)) continue;
                UUID exileId = nativeId(semanticMap, text(exileSpec, "semantic_id"));
                Card exileCard = game.getCard(exileId);
                if (exileCard == null) throw fail("NATIVE_STATE_LOAD_EXILE_CARD_MISSING:" + text(exileSpec, "semantic_id"));
                exileCard.setFaceDown(true, game);
            }
''',
        "face-down-exile-native-apply",
    )

    text = replace_once(
        text,
        '            requireNative(card != null && player.getId().equals(card.getOwnerId()), "owner:" + semantic);\n'
        '            if (expected == Zone.LIBRARY && spec.has("zone_position")) {\n',
        '            requireNative(card != null && player.getId().equals(card.getOwnerId()), "owner:" + semantic);\n'
        '            if (expected == Zone.EXILED) {\n'
        '                requireNative(card.isFaceDown(game) == booleanValue(spec, "face_down", false), "exile-face-down:" + semantic);\n'
        '            }\n'
        '            if (expected == Zone.LIBRARY && spec.has("zone_position")) {\n',
        "face-down-exile-readback",
    )

    SCENARIO.write_text(text, encoding="utf-8")


def main() -> int:
    patch_native_state()
    patch_face_down_exile()
    print("WS49_NATIVE_REMEDIATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

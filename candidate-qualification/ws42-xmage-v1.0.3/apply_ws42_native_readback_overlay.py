#!/usr/bin/env python3
"""Install WS-42's request-independent native construction readback surface.

This qualification-only overlay runs after the inherited WS34/36/39 overlays.
It deliberately disconnects the WS34 whole-request construction echo from the
WS42 state endpoint. For NATIVE_STATE_LOAD it captures XMage state immediately
after native scenario validation and before priority/SBA continuation.

No Magic legality is implemented here; this is read-only evidence plumbing.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26QualificationSession.java"
REPLAY = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26ReplayRecorder.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS42_NATIVE_READBACK_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def patch_session() -> None:
    text = SESSION.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    private volatile XmageWs26ReplayRecorder replayRecorder;\n",
        "    private volatile XmageWs26ReplayRecorder replayRecorder;\n"
        "    private volatile JsonObject ws42NativeConstructionSnapshot;\n",
        "snapshot-field",
    )
    text = replace_once(
        text,
        '''                replayRecorder = new XmageWs26ReplayRecorder(\n                        game, players, knowledgeLedger, appliedScenario.semanticObjectIds()\n                );\n                replayRecorder.checkpoint("after_native_setup_validation");\n''',
        '''                replayRecorder = new XmageWs26ReplayRecorder(\n                        game, players, knowledgeLedger, appliedScenario.semanticObjectIds()\n                );\n                ws42NativeConstructionSnapshot = replayRecorder.currentState();\n                replayRecorder.checkpoint("after_native_setup_validation");\n''',
        "capture-before-resume",
    )
    text = replace_once(
        text,
        '''        payload.add("rules_rng_tape", XmageWs26RulesRngTape.snapshot(seed));\n        addSuccessorConstructionProof(payload);\n        return payload;\n''',
        '''        payload.add("rules_rng_tape", XmageWs26RulesRngTape.snapshot(seed));\n        addWs42NativeConstructionReadback(payload);\n        return payload;\n''',
        "disconnect-ws34-echo",
    )
    helper_anchor = '''    private void addSuccessorConstructionProof(JsonObject payload) {\n'''
    helper = '''    private void addWs42NativeConstructionReadback(JsonObject payload) {\n        if (appliedScenario == null || appliedScenario.validation() == null\n                || !appliedScenario.validation().has("valid")\n                || !appliedScenario.validation().get("valid").getAsBoolean()) {\n            throw new IllegalStateException("WS42_NATIVE_SETUP_NOT_VALIDATED");\n        }\n        JsonObject readback = new JsonObject();\n        readback.addProperty("schema_version", "xmage-ws42-native-construction-readback/1.0.0");\n        readback.addProperty("execution_entry_mode", executionEntryMode);\n        readback.addProperty("rules_seed", seed);\n        readback.addProperty("starting_player_seat", startingPlayerSeat + 1);\n        readback.addProperty("starting_life", game.getStartingLife());\n        readback.addProperty("player_count", players.size());\n        readback.addProperty("request_object_copied_as_proof", false);\n        readback.add("native_validation", appliedScenario.validation().deepCopy());\n        readback.add("rules_rng_tape", XmageWs26RulesRngTape.snapshot(seed));\n        if (NATIVE_STATE_LOAD.equals(executionEntryMode)) {\n            if (ws42NativeConstructionSnapshot == null) {\n                throw new IllegalStateException("WS42_NATIVE_CONSTRUCTION_SNAPSHOT_MISSING");\n            }\n            readback.add("semantic_state", ws42NativeConstructionSnapshot.deepCopy());\n            readback.addProperty("snapshot_boundary", "AFTER_NATIVE_SETUP_VALIDATION_BEFORE_PRIORITY_RESUME");\n        } else {\n            readback.addProperty("snapshot_boundary", "NATURAL_START_REQUIRES_EXECUTOR_BOUNDARY");\n        }\n        payload.add("ws42_native_construction_readback", readback);\n    }\n\n    private void addSuccessorConstructionProof(JsonObject payload) {\n'''
    text = replace_once(text, helper_anchor, helper, "readback-helper")
    SESSION.write_text(text, encoding="utf-8")


def patch_replay() -> None:
    text = REPLAY.read_text(encoding="utf-8")
    controlled_anchor = '''                item.addProperty("face_down", permanent.isFaceDown(game));\n                item.addProperty("damage", permanent.getDamage());\n'''
    controlled_new = '''                item.addProperty("face_down", permanent.isFaceDown(game));\n                item.addProperty("controlled_since_turn_began", permanent.wasControlledFromStartOfControllerTurn());\n                if (permanent.getAttachedTo() != null) {\n                    String attachedSemantic = scenarioObjectIds.get(permanent.getAttachedTo());\n                    if (attachedSemantic != null) {\n                        item.addProperty("attached_to_semantic_id", attachedSemantic);\n                    }\n                }\n                item.addProperty("damage", permanent.getDamage());\n'''
    text = replace_once(text, controlled_anchor, controlled_new, "permanent-readback")
    REPLAY.write_text(text, encoding="utf-8")


def main() -> int:
    patch_session()
    patch_replay()
    print("WS42_NATIVE_READBACK_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

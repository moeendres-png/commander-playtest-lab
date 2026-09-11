#!/usr/bin/env python3
"""Wire the WS46 v1.0.4 construction extension after the WS42 overlay.

The WS42 implementation remains the bootstrap/native-state provenance. This
layer adds only the v1.0.4 construction surfaces source-audited in checkpoints
03C/03E. It must be applied after the WS42 native readback/state overlays.

For NATURAL_GAME_START, WS46 also exposes the already-existing live XMage
state at the first externally pending decision after real game.start(), before
any external submit. This is qualification-only evidence plumbing; no Magic
legality or player choice is implemented here.
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
        raise SystemExit(f"WS46_V104_OVERLAY_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def patch_scenario() -> None:
    text = SCENARIO.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '            "ws42_knowledge_state", "ws42_commander_damage_matrix",\n'
        '            "ws42_revealed_state"\n    );',
        '            "ws42_knowledge_state", "ws42_commander_damage_matrix",\n'
        '            "ws42_revealed_state", "ws46_contract_version",\n'
        '            "ws46_zone_move_entry"\n    );',
        "top-level-v104-keys",
    )

    text = replace_once(
        text,
        '        JsonObject ws42RevealedValidation = XmageWs42RevealedState.applyAndValidate(\n'
        '                scenario, game, semanticMap\n'
        '        );\n'
        '        applyStackState(scenario, game, players, semanticMap);\n',
        '        JsonObject ws42RevealedValidation = XmageWs42RevealedState.applyAndValidate(\n'
        '                scenario, game, semanticMap\n'
        '        );\n'
        '        JsonObject ws46NativeConstructionValidation = XmageWs46NativeConstructionState.applyAndValidate(\n'
        '                scenario, game, players, semanticMap, ledger\n'
        '        );\n'
        '        applyStackState(scenario, game, players, semanticMap);\n',
        "apply-v104-construction-extension",
    )

    text = replace_once(
        text,
        '        validation.add("ws42_revealed_state", ws42RevealedValidation);\n',
        '        validation.add("ws42_revealed_state", ws42RevealedValidation);\n'
        '        validation.add("ws46_native_construction_state", ws46NativeConstructionValidation);\n',
        "publish-v104-validation",
    )

    SCENARIO.write_text(text, encoding="utf-8")


def patch_natural_start_readback() -> None:
    text = SESSION.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''        } else {\n            readback.addProperty("snapshot_boundary", "NATURAL_START_REQUIRES_EXECUTOR_BOUNDARY");\n        }\n''',
        '''        } else if (XmageWs26Scenario.NATURAL_GAME_START.equals(executionEntryMode)) {\n            failIfEngineFailed();\n            if (isEngineTerminal()) {\n                throw new IllegalStateException("WS46_NATURAL_START_TERMINATED_BEFORE_FIRST_EXTERNAL_DECISION");\n            }\n            if (controller.pendingDecision() == null) {\n                throw new IllegalStateException("WS46_NATURAL_START_FIRST_EXTERNAL_DECISION_MISSING");\n            }\n            if (replayRecorder == null) {\n                throw new IllegalStateException("WS46_NATURAL_START_REPLAY_RECORDER_MISSING");\n            }\n            JsonObject naturalState = replayRecorder.currentState();\n            if (naturalState == null) {\n                throw new IllegalStateException("WS46_NATURAL_START_NATIVE_STATE_MISSING");\n            }\n            readback.add("semantic_state", naturalState.deepCopy());\n            readback.addProperty("pending_external_decision_present", true);\n            readback.addProperty("snapshot_boundary",\n                    "AFTER_NATURAL_GAME_START_AT_FIRST_EXTERNAL_DECISION_BEFORE_SUBMISSION");\n        } else {\n            throw new IllegalStateException("WS46_UNSUPPORTED_EXECUTION_ENTRY_MODE:" + executionEntryMode);\n        }\n''',
        "natural-start-first-decision-readback",
    )
    SESSION.write_text(text, encoding="utf-8")


def main() -> int:
    patch_scenario()
    patch_natural_start_readback()
    print("WS46_V104_CONSTRUCTION_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

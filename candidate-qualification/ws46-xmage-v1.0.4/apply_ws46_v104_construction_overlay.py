#!/usr/bin/env python3
"""Wire the WS46 v1.0.4 construction extension after the WS42 overlay.

The WS42 implementation remains the bootstrap/native-state provenance.  This
layer adds only the v1.0.4 construction surfaces source-audited in checkpoint
03C.  It must be applied after apply_ws42_native_state_extension_overlay.py.
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
        raise SystemExit(f"WS46_V104_OVERLAY_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def main() -> int:
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
    print("WS46_V104_CONSTRUCTION_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Apply exact qualification-only fixes for the v1.0.1 natural-start slice.

This does not alter the pinned XMage repository. It patches only Commander Lab's
qualification bridge/helper sources on the candidate branch before compilation.
Every replacement is exact/fail-closed so source drift cannot silently change
semantics.
"""
from __future__ import annotations

from pathlib import Path


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"OVERLAY_SOURCE_DRIFT:{path}:{old!r}")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    session = Path("engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26QualificationSession.java")
    replace_exact(
        session,
        """        GameOptions options = new GameOptions();\n        options.rollbackTurnsAllowed = false;\n        options.testMode = true;\n        String executionEntryMode = scenario.has(\"execution_entry_mode\")\n""",
        """        GameOptions options = new GameOptions();\n        options.rollbackTurnsAllowed = false;\n        String executionEntryMode = scenario.has(\"execution_entry_mode\")\n""",
    )
    replace_exact(
        session,
        """                : XmageWs26Scenario.NATIVE_STATE_LOAD;\n        options.skipInitShuffling = !XmageWs26Scenario.NATURAL_GAME_START.equals(executionEntryMode);\n""",
        """                : XmageWs26Scenario.NATIVE_STATE_LOAD;\n        // Real pregame must execute XMage's native CR 103 lifecycle. In XMage\n        // testMode intentionally suppresses initial hand draw/mulligan setup.\n        options.testMode = !XmageWs26Scenario.NATURAL_GAME_START.equals(executionEntryMode);\n        options.skipInitShuffling = !XmageWs26Scenario.NATURAL_GAME_START.equals(executionEntryMode);\n""",
    )

    gate = Path("candidate-qualification/ws26-xmage/run_ws26_gate.py")
    replace_exact(
        gate,
        """    expected_seat = int(scenario[\"starting_player_seat\"])\n    if expected_seat not in {1, 2, 3, 4}:\n        raise RuntimeError(f\"invalid scenario starting_player_seat: {expected_seat}\")\n\n    options = decision.get(\"legal_options\") or []\n    if len(options) != 4:\n""",
        """    expected_seat = int(scenario[\"starting_player_seat\"])\n    player_count = len(scenario.get(\"players\") or [])\n    if player_count < 2 or player_count > 5:\n        raise RuntimeError(f\"invalid scenario player count: {player_count}\")\n    if expected_seat < 1 or expected_seat > player_count:\n        raise RuntimeError(f\"invalid scenario starting_player_seat: {expected_seat}\")\n\n    options = decision.get(\"legal_options\") or []\n    if len(options) != player_count:\n""",
    )
    replace_exact(
        gate,
        """    by_id = {str(option.get(\"option_id\")): option for option in options}\n    if set(by_id) != {\"P1\", \"P2\", \"P3\", \"P4\"} or len(by_id) != 4:\n""",
        """    by_id = {str(option.get(\"option_id\")): option for option in options}\n    expected_ids = {f\"P{seat}\" for seat in range(1, player_count + 1)}\n    if set(by_id) != expected_ids or len(by_id) != player_count:\n""",
    )
    replace_exact(gate, "    for seat in range(1, 5):\n", "    for seat in range(1, player_count + 1):\n")
    replace_exact(gate, "    if len(object_ids) != 4:\n", "    if len(object_ids) != player_count:\n")
    print("XMAGE_NATURAL_START_OVERLAY=PASS")


if __name__ == "__main__":
    main()

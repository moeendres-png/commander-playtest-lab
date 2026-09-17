#!/usr/bin/env python3
"""Fail-closed post-overlay compile guard for the WS-49 hidden-library repair.

The WS49 native remediation is intentionally expressed as a source transform
against the inherited qualification bridge.  XmageWs26Scenario exposes
``array``/``optionalArray`` helpers but no ``optionalObject`` helper.  Replace
only that single WS49-introduced call with an equivalent direct JsonObject
shape check.  Any source drift fails closed.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"


def main() -> int:
    text = SCENARIO.read_text(encoding="utf-8")
    old = '''            JsonObject knowledge = optionalObject(scenario, "ws42_knowledge_state");
            if (knowledge != null) {
'''
    new = '''            JsonObject knowledge = scenario.has("ws42_knowledge_state")
                    && scenario.get("ws42_knowledge_state").isJsonObject()
                    ? scenario.getAsJsonObject("ws42_knowledge_state")
                    : null;
            if (knowledge != null) {
'''
    if new in text:
        print("WS49_COMPILE_GUARD=ALREADY_APPLIED")
        return 0
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS49_COMPILE_GUARD_ANCHOR_MISMATCH:count={count}")
    SCENARIO.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("WS49_COMPILE_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

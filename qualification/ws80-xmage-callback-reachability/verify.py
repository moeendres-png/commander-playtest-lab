"""WS80 deterministic verifier (stdlib only).

Checks the machine-readable WS80 outputs plus the production diff for the
hard gates. No randomness, no network, no secrets. Exit 0 on PASS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BRIDGE = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageBridgePlayer.java"
CONFIG = ROOT / "config/rules_engines.json"

FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)


def load(name: str) -> dict:
    path = OUT / name
    if not path.is_file():
        fail(f"missing required output: {name}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{name} is not valid JSON: {exc}")
        return {}


def main() -> int:
    for name in (
        "ENTRYPOINT_REACHABILITY.json",
        "CALLBACK_INVENTORY.json",
        "CAPABILITY_MAPPING.json",
        "RISK_MATRIX.json",
        "VALIDATION.json",
    ):
        load(name)
    validation = load("VALIDATION.json")
    gates = validation.get("gates", {}) if isinstance(validation, dict) else {}
    expected = {
        "ENTRYPOINT_INVENTORY_COMPLETE": "PASS",
        "CALLBACK_INVENTORY_COMPLETE": "PASS",
        "CAPABILITY_REACHABILITY_CONSISTENT": "PASS",
        "PRODUCTION_REACHABLE_DEFAULT_DECISIONS": 0,
        "FULL_GAME_EXTERNAL_DECISION_BOUNDARY": "PASS",
        "RULES_RANDOMNESS_ENGINE_OWNED": "PASS",
        "UNSUPPORTED_PATHS_FAIL_CLOSED": "PASS",
        "COMPATIBILITY_CAPABILITY_INFLATION": 0,
        "PILOT_RULES_LOGIC": 0,
        "ENGINE_PIN_CHANGE": 0,
    }
    for key, want in expected.items():
        got = gates.get(key, "<missing>")
        if got != want:
            fail(f"gate {key}: expected {want!r}, observed {got!r}")
    if validation.get("engine_pin_change", "<missing>") != 0:
        fail("engine_pin_change must be 0")
    if validation.get("behavior_credit_change", "<missing>") != 0:
        fail("behavior_credit_change must be 0")
    if validation.get("architecture_freeze") != "NOT_CLAIMED":
        fail("ARCHITECTURE_FREEZE must be NOT_CLAIMED")
    if validation.get("production_provider") != "NOT_SELECTED":
        fail("PRODUCTION_PROVIDER must be NOT_SELECTED")

    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read config/rules_engines.json: {exc}")
        config = {}
    if config.get("primary_engine", {}).get("commit") != "77d7646da6958fdf8125ee7c8f4aabd130d21d4c":
        fail("primary_engine pin changed")
    if config.get("protocol_version") != "2.0.0":
        fail("protocol_version changed")
    missing = config.get("primary_engine", {}).get("missing_required_capabilities", [])
    if "legal_actions_supported" not in missing or "action_submission_supported" not in missing:
        fail("config must still list legal_actions/action_submission as missing")

    try:
        bridge = BRIDGE.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read XmageBridgePlayer.java: {exc}")
        bridge = ""
    for needle in (
        "failIfExternallyControlled",
        "UNSUPPORTED_COMPATIBILITY_DECISION",
        "isStartingPlayerInitChoice",
        "Select a starting player",
        "chooseAbilityForCast",
        "chooseLandOrSpellAbility",
    ):
        if needle not in bridge:
            fail(f"XmageBridgePlayer.java missing required marker: {needle}")
    for forbidden in ("Math.min(message", "new Random(", "TestPlayer", "ComputerPlayer"):
        if forbidden in bridge:
            fail(f"XmageBridgePlayer.java contains forbidden marker: {forbidden}")

    if FAILURES:
        print("WS80_VERIFY=FAIL")
        for item in FAILURES:
            print(f"- {item}")
        return 1
    print("WS80_VERIFY=PASS")
    print("gates: PRODUCTION_REACHABLE_DEFAULT_DECISIONS=0 UNSUPPORTED_PATHS_FAIL_CLOSED=PASS CAPABILITY_TRUTH=PASS ENGINE_PIN_CHANGE=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

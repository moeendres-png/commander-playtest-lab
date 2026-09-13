"""WS88 integration verifier (stdlib only).

Successor/supersession mechanism for the sealed WS80 package: re-establishes
the WS80 fail-closed properties on the Coordinator-accepted XMage successor
cfc36f445f917f101fa2ed588770e043f53bc44c with fresh runtime evidence, without
touching the historical WS80 frame. No randomness, no network, no secrets.
Exit 0 on PASS.

Supersedes: qualification/ws80-xmage-callback-reachability (bound to
77d7646da6958fdf8125ee7c8f4aabd130d21d4c, retained as provenance).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CONFIG = ROOT / "config/rules_engines.json"
BRIDGE_PLAYER = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageBridgePlayer.java"
BRIDGE_PROVIDER = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java"
PHASE6_ADAPTER = (
    ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/Phase6DifferentialAdapter.java"
)

OLD_PIN = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
NEW_PIN = "cfc36f445f917f101fa2ed588770e043f53bc44c"

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


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def main() -> int:
    for name in ("ENGINE_VALIDATION.json", "RUNTIME_VALIDATION.json", "VALIDATION.json"):
        load(name)
    validation = load("VALIDATION.json")
    gates = validation.get("gates", {}) if isinstance(validation, dict) else {}
    expected: dict[str, object] = {
        "SOURCE_LOCK": "PASS",
        "XMAGE_SUCCESSOR_LOCK": "PASS",
        "OLD_RUNTIME_IS_ANCESTOR": "PASS",
        "PIN_CONSUMER_INVENTORY": "PASS",
        "HISTORICAL_EVIDENCE_REWRITTEN": "NO",
        "PRODUCTION_PIN_CONSUMERS_COHERENT": "PASS",
        "DOCKER_PIN_AUTHORITY_GATE": "PASS",
        "ENGINE_MATERIALIZATION": "PASS",
        "XMAGE_RNG_SUCCESSOR_TESTS": "PASS",
        "XMAGE_H01_A": "PASS",
        "XMAGE_H01_B": "PASS",
        "XMAGE_H01_C": "PASS",
        "WS85_PURITY_REGRESSION": "PASS",
        "WS80_FAIL_CLOSED_ON_NEW_PIN": "PASS",
        "PRODUCTION_REACHABLE_DEFAULT_DECISIONS": 0,
        "FULL_GAME_FAIL_CLOSED": "PASS",
        "RULES_RANDOMNESS_ENGINE_OWNED": "PASS",
        "CAPABILITY_INFLATION": 0,
        "PILOT_RULES_LOGIC": 0,
        "EXTERNAL_XMAGE_INTEGRATION": "PASS",
        "XMAGE_FULL_GAME_CONFORMANCE": "PASS",
        "LIFECYCLE_REGRESSION": "PASS",
        "QUALIFICATION_SUITE": "PASS",
        "RUFF": "PASS",
        "BEHAVIOR_CREDIT_CHANGE": 0,
    }
    for key, want in expected.items():
        got = gates.get(key, "<missing>")
        if got != want:
            fail(f"gate {key}: expected {want!r}, observed {got!r}")
    if gates.get("ENGINE_PIN_CHANGE") != "AUTHORIZED_REPIN":
        fail("ENGINE_PIN_CHANGE must be AUTHORIZED_REPIN")
    if validation.get("first_wave_current_ranking", "<missing>") != (
        "INVALID_PENDING_RQC3_REQUALIFICATION"
    ):
        fail("FIRST_WAVE_CURRENT_RANKING must stay INVALID_PENDING_RQC3_REQUALIFICATION")
    if validation.get("full107_behavior", "<missing>") != "NOT_RUN":
        fail("FULL107_BEHAVIOR must be NOT_RUN")
    if validation.get("behavior_credit_change", "<missing>") != 0:
        fail("behavior_credit_change must be 0")
    if validation.get("architecture_freeze") != "NOT_CLAIMED":
        fail("ARCHITECTURE_FREEZE must be NOT_CLAIMED")
    if validation.get("production_provider") != "NOT_SELECTED":
        fail("PRODUCTION_PROVIDER must be NOT_SELECTED")
    subject = validation.get("pin_subject", {})
    if subject.get("commit") != NEW_PIN:
        fail("pin_subject.commit must be the successor pin")
    if "ws80-xmage-callback-reachability" not in str(subject.get("supersedes", "")):
        fail("pin_subject must name the superseded WS80 package")

    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read config/rules_engines.json: {exc}")
        config = {}
    if config.get("primary_engine", {}).get("commit") != NEW_PIN:
        fail("primary_engine pin is not the successor")
    archive = config.get("primary_engine", {}).get("source_archive", "")
    if NEW_PIN not in archive or OLD_PIN in archive:
        fail("primary_engine source_archive is not coherent with the successor pin")
    if config.get("protocol_version") != "2.0.0":
        fail("protocol_version changed")
    missing = config.get("primary_engine", {}).get("missing_required_capabilities", [])
    if "legal_actions_supported" not in missing or "action_submission_supported" not in missing:
        fail("config must still list legal_actions/action_submission as missing")

    provider_src = read_text(BRIDGE_PROVIDER)
    if NEW_PIN not in provider_src or OLD_PIN in provider_src:
        fail("XmageProvider.java must report exactly the successor pin")
    phase6_src = read_text(PHASE6_ADAPTER)
    if phase6_src.count(NEW_PIN) != 2 or OLD_PIN in phase6_src:
        fail("Phase6DifferentialAdapter.java must carry exactly the successor pin twice")

    player_src = read_text(BRIDGE_PLAYER)
    for needle in (
        "failIfExternallyControlled",
        "UNSUPPORTED_COMPATIBILITY_DECISION",
        "isStartingPlayerInitChoice",
        "Select a starting player",
        "chooseAbilityForCast",
        "chooseLandOrSpellAbility",
    ):
        if needle not in player_src:
            fail(f"XmageBridgePlayer.java missing required marker: {needle}")
    for forbidden in ("Math.min(message", "new Random(", "TestPlayer", "ComputerPlayer"):
        if forbidden in player_src:
            fail(f"XmageBridgePlayer.java contains forbidden marker: {forbidden}")

    historical_must_keep_old = [
        ROOT / "qualification/ws80-xmage-callback-reachability/verify.py",
        ROOT / "qualification/ws80-xmage-callback-reachability/VALIDATION.json",
        ROOT / "qualification/WS17_SOURCE_LOCK.json",
        ROOT / "docs/B4F_XMAGE_FIDELITY_CLOSEOUT.md",
    ]
    for path in historical_must_keep_old:
        text = read_text(path)
        if text and OLD_PIN not in text:
            fail(f"historical file lost its old pin (rewritten?): {path.relative_to(ROOT)}")
    historical_must_not_gain_new = [
        ROOT / "qualification/ws80-xmage-callback-reachability/verify.py",
        ROOT / "qualification/ws80-xmage-callback-reachability/VALIDATION.json",
        ROOT / "qualification/ws80-xmage-callback-reachability/SOURCE_LOCK.md",
        ROOT / "qualification/WS17_SOURCE_LOCK.json",
        ROOT / "qualification/evidence/candidates/xmage.json",
        ROOT / "docs/B4F_XMAGE_FIDELITY_CLOSEOUT.md",
        ROOT / "docs/xmage/BRIDGE_ARCHITECTURE_B0.md",
        ROOT / "docs/WS_A1D_PIN_CONSUMER_AUDIT.md",
        ROOT / "src/commander_lab/engine/rules/phase85.py",
    ]
    for path in historical_must_not_gain_new:
        text = read_text(path)
        if text and NEW_PIN in text:
            fail(f"historical file gained the new pin (rewritten?): {path.relative_to(ROOT)}")

    if FAILURES:
        print("WS88_VERIFY=FAIL")
        for item in FAILURES:
            print(f"- {item}")
        return 1
    print("WS88_VERIFY=PASS")
    print(
        "gates: WS80_FAIL_CLOSED_ON_NEW_PIN=PASS "
        "PRODUCTION_REACHABLE_DEFAULT_DECISIONS=0 ENGINE_PIN_CHANGE=AUTHORIZED_REPIN "
        "HISTORICAL_EVIDENCE_REWRITTEN=NO"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

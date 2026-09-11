#!/usr/bin/env python3
"""Qualification-only WS-34 provider overlay; never edits the pinned XMage engine.

The overlay extends the existing WS-26 qualification bridge only.  It does not
modify XMage rules/card code.  WS-34 needs two successor-specific properties:

* Commander free-mulligan semantics differ for 2P vs multiplayer Commander.
* the provider must emit the complete provider-neutral requested-state
  projection after native setup validation, so the harness can compare the
  provider-emitted normalized construction digest with the frozen WS-32 digest.

The second surface is deliberately gated by the existing native scenario
validator.  It is unavailable before an Applied scenario exists and therefore
cannot turn a rejected or deferred setup into successor runtime credit.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26QualificationSession.java"
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"

MULLIGAN_OLD = "MulliganType.LONDON.getMulligan(1),"
MULLIGAN_NEW = "MulliganType.LONDON.getMulligan(playerCount >= 3 ? 1 : 0),"

TOP_OLD = '            "execution_entry_mode", "temporal_state"\n    );'
TOP_NEW = '            "execution_entry_mode", "temporal_state",\n            "successor_requested_state", "successor_requested_state_digest"\n    );'

STATE_OLD = '''    JsonObject qualificationStatePayload() {\n        ensureStarted();\n        JsonObject payload = new JsonObject();\n        payload.add("semantic_state", replayRecorder.currentState());\n        payload.add("rules_rng_tape", XmageWs26RulesRngTape.snapshot(seed));\n        return payload;\n    }'''

STATE_NEW = '''    JsonObject qualificationStatePayload() {\n        ensureStarted();\n        JsonObject payload = new JsonObject();\n        payload.add("semantic_state", replayRecorder.currentState());\n        payload.add("rules_rng_tape", XmageWs26RulesRngTape.snapshot(seed));\n        addSuccessorConstructionProof(payload);\n        return payload;\n    }\n\n    private void addSuccessorConstructionProof(JsonObject payload) {\n        if (configuredScenario == null || !configuredScenario.has("successor_requested_state")\n                || !configuredScenario.has("successor_requested_state_digest")) {\n            return;\n        }\n        if (appliedScenario == null || appliedScenario.validation() == null\n                || !appliedScenario.validation().has("valid")\n                || !appliedScenario.validation().get("valid").getAsBoolean()) {\n            throw new IllegalStateException("SUCCESSOR_NATIVE_SETUP_NOT_VALIDATED");\n        }\n        if (!configuredScenario.get("successor_requested_state").isJsonObject()) {\n            throw new IllegalStateException("SUCCESSOR_REQUESTED_STATE_MUST_BE_OBJECT");\n        }\n        String declaredDigest = configuredScenario.get("successor_requested_state_digest").getAsString();\n        if (declaredDigest == null || !declaredDigest.matches("[0-9a-f]{64}")) {\n            throw new IllegalStateException("SUCCESSOR_REQUESTED_STATE_DIGEST_INVALID");\n        }\n        payload.add("normalized_constructed_state",\n                configuredScenario.getAsJsonObject("successor_requested_state").deepCopy());\n        payload.addProperty("normalized_constructed_state_declared_digest", declaredDigest);\n        payload.addProperty("normalized_constructed_state_proof", "PROVIDER_NATIVE_SETUP_VALIDATION_BOUND");\n        payload.add("normalized_constructed_state_native_validation",\n                appliedScenario.validation().deepCopy());\n    }'''


def replace_once(path: Path, old: str, new: str, code: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if text.count(old) != 1:
        raise SystemExit(code)
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    replace_once(SESSION, MULLIGAN_OLD, MULLIGAN_NEW, "WS34_MULLIGAN_OVERLAY_ANCHOR_MISMATCH")
    replace_once(SCENARIO, TOP_OLD, TOP_NEW, "WS34_SUCCESSOR_TOP_OVERLAY_ANCHOR_MISMATCH")
    replace_once(SESSION, STATE_OLD, STATE_NEW, "WS34_SUCCESSOR_STATE_PROOF_ANCHOR_MISMATCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

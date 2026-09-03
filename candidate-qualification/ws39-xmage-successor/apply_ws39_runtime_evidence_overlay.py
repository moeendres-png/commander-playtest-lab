#!/usr/bin/env python3
"""WS-39 qualification-only runtime-evidence overlays.

Run after apply_ws39_provider_overlay.py. The XMage source transform instruments
native RandomUtil for attributable/replayable Rules-RNG evidence; it does not
supply randomness from Commander Lab. The bridge correction keeps ordinary
actor-visible Knowledge-Ledger identity unchanged while adding the frozen
scenario semantic id as qualification-only evidence metadata.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"
PLAYER = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java"
RNG_OVERLAY = ROOT / "candidate-qualification/ws39-xmage-successor/apply_ws39_rng_instrumentation.py"
XMAGE_ROOT = ROOT / "vendor/engine-source/xmage"
RNG_REPORT = ROOT / "artifacts/ws39-ci/WS39_XMAGE_RNG_SOURCE_TRANSFORM.json"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS39_RUNTIME_EVIDENCE_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def apply_rng_instrumentation() -> None:
    subprocess.run(
        [
            sys.executable,
            str(RNG_OVERLAY),
            "--xmage-root",
            str(XMAGE_ROOT),
            "--output",
            str(RNG_REPORT),
        ],
        check=True,
    )


def apply_semantic_source_evidence() -> None:
    scenario_text = SCENARIO.read_text(encoding="utf-8")
    scenario_text = replace_once(
        scenario_text,
        "    private XmageWs26Scenario() {}\n",
        "    private static final Map<Game, Map<UUID, String>> WS39_SEMANTIC_IDS_BY_GAME =\n"
        "            java.util.Collections.synchronizedMap(new java.util.WeakHashMap<>());\n\n"
        "    private XmageWs26Scenario() {}\n\n"
        "    static String ws39SemanticObjectId(Game game, UUID nativeId) {\n"
        "        if (game == null || nativeId == null) return null;\n"
        "        Map<UUID, String> semanticIds = WS39_SEMANTIC_IDS_BY_GAME.get(game);\n"
        "        if (semanticIds == null) return null;\n"
        "        String direct = semanticIds.get(nativeId);\n"
        "        if (direct != null) return direct;\n"
        "        Card card = game.getCard(nativeId);\n"
        "        if (card != null) {\n"
        "            String cardId = semanticIds.get(card.getId());\n"
        "            if (cardId != null) return cardId;\n"
        "            String mainId = semanticIds.get(card.getMainCard().getId());\n"
        "            if (mainId != null) return mainId;\n"
        "        }\n"
        "        Permanent permanent = game.getPermanent(nativeId);\n"
        "        if (permanent != null) {\n"
        "            String permanentId = semanticIds.get(permanent.getId());\n"
        "            if (permanentId != null) return permanentId;\n"
        "            return semanticIds.get(permanent.getMainCard().getId());\n"
        "        }\n"
        "        return null;\n"
        "    }\n",
        "scenario-semantic-registry",
    )
    scenario_text = replace_once(
        scenario_text,
        "        validation.add(\"commander_history\", commanderHistoryValidation);\n"
        "        return new Applied(\n",
        "        validation.add(\"commander_history\", commanderHistoryValidation);\n"
        "        WS39_SEMANTIC_IDS_BY_GAME.put(game, Map.copyOf(semanticMap));\n"
        "        return new Applied(\n",
        "scenario-semantic-registration",
    )
    SCENARIO.write_text(scenario_text, encoding="utf-8")

    player_text = PLAYER.read_text(encoding="utf-8")
    player_text = replace_once(
        player_text,
        "            String semanticSource = XmageDecisionOptionIdentity.visibleNativeToSemantic(\n"
        "                    game, XmageFullGameStateRedactor.actorView(game, this)\n"
        "            ).get(ability.getSourceId());\n"
        "            if (semanticSource != null) {\n"
        "                metadata.addProperty(\"semantic_source_object_id\", semanticSource);\n"
        "            }\n",
        "            String visibleSource = XmageDecisionOptionIdentity.visibleNativeToSemantic(\n"
        "                    game, XmageFullGameStateRedactor.actorView(game, this)\n"
        "            ).get(ability.getSourceId().toString());\n"
        "            if (visibleSource != null) {\n"
        "                metadata.addProperty(\"visible_source_object_id\", visibleSource);\n"
        "            }\n"
        "            String semanticSource = XmageWs26Scenario.ws39SemanticObjectId(\n"
        "                    game, ability.getSourceId()\n"
        "            );\n"
        "            if (semanticSource != null) {\n"
        "                metadata.addProperty(\"semantic_source_object_id\", semanticSource);\n"
        "            }\n",
        "ability-source-evidence",
    )
    PLAYER.write_text(player_text, encoding="utf-8")


def main() -> int:
    apply_rng_instrumentation()
    apply_semantic_source_evidence()
    print("WS39_RUNTIME_EVIDENCE_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

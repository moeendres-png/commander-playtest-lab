#!/usr/bin/env python3
"""WS-39 qualification-only semantic identity normalization for stack targets.

The frozen WS-32 v1.0.2 corpus contains three stack target references whose
lexical semantic token differs from the current semantic-object token while the
identity remains uniquely recoverable from the frozen state:

* case-only differences (for example obj:P2-bears vs obj:p2-bears), and
* an incarnation alias retained as card_lineage_id (obj:P1-commander ->
  line:obj:P1-commander on the current battlefield incarnation).

This overlay does not decide target legality. It only resolves a frozen target
reference to one native object by exact id, then a unique case-insensitive id,
then a unique frozen lineage alias. Any missing or ambiguous mapping fails
closed. XMage's native Target.canTarget remains authoritative.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"


def replace_exact(text: str, old: str, new: str, expected: int, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"WS39_STACK_IDENTITY_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new)


def main() -> int:
    text = SCENARIO.read_text(encoding="utf-8")

    text = replace_exact(
        text,
        "stackTargetNativeId(targetSemantic, players, semanticMap)",
        "stackTargetNativeId(targetSemantic, scenario, players, semanticMap)",
        2,
        "stack-target-call-sites",
    )

    old = '''    private static UUID stackTargetNativeId(\n            String semantic,\n            List<? extends Player> players,\n            Map<UUID, String> semanticMap\n    ) {\n        if (semantic.matches("P[1-9][0-9]*")) {\n            int seat = playerSeatValue(semantic, players.size());\n            return players.get(seat - 1).getId();\n        }\n        return nativeId(semanticMap, semantic);\n    }\n'''
    new = '''    private static UUID stackTargetNativeId(\n            String semantic,\n            JsonObject scenario,\n            List<? extends Player> players,\n            Map<UUID, String> semanticMap\n    ) {\n        if (semantic.matches("P[1-9][0-9]*")) {\n            int seat = playerSeatValue(semantic, players.size());\n            return players.get(seat - 1).getId();\n        }\n\n        UUID exact = uniqueSemanticNativeId(semanticMap, semantic, false);\n        if (exact != null) return exact;\n\n        UUID caseInsensitive = uniqueSemanticNativeId(semanticMap, semantic, true);\n        if (caseInsensitive != null) return caseInsensitive;\n\n        JsonObject requested = object(scenario, "successor_requested_state");\n        String lineageAlias = "line:" + semantic;\n        String mappedSemantic = null;\n        for (JsonElement element : optionalArray(requested, "semantic_objects")) {\n            if (!element.isJsonObject()) {\n                throw fail("NATIVE_VALIDATION_FAILED: requested semantic object is not object");\n            }\n            JsonObject object = element.getAsJsonObject();\n            if (!object.has("card_lineage_id") || object.get("card_lineage_id").isJsonNull()) continue;\n            if (!lineageAlias.equals(object.get("card_lineage_id").getAsString())) continue;\n            String candidate = text(object, "semantic_id");\n            if (mappedSemantic != null && !mappedSemantic.equals(candidate)) {\n                throw fail("NATIVE_VALIDATION_FAILED: ambiguous stack lineage alias " + semantic);\n            }\n            mappedSemantic = candidate;\n        }\n        if (mappedSemantic == null) {\n            throw fail("NATIVE_VALIDATION_FAILED: stale semantic id " + semantic);\n        }\n        UUID lineageNative = uniqueSemanticNativeId(semanticMap, mappedSemantic, false);\n        if (lineageNative == null) {\n            throw fail("NATIVE_VALIDATION_FAILED: stale lineage target " + semantic + " -> " + mappedSemantic);\n        }\n        return lineageNative;\n    }\n\n    private static UUID uniqueSemanticNativeId(\n            Map<UUID, String> semanticMap,\n            String semantic,\n            boolean ignoreCase\n    ) {\n        UUID match = null;\n        for (Map.Entry<UUID, String> entry : semanticMap.entrySet()) {\n            boolean equals = ignoreCase\n                    ? semantic.equalsIgnoreCase(entry.getValue())\n                    : semantic.equals(entry.getValue());\n            if (!equals) continue;\n            if (match != null && !match.equals(entry.getKey())) {\n                throw fail("NATIVE_VALIDATION_FAILED: ambiguous semantic alias " + semantic);\n            }\n            match = entry.getKey();\n        }\n        return match;\n    }\n'''
    text = replace_exact(text, old, new, 1, "stack-target-resolver")

    SCENARIO.write_text(text, encoding="utf-8")
    print("WS39_STACK_IDENTITY_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

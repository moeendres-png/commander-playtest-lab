#!/usr/bin/env python3
"""Remove identity-derived hidden-card references from the WS42 XMage provider.

The legacy ledger used a hash of deck composition + zone + card name +
occurrence as a privileged physical reference.  A known-deck adversary can
precompute that value.  WS42 replaces it with an identity-independent random
opaque physical handle.  This randomness is observation-only, never Rules RNG.

The replay recorder separately canonicalizes these opaque handles to stable
encounter-order aliases before semantic checkpoint hashing, so clean-process
replay does not depend on the non-Rules opaque-handle generator.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageKnowledgeLedger.java"
REPLAY = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26ReplayRecorder.java"
ACTOR_TEST = ROOT / "engine-bridge/src/test/java/org/commanderlab/xmage/XmageActorIdentityProjectionAdversarialTest.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS42_HIDDEN_IDENTITY_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def patch_ledger() -> None:
    text = LEDGER.read_text(encoding="utf-8")
    old = '''        String fingerprint = deckFingerprint(deck);\n        Map<String, Integer> mainOccurrences = new HashMap<>();\n        for (Card card : deck.getCards()) {\n            int occurrence = mainOccurrences.merge(card.getName(), 1, Integer::sum);\n            physicalCardRefs.put(\n                    card.getMainCard().getId(),\n                    stablePhysicalRef(zeroBasedSeat, fingerprint, "main", card.getName(), occurrence)\n            );\n        }\n        Map<String, Integer> commandOccurrences = new HashMap<>();\n        for (Card card : deck.getSideboard()) {\n            int occurrence = commandOccurrences.merge(card.getName(), 1, Integer::sum);\n            physicalCardRefs.put(\n                    card.getMainCard().getId(),\n                    stablePhysicalRef(zeroBasedSeat, fingerprint, "command", card.getName(), occurrence)\n            );\n        }\n'''
    new = '''        for (Card card : deck.getCards()) {\n            physicalCardRefs.put(card.getMainCard().getId(), opaquePhysicalRef());\n        }\n        for (Card card : deck.getSideboard()) {\n            physicalCardRefs.put(card.getMainCard().getId(), opaquePhysicalRef());\n        }\n'''
    text = replace_once(text, old, new, "ledger-registration")

    old_helpers = '''    private static String stablePhysicalRef(int zeroBasedSeat, String deckFingerprint, String deckZone, String name, int occurrence) {\n        return "card-P" + (zeroBasedSeat + 1) + "-"\n                + sha256(deckFingerprint + "\\u0000" + deckZone + "\\u0000" + name + "\\u0000" + occurrence).substring(0, 20);\n    }\n\n    private static String deckFingerprint(Deck deck) {\n        List<String> main = deck.getCards().stream().map(Card::getName).sorted().toList();\n        List<String> command = deck.getSideboard().stream().map(Card::getName).sorted().toList();\n        return sha256("main=" + String.join("\\u0000", main) + "\\u0001command=" + String.join("\\u0000", command));\n    }\n\n    private static String sha256(String value) {\n        try {\n            MessageDigest digest = MessageDigest.getInstance("SHA-256");\n            byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));\n            StringBuilder result = new StringBuilder(bytes.length * 2);\n            for (byte b : bytes) {\n                result.append(String.format("%02x", b));\n            }\n            return result.toString();\n        } catch (NoSuchAlgorithmException exc) {\n            throw new IllegalStateException("SHA-256 unavailable", exc);\n        }\n    }\n'''
    new_helpers = '''    private static String opaquePhysicalRef() {\n        // Deliberately independent of deck fingerprint, card name, seat, zone,\n        // occurrence, native card UUID and Rules RNG.  Replay canonicalization\n        // removes this observation-only nonce before semantic evidence hashing.\n        return "card-opaque-" + UUID.randomUUID();\n    }\n'''
    text = replace_once(text, old_helpers, new_helpers, "ledger-identity-helpers")
    if "stablePhysicalRef(" in text or "deckFingerprint(" in text:
        raise SystemExit("WS42_HIDDEN_IDENTITY_DERIVATION_STILL_REACHABLE")
    LEDGER.write_text(text, encoding="utf-8")


def patch_replay() -> None:
    text = REPLAY.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import java.util.List;\nimport java.util.Map;\n",
        "import java.util.LinkedHashMap;\nimport java.util.List;\nimport java.util.Map;\n",
        "replay-import",
    )
    text = replace_once(
        text,
        "    private final Map<UUID, String> scenarioObjectIds;\n",
        "    private final Map<UUID, String> scenarioObjectIds;\n"
        "    private final Map<String, String> replayObjectRefs = new LinkedHashMap<>();\n"
        "    private int replayObjectSequence;\n",
        "replay-fields",
    )
    text = replace_once(
        text,
        "            JsonObject view = ledger.snapshot(game, player, player);\n",
        "            JsonObject view = replaySafeActorView(player);\n",
        "checkpoint-actor-view",
    )
    text = replace_once(
        text,
        "        for (Player player : players) {\n            actorViews.add(ledger.snapshot(game, player, player));\n        }\n",
        "        for (Player player : players) {\n            actorViews.add(replaySafeActorView(player));\n        }\n",
        "current-state-actor-view",
    )

    helper_anchor = "    private JsonObject decisionRecord(\n"
    helper = '''    private JsonObject replaySafeActorView(Player player) {\n        JsonObject view = ledger.snapshot(game, player, player);\n        registerReplayObjectIds(view);\n        replaceReplayObjectIds(view);\n        return view;\n    }\n\n    private void registerReplayObjectIds(JsonElement element) {\n        if (element == null || element.isJsonNull() || element.isJsonPrimitive()) {\n            return;\n        }\n        if (element.isJsonArray()) {\n            for (JsonElement child : element.getAsJsonArray()) {\n                registerReplayObjectIds(child);\n            }\n            return;\n        }\n        JsonObject object = element.getAsJsonObject();\n        JsonElement objectId = object.get("object_id");\n        if (objectId != null && objectId.isJsonPrimitive()\n                && objectId.getAsJsonPrimitive().isString()) {\n            replayObjectRefs.computeIfAbsent(objectId.getAsString(), ignored -> {\n                replayObjectSequence++;\n                return "replay-obj-" + String.format("%06d", replayObjectSequence);\n            });\n        }\n        for (Map.Entry<String, JsonElement> entry : object.entrySet()) {\n            registerReplayObjectIds(entry.getValue());\n        }\n    }\n\n    private void replaceReplayObjectIds(JsonElement element) {\n        if (element == null || element.isJsonNull()) {\n            return;\n        }\n        if (element.isJsonArray()) {\n            JsonArray array = element.getAsJsonArray();\n            for (int index = 0; index < array.size(); index++) {\n                JsonElement child = array.get(index);\n                if (child.isJsonPrimitive() && child.getAsJsonPrimitive().isString()) {\n                    String replacement = replayObjectRefs.get(child.getAsString());\n                    if (replacement != null) {\n                        array.set(index, new com.google.gson.JsonPrimitive(replacement));\n                    }\n                } else {\n                    replaceReplayObjectIds(child);\n                }\n            }\n            return;\n        }\n        if (element.isJsonPrimitive()) {\n            return;\n        }\n        JsonObject object = element.getAsJsonObject();\n        for (String key : new ArrayList<>(object.keySet())) {\n            JsonElement child = object.get(key);\n            if (child != null && child.isJsonPrimitive()\n                    && child.getAsJsonPrimitive().isString()) {\n                String replacement = replayObjectRefs.get(child.getAsString());\n                if (replacement != null) {\n                    object.addProperty(key, replacement);\n                }\n            } else {\n                replaceReplayObjectIds(child);\n            }\n        }\n    }\n\n    private JsonObject decisionRecord(\n'''
    text = replace_once(text, helper_anchor, helper, "replay-normalization-helper")
    REPLAY.write_text(text, encoding="utf-8")


def patch_adversarial_test() -> None:
    text = ACTOR_TEST.read_text(encoding="utf-8")
    old_first = '''        String privilegedRef = precomputedKnownDeckRef();\n        assertEquals(\n                privilegedRef,\n                privilegedRefForHoney(first),\n                "test must reproduce the actual deterministic privileged ledger reference"\n        );\n        JsonObject privilegedView = privilegedView(privilegedRef);\n'''
    new_first = '''        String legacyPredictableRef = precomputedKnownDeckRef();\n        String privilegedRef = privilegedRefForHoney(first);\n        assertNotEquals(\n                legacyPredictableRef,\n                privilegedRef,\n                "known deck + card identity must not predict the privileged physical reference"\n        );\n        assertTrue(privilegedRef.startsWith("card-opaque-"));\n        JsonObject privilegedView = privilegedView(privilegedRef);\n'''
    text = replace_once(text, old_first, new_first, "adversarial-first-session")
    old_second = '''        Fixture second = fixture("ws34-known-deck-b");\n        assertEquals(privilegedRef, privilegedRefForHoney(second));\n        String secondSessionHandle = projectedObjectId(second.game(), second.players().get(0), privilegedView);\n        assertNotEquals(firstActorHandle, secondSessionHandle, "independent games must not reuse a deterministic known-deck handle");\n'''
    new_second = '''        Fixture second = fixture("ws34-known-deck-b");\n        String secondPrivilegedRef = privilegedRefForHoney(second);\n        assertNotEquals(\n                privilegedRef,\n                secondPrivilegedRef,\n                "independent games must not reuse a predictable privileged physical reference"\n        );\n        JsonObject secondPrivilegedView = privilegedView(secondPrivilegedRef);\n        String secondSessionHandle = projectedObjectId(second.game(), second.players().get(0), secondPrivilegedView);\n        assertNotEquals(firstActorHandle, secondSessionHandle, "independent games must not reuse an actor-facing handle");\n'''
    text = replace_once(text, old_second, new_second, "adversarial-second-session")
    ACTOR_TEST.write_text(text, encoding="utf-8")


def main() -> int:
    patch_ledger()
    patch_replay()
    patch_adversarial_test()
    print("WS42_HIDDEN_IDENTITY_REMEDIATION_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

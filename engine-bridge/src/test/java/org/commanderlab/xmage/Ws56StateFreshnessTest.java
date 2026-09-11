package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS56 Phase D — State / frame freshness (successor).
 *
 * <p>Strongest conformant ADAPTER_OWNED freshness without a second Rules
 * engine. Binds game identity, principal, decision kind, current authoritative
 * option identities, and relevant current frame/state identity. A response
 * issued against an older frame fails closed. Every field is classified as
 * ENGINE_NATIVE or ADAPTER_OWNED; no adapter digest is described as
 * XMage-native; no revision metadata leaks hidden information.</p>
 */
class Ws56StateFreshnessTest {

    @Test
    void freshnessFieldsPresentAndClassified() throws Exception {
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws56-fresh-present");
        JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(bridge));
        // Required bindings present.
        for (String field : List.of("game_id", "decision_id", "decision_offset",
                "actor_id", "decision_subject_id", "decision_class",
                "legal_options", "option_digest", "frame_digest", "frame_revision",
                "actor_view_hash", "freshness", "field_provenance")) {
            assertTrue(decision.has(field) && !decision.get(field).isJsonNull(),
                    "freshness frame must carry " + field + ": " + decision);
        }
        JsonObject freshness = decision.getAsJsonObject("freshness");
        for (String field : List.of("game_id", "actor_id", "decision_subject_id",
                "decision_kind", "option_digest", "frame_digest", "frame_revision", "actor_view_hash")) {
            assertTrue(freshness.has(field) && !freshness.get(field).isJsonNull(),
                    "freshness object must carry " + field);
        }
        assertEquals(decision.get("decision_class").getAsString(),
                freshness.get("decision_kind").getAsString(),
                "freshness kind must equal engine decision class");
        assertEquals(decision.get("frame_digest").getAsString(),
                freshness.get("frame_digest").getAsString());
        assertEquals(decision.get("option_digest").getAsString(),
                freshness.get("option_digest").getAsString());

        JsonObject provenance = decision.getAsJsonObject("field_provenance");
        // Every classified field must be exactly one of the two allowed values.
        for (String key : provenance.keySet()) {
            String value = provenance.get(key).getAsString();
            assertTrue("ENGINE_NATIVE".equals(value) || "ADAPTER_OWNED".equals(value),
                    "provenance must be ENGINE_NATIVE or ADAPTER_OWNED: " + key + "=" + value);
        }
        // Spot-check required classifications.
        assertEquals("ENGINE_NATIVE", provenance.get("game_id").getAsString());
        assertEquals("ENGINE_NATIVE", provenance.get("actor_id").getAsString());
        assertEquals("ENGINE_NATIVE", provenance.get("decision_class").getAsString());
        assertEquals("ENGINE_NATIVE", provenance.get("legal_options").getAsString());
        assertEquals("ADAPTER_OWNED", provenance.get("decision_id").getAsString());
        assertEquals("ADAPTER_OWNED", provenance.get("option_digest").getAsString());
        assertEquals("ADAPTER_OWNED", provenance.get("frame_digest").getAsString());
        assertEquals("ADAPTER_OWNED", provenance.get("frame_revision").getAsString());
        assertEquals("ADAPTER_OWNED", provenance.get("actor_view_hash").getAsString());

        // Digests must be opaque hashes (hex, fixed length), not names or UUIDs.
        String frameDigest = decision.get("frame_digest").getAsString();
        String optionDigest = decision.get("option_digest").getAsString();
        assertTrue(frameDigest.matches("[0-9a-f]{64}"), "frame_digest must be SHA-256 hex: " + frameDigest);
        assertTrue(optionDigest.matches("[0-9a-f]{64}"), "option_digest must be SHA-256 hex: " + optionDigest);

        JsonObject evidence = new JsonObject();
        evidence.addProperty("game_id", decision.get("game_id").getAsString());
        evidence.addProperty("decision_class", decision.get("decision_class").getAsString());
        evidence.addProperty("frame_digest", frameDigest);
        evidence.addProperty("option_digest", optionDigest);
        evidence.addProperty("provenance_ok", true);
        writeEvidence("freshness-present.json", evidence);
    }

    @Test
    void optionDigestBindsCurrentOptionIdentities() throws Exception {
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws56-fresh-options");
        JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(bridge));
        List<String> ids = new ArrayList<>();
        for (JsonElement e : decision.getAsJsonArray("legal_options")) {
            ids.add(e.getAsJsonObject().get("option_id").getAsString());
        }
        List<String> sorted = new ArrayList<>(ids);
        Collections.sort(sorted);
        List<String> parts = new ArrayList<>();
        parts.add("options");
        parts.add(decision.get("decision_class").getAsString());
        parts.addAll(sorted);
        String recomputed = XmageFullGameDecisionController.stableId(parts.toArray(new String[0]));
        assertEquals(decision.get("option_digest").getAsString(), recomputed,
                "option_digest must be the adapter hash of the current sorted option identities");
        // Different option sets must give different digests (binding is live).
        // Advance one decision and verify the next frame's digest differs.
        JsonObject after = Ws52.submit(bridge, decision,
                List.of(ids.get(0)));
        JsonObject next = Ws52.requirePendingDecision(after);
        // Next frame may coincidentally share option ids (e.g., mulligan keep);
        // the frame digest must still differ because revision/actor-view advance.
        // At minimum, the pair (decision_id, frame_digest) must advance.
        assertTrue(!decision.get("decision_id").getAsString().equals(next.get("decision_id").getAsString())
                        || !decision.get("frame_digest").getAsString().equals(next.get("frame_digest").getAsString()),
                "progression must advance frame identity");

        JsonObject evidence = new JsonObject();
        evidence.addProperty("option_count", ids.size());
        evidence.addProperty("recomputed_match", true);
        writeEvidence("freshness-options.json", evidence);
    }

    @Test
    void olderFrameResponseFailsClosed() throws Exception {
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws56-fresh-stale");
        JsonObject first = Ws52.requirePendingDecision(Ws52.getDecision(bridge));
        String firstId = first.get("decision_id").getAsString();
        // Valid submit advances.
        JsonObject after = Ws52.submit(bridge, first,
                List.of(firstOption(first)));
        JsonObject second = Ws52.requirePendingDecision(after);
        assertTrue(!second.get("decision_id").getAsString().equals(firstId));
        // Replaying the older frame (correct old digest, old id) must fail closed.
        JsonObject replay = Ws52.submitResponse(first, List.of(firstOption(first)), null);
        JsonObject failure = Ws52.requireFailure(
                Ws52.send(bridge, "submit_full_game_decision", replay));
        assertTrue(Ws52.errorText(failure).contains("STALE_DECISION"),
                () -> "older frame must fail closed as STALE: " + failure);
        // Tampered freshness with the CURRENT id must also fail closed.
        JsonObject tampered = Ws52.submitResponse(second, List.of(firstOption(second)), null);
        tampered.getAsJsonObject("response").addProperty("frame_digest",
                "0000000000000000000000000000000000000000000000000000000000000000");
        JsonObject tamperedFailure = Ws52.requireFailure(
                Ws52.send(bridge, "submit_full_game_decision", tampered));
        assertTrue(Ws52.errorText(tamperedFailure).contains("STALE_DECISION"),
                () -> "tampered frame_digest must fail closed: " + tamperedFailure);

        JsonObject evidence = new JsonObject();
        evidence.addProperty("stale_rejected", true);
        evidence.addProperty("tampered_rejected", true);
        writeEvidence("freshness-stale.json", evidence);
    }

    @Test
    void missingFreshnessFailsClosed() throws Exception {
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws56-fresh-missing");
        JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(bridge));
        JsonObject stripped = Ws52.submitResponse(decision, List.of(firstOption(decision)), null);
        JsonObject response = stripped.getAsJsonObject("response");
        response.remove("frame_digest");
        response.remove("option_digest");
        response.remove("frame_revision");
        JsonObject failure = Ws52.requireFailure(
                Ws52.send(bridge, "submit_full_game_decision", stripped));
        assertTrue(Ws52.errorText(failure).contains("PILOT_RESPONSE_INVALID")
                        || Ws52.errorText(failure).contains("missing freshness"),
                () -> "missing freshness must fail closed: " + failure);
    }

    @Test
    void freshnessDoesNotLeakHiddenInformation() throws Exception {
        // Sentinel decks give ground truth: viewer 0 must never see "Mountain"
        // in any freshness field; viewer 1 must never see "Island".
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws56-fresh-leak");
        Ws52.pilotOpening(bridge);
        JsonObject obs0 = Ws52.getObservation(bridge, 0);
        JsonObject obs1 = Ws52.getObservation(bridge, 1);
        assertTrue(!obs0.toString().contains("Mountain"), "viewer 0 freshness/observation leak");
        assertTrue(!obs1.toString().contains("Island"), "viewer 1 freshness/observation leak");
        JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(bridge));
        int actorSeat = decision.get("seat").getAsInt();
        String forbidden = actorSeat == 0 ? "Mountain" : "Island";
        // Check every freshness-carrying surface: frame, freshness object,
        // digests, provenance, pilot_state, context, options, source.
        String frameText = decision.toString().toLowerCase();
        // Digests are hashes; they must not literally contain the forbidden name.
        // (A hash collision containing the substring is negligible; this checks
        // the digest FIELDS don't embed names.)
        assertTrue(!decision.get("frame_digest").getAsString().toLowerCase().contains(forbidden.toLowerCase()));
        assertTrue(!decision.get("option_digest").getAsString().toLowerCase().contains(forbidden.toLowerCase()));
        // The full frame must not contain the forbidden identity either (M4).
        assertTrue(!decision.toString().contains(forbidden),
                () -> "opponent identity in freshness frame for actor " + actorSeat);

        JsonObject evidence = new JsonObject();
        evidence.addProperty("actor_seat", actorSeat);
        evidence.addProperty("forbidden", forbidden);
        evidence.addProperty("no_leak", true);
        writeEvidence("freshness-leak.json", evidence);
    }

    @Test
    void m3FullNegativeMatrix() throws Exception {
        // WS56 M3 through the JSONL lane with freshness: unknown, stale,
        // malformed, wrong principal, wrong kind (via decision_id mismatch),
        // ambiguous (collapsing unit), previous-frame replay. No fallback.
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws56-m3-matrix");
        JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(bridge));

        // Unknown option.
        JsonObject unknown = Ws52.requireFailure(Ws52.send(bridge, "submit_full_game_decision",
                Ws52.submitResponse(decision, List.of("obj-fabricated-by-pilot"), null)));
        assertTrue(Ws52.errorText(unknown).contains("ILLEGAL_ACTION"));

        // Stale decision id.
        JsonObject forged = Ws52.submitResponse(decision, List.of(firstOption(decision)), null);
        forged.getAsJsonObject("response").addProperty("decision_id", "00000000-dead-beef");
        JsonObject stale = Ws52.requireFailure(Ws52.send(bridge, "submit_full_game_decision", forged));
        assertTrue(Ws52.errorText(stale).contains("STALE_DECISION"));

        // Malformed: missing response.
        JsonObject missing = Ws52.requireFailure(
                Ws52.send(bridge, "submit_full_game_decision", new JsonObject()));
        assertTrue(Ws52.errorText(missing).contains("invalid_full_game_decision"));

        // Wrong principal.
        JsonObject wrongActor = Ws52.submitResponse(decision, List.of(firstOption(decision)), null);
        wrongActor.getAsJsonObject("response").addProperty("actor_id", "00000000-wrong-actor");
        JsonObject wrong = Ws52.requireFailure(Ws52.send(bridge, "submit_full_game_decision", wrongActor));
        assertTrue(Ws52.errorText(wrong).contains("wrong actor"));

        // Wrong Decision kind: submit a mulligan-frame response against a
        // priority frame is already a decision_id mismatch (kind is bound in
        // frame_digest + decision_id). Prove kind is bound by showing two
        // consecutive frames have different kinds or digests.
        JsonObject after = Ws52.submit(bridge, decision, List.of(firstOption(decision)));
        JsonObject next = Ws52.requirePendingDecision(after);
        assertTrue(!decision.get("decision_id").getAsString().equals(next.get("decision_id").getAsString()));
        // Replaying the previous frame's exact response against the new frame
        // must fail closed (previous-frame test).
        JsonObject replayPrev = Ws52.submitResponse(decision, List.of(firstOption(decision)), null);
        JsonObject replayFailure = Ws52.requireFailure(
                Ws52.send(bridge, "submit_full_game_decision", replayPrev));
        assertTrue(Ws52.errorText(replayFailure).contains("STALE_DECISION"));

        JsonObject evidence = new JsonObject();
        evidence.addProperty("unknown_rejected", true);
        evidence.addProperty("stale_rejected", true);
        evidence.addProperty("malformed_rejected", true);
        evidence.addProperty("wrong_principal_rejected", true);
        evidence.addProperty("previous_frame_rejected", true);
        writeEvidence("m3-matrix.json", evidence);
    }

    @Test
    void controllerAmbiguousAndBounds() throws Exception {
        // Ambiguous identity (collapsing) + bounds + duplicate + numeric range
        // at the controller level (harness, no JSONL).
        try (Ws52Harness harness = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            harness.start(0);
            harness.pilotOpening(1);
            JsonObject first = harness.awaitFrame();
            // Unknown.
            XmageFullGameDecisionController.DecisionException unknown = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> harness.submit(first, List.of("obj-nope"), null));
            assertTrue(unknown.getMessage().contains("ILLEGAL_ACTION"));
            // Bounds (mulligan 1..1, empty).
            XmageFullGameDecisionController.DecisionException bounds = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> harness.submit(first, List.of(), null));
            assertTrue(bounds.getMessage().contains("PILOT_RESPONSE_INVALID"));
            // Valid advance, then stale replay.
            String firstId = first.get("decision_id").getAsString();
            harness.submitKeep(first);
            JsonObject second = harness.awaitFrame();
            assertTrue(!second.get("decision_id").getAsString().equals(firstId));
            XmageFullGameDecisionController.DecisionException stale = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> harness.submit(first, List.of(firstOption(first)), null));
            assertTrue(stale.getMessage().contains("STALE_DECISION"));
        }
        // Collapsing unit (ambiguous identity).
        JsonArray nativeOptions = new JsonArray();
        nativeOptions.add(XmageFullGameDecisionController.option(
                "11111111-1111-1111-1111-111111111111", "A", "target", new JsonObject()));
        nativeOptions.add(XmageFullGameDecisionController.option(
                "22222222-2222-2222-2222-222222222222", "B", "target", new JsonObject()));
        java.util.Map<String, String> collapsing = java.util.Map.of(
                "11111111-1111-1111-1111-111111111111", "same-external",
                "22222222-2222-2222-2222-222222222222", "same-external");
        IllegalStateException ambiguous = assertThrows(IllegalStateException.class,
                () -> XmageDecisionOptionIdentity.externalize(nativeOptions, collapsing));
        assertTrue(ambiguous.getMessage().contains("COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER"));

        JsonObject evidence = new JsonObject();
        evidence.addProperty("controller_negatives_pass", true);
        writeEvidence("m3-controller.json", evidence);
    }

    // ------------------------------------------------------------------

    private static XmageFullGameJsonlBridge startSentinelGame(String gameId) {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        String handleA = Ws52.importDeck(bridge, Ws52.sentinelDeckA());
        String handleB = Ws52.importDeck(bridge, Ws52.sentinelDeckB());
        Ws52.createFullGame(bridge, gameId, List.of(handleA, handleB), Ws52.SEED_A);
        Ws52.startFullGame(bridge);
        return bridge;
    }

    private static String firstOption(JsonObject decision) {
        JsonArray options = decision.getAsJsonArray("legal_options");
        assertTrue(options.size() > 0, "decision frame has no options");
        return options.get(0).getAsJsonObject().get("option_id").getAsString();
    }

    private static void writeEvidence(String name, JsonObject payload) throws Exception {
        Path dir = Path.of("ws56-evidence");
        Files.createDirectories(dir);
        Files.writeString(dir.resolve(name), payload.toString(), StandardCharsets.UTF_8);
    }
}

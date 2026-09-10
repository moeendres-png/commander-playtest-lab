package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS52 M3 — stale / invalid / ambiguous rejection.
 *
 * <p>Every negative control must fail closed with a typed error and must
 * never resolve by rematching, defaulting, or falling back. Transport-level
 * controls run against the JSONL lane; controller/binding controls run
 * against the live decision controller.</p>
 */
class Ws52M3RejectionTest {

    // ------------------------------------------------------------------
    // Transport envelope (JSONL lane, black-box pilot)
    // ------------------------------------------------------------------

    @Test
    void staleDecisionIdIsRejected() {
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws52-m3-stale");
        JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(bridge));
        JsonObject forged = Ws52.submitResponse(decision, List.of(firstOption(decision)), null);
        forged.getAsJsonObject("response").addProperty("decision_id", "00000000-dead-beef");
        JsonObject failure = Ws52.requireFailure(
                Ws52.send(bridge, "submit_full_game_decision", forged));
        assertTrue(Ws52.errorText(failure).contains("STALE_DECISION"),
                () -> "stale id must be rejected: " + failure);
    }

    @Test
    void wrongActorIsRejected() {
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws52-m3-actor");
        JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(bridge));
        JsonObject forged = Ws52.submitResponse(decision, List.of(firstOption(decision)), null);
        forged.getAsJsonObject("response").addProperty("actor_id", "00000000-wrong-actor");
        JsonObject failure = Ws52.requireFailure(
                Ws52.send(bridge, "submit_full_game_decision", forged));
        assertTrue(Ws52.errorText(failure).contains("wrong actor"),
                () -> "wrong actor must be rejected: " + failure);
    }

    @Test
    void unknownOptionIsRejected() {
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws52-m3-unknown");
        JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(bridge));
        JsonObject failure = Ws52.requireFailure(Ws52.send(bridge, "submit_full_game_decision",
                Ws52.submitResponse(decision, List.of("obj-fabricated-by-pilot"), null)));
        assertTrue(Ws52.errorText(failure).contains("ILLEGAL_ACTION"),
                () -> "fabricated option must be rejected: " + failure);
    }

    @Test
    void malformedResponsesAreRejected() {
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws52-m3-malformed");
        // Missing response object.
        JsonObject missing = Ws52.requireFailure(
                Ws52.send(bridge, "submit_full_game_decision", new JsonObject()));
        assertTrue(Ws52.errorText(missing).contains("invalid_full_game_decision"),
                () -> "missing response must be rejected: " + missing);
        // Not JSON at all.
        XmageFullGameJsonlBridge.Result raw = bridge.handle("{not json");
        assertTrue(!JsonTestHelper.success(raw));
        // Wrong protocol version.
        JsonObject versioned = new JsonObject();
        versioned.addProperty("protocol_version", "0.0.0-wrong");
        versioned.addProperty("request_id", "ws52-m3-version");
        versioned.addProperty("message_type", "get_full_game_decision");
        versioned.add("payload", new JsonObject());
        JsonObject versionFailure = Ws52.requireFailure(
                JsonTestHelper.parse(bridge.handle(versioned.toString())));
        assertTrue(Ws52.errorText(versionFailure).contains("protocol_version_mismatch"),
                () -> "wrong protocol version must be rejected: " + versionFailure);
    }

    @Test
    void secondGameInOneProcessIsRefused() {
        XmageFullGameJsonlBridge bridge = startSentinelGame("ws52-m3-once");
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", "ws52-m3-twice");
        JsonArray handles = new JsonArray();
        handles.add("whatever");
        handles.add("whatever");
        payload.add("deck_handles", handles);
        payload.addProperty("seed", Ws52.SEED_A);
        JsonObject failure = Ws52.requireFailure(
                Ws52.send(bridge, "create_full_game", payload));
        assertTrue(Ws52.errorText(failure).contains("full_game_process_already_used"),
                () -> "second game in one process must be refused: " + failure);
    }

    // ------------------------------------------------------------------
    // Live controller (harness game, started, mulligan pending)
    // ------------------------------------------------------------------

    @Test
    void controllerRejectsStaleUnknownDuplicateAndBounds() {
        try (Ws52Harness harness = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            harness.start(0);
            harness.pilotOpening(1);
            JsonObject first = harness.awaitFrame();
            String firstId = first.get("decision_id").getAsString();

            // Unknown option.
            XmageFullGameDecisionController.DecisionException unknown = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> harness.submit(first, List.of("obj-nope"), null));
            assertTrue(unknown.getMessage().contains("ILLEGAL_ACTION"));

            // Selection-count bounds (the second mulligan requires exactly one).
            XmageFullGameDecisionController.DecisionException bounds = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> harness.submit(first, List.of(), null));
            assertTrue(bounds.getMessage().contains("PILOT_RESPONSE_INVALID"));

            // Valid submit advances; replaying the first frame is stale.
            harness.submitKeep(first);
            JsonObject second = harness.awaitFrame();
            assertTrue(!second.get("decision_id").getAsString().equals(firstId));
            XmageFullGameDecisionController.DecisionException stale = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> harness.submit(first, List.of(firstOption(first)), null));
            assertTrue(stale.getMessage().contains("STALE_DECISION"),
                    () -> "replayed frame must be stale, observed: " + stale.getMessage());
        }
    }

    @Test
    void controllerRejectsDuplicateSelectionWithinBounds() throws Exception {
        // Mulligan frames (1..1) reject pairs at the bounds check before the
        // duplicate check; a 0..2 target frame reaches the duplicate gate.
        // The engine is parked at priority while the phantom direct player
        // (own controller) issues the target call on the live game.
        try (Ws52Harness harness = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            mage.target.TargetPlayer target = new mage.target.TargetPlayer(0, 2, false);
            java.util.concurrent.ExecutorService exec =
                    java.util.concurrent.Executors.newSingleThreadExecutor();
            try {
                java.util.concurrent.Future<Boolean> worker = exec.submit(
                        () -> direct.player().chooseTarget(mage.constants.Outcome.Benefit,
                                target, null, harness.game));
                JsonObject pending = direct.awaitDecision();
                assertEquals("target", pending.get("decision_class").getAsString());
                String one = firstOption(pending);
                XmageFullGameDecisionController.DecisionException duplicate = assertThrows(
                        XmageFullGameDecisionController.DecisionException.class,
                        () -> direct.submit(pending, List.of(one, one), null));
                assertTrue(duplicate.getMessage().contains("duplicate"),
                        () -> "duplicate selection must be rejected: " + duplicate.getMessage());
                // The frame stays live after the rejected submit; resolve it cleanly.
                direct.submit(pending, List.of(one), null);
                assertTrue(worker.get(30, java.util.concurrent.TimeUnit.SECONDS));
            } finally {
                exec.shutdownNow();
            }
        }
    }

    @Test
    void controllerRejectsOutOfRangeNumeric() throws Exception {
        try (Ws52Harness harness = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            java.util.concurrent.ExecutorService exec =
                    java.util.concurrent.Executors.newSingleThreadExecutor();
            try {
                java.util.concurrent.Future<Integer> worker =
                        exec.submit(() -> direct.player().announceX(
                                1, 6, "WS52 announce X", harness.game, null, false));
                JsonObject pending = direct.awaitDecision();
                assertEquals("announce_x", pending.get("decision_class").getAsString());
                assertEquals(0, pending.getAsJsonArray("legal_options").size());

                XmageFullGameDecisionController.DecisionException range = assertThrows(
                        XmageFullGameDecisionController.DecisionException.class,
                        () -> direct.submit(pending,
                                List.of(), 7));
                assertTrue(range.getMessage().contains("out of range"),
                        () -> "out-of-range numeric must be rejected: " + range.getMessage());

                direct.submit(pending, List.of(), 4);
                assertEquals(4, worker.get(30, java.util.concurrent.TimeUnit.SECONDS).intValue());
            } finally {
                exec.shutdownNow();
            }
        }
    }

    // ------------------------------------------------------------------
    // Binding envelope (pure unit: zero / multiple native binding)
    // ------------------------------------------------------------------

    @Test
    void zeroNativeBindingFailsClosed() {
        JsonArray nativeOptions = new JsonArray();
        nativeOptions.add(XmageFullGameDecisionController.option(
                "11111111-1111-1111-1111-111111111111", "Hidden", "target", new JsonObject()));
        IllegalStateException failure = assertThrows(IllegalStateException.class,
                () -> XmageDecisionOptionIdentity.externalize(nativeOptions, Map.of()));
        assertTrue(failure.getMessage().contains("COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER"),
                () -> "zero binding must fail closed: " + failure.getMessage());
    }

    @Test
    void collapsingBindingsFailClosed() {
        JsonArray nativeOptions = new JsonArray();
        nativeOptions.add(XmageFullGameDecisionController.option(
                "11111111-1111-1111-1111-111111111111", "A", "target", new JsonObject()));
        nativeOptions.add(XmageFullGameDecisionController.option(
                "22222222-2222-2222-2222-222222222222", "B", "target", new JsonObject()));
        Map<String, String> collapsing = Map.of(
                "11111111-1111-1111-1111-111111111111", "same-external",
                "22222222-2222-2222-2222-222222222222", "same-external");
        IllegalStateException failure = assertThrows(IllegalStateException.class,
                () -> XmageDecisionOptionIdentity.externalize(nativeOptions, collapsing));
        assertTrue(failure.getMessage().contains("COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER"),
                () -> "collapsing bindings must fail closed: " + failure.getMessage());
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

    /** Minimal JSON helpers local to M3 (transport-shape assertions only). */
    private static final class JsonTestHelper {
        static boolean success(XmageFullGameJsonlBridge.Result result) {
            return parse(result).get("success").getAsBoolean();
        }

        static JsonObject parse(XmageFullGameJsonlBridge.Result result) {
            return com.google.gson.JsonParser.parseString(result.json()).getAsJsonObject();
        }
    }
}

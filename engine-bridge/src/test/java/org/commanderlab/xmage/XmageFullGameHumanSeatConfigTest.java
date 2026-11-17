package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #1169 (M4 human seat): contract tests for configurable decision timeouts
 * ({@code commanderlab.fullGame.decisionTimeoutSeconds} and {@code decision_timeout_seconds})
 * and explicit {@code human_seats} wiring on {@code create_full_game}.
 */
class XmageFullGameHumanSeatConfigTest {

    @AfterEach
    void clearProperties() {
        System.clearProperty(XmageFullGameDecisionController.DECISION_TIMEOUT_SECONDS_PROPERTY);
        System.clearProperty(XmageFullGameDecisionController.SKIP_FORCED_DECISIONS_PROPERTY);
    }

    @Test
    void defaultsMatchSealedStandard() {
        assertEquals(Duration.ofSeconds(120), XmageFullGameDecisionController.defaultTimeoutFromProperty());
        assertEquals(Duration.ofSeconds(120), XmageFullGameDecisionController.timeoutFromSeconds(120));
        assertTrue(XmageFullGameDecisionController.timeoutFromSeconds(0).toDays() >= 30);
        assertThrows(
                IllegalArgumentException.class,
                () -> XmageFullGameDecisionController.timeoutFromSeconds(-1)
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> XmageFullGameDecisionController.timeoutFromSeconds(86_401)
        );
    }

    @Test
    void propertyOverridesDefaultTimeoutAndRejectsInvalidValues() {
        System.setProperty(XmageFullGameDecisionController.DECISION_TIMEOUT_SECONDS_PROPERTY, "3600");
        assertEquals(Duration.ofSeconds(3600), XmageFullGameDecisionController.defaultTimeoutFromProperty());

        System.setProperty(XmageFullGameDecisionController.DECISION_TIMEOUT_SECONDS_PROPERTY, "0");
        assertTrue(XmageFullGameDecisionController.defaultTimeoutFromProperty().toDays() >= 30);

        System.setProperty(XmageFullGameDecisionController.DECISION_TIMEOUT_SECONDS_PROPERTY, "abc");
        assertThrows(
                IllegalArgumentException.class,
                XmageFullGameDecisionController::defaultTimeoutFromProperty
        );
    }

    @Test
    void createFullGameConfiguresHumanSeatsAndTimeoutFailClosed() throws Exception {
        System.setProperty(XmageFullGameDecisionController.SKIP_FORCED_DECISIONS_PROPERTY, "true");
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        assertTrue(startFullGameLane(bridge));

        List<String> handles = List.of(
                importSampleDeck(bridge, "d1"),
                importSampleDeck(bridge, "d2")
        );

        // Out-of-range human_seat fails closed without consuming a game slot.
        JsonObject badSeatPayload = new JsonObject();
        badSeatPayload.addProperty("game_id", "bad-seat");
        JsonArray handleArray = new JsonArray();
        handles.forEach(handleArray::add);
        badSeatPayload.add("deck_handles", handleArray);
        badSeatPayload.addProperty("seed", 11);
        badSeatPayload.addProperty("starting_player_seat", 0);
        JsonArray badSeats = new JsonArray();
        badSeats.add(2);
        badSeatPayload.add("human_seats", badSeats);

        JsonObject badResp = send(bridge, "bad-seat-1", "create_full_game", badSeatPayload);
        assertFalse(badResp.get("success").getAsBoolean());

        // Invalid negative timeout also fails closed without consuming a game slot.
        JsonObject badTimeoutPayload = badSeatPayload.deepCopy();
        badTimeoutPayload.remove("human_seats");
        badTimeoutPayload.addProperty("decision_timeout_seconds", -10);
        JsonObject badTimeoutResp = send(bridge, "bad-to-1", "create_full_game", badTimeoutPayload);
        assertFalse(badTimeoutResp.get("success").getAsBoolean());

        // Valid creation with human_seats=[0] and unlimited timeout (0) succeeds.
        JsonObject okPayload = new JsonObject();
        okPayload.addProperty("game_id", "human-test-1");
        okPayload.add("deck_handles", handleArray);
        okPayload.addProperty("seed", 11);
        okPayload.addProperty("starting_player_seat", 0);
        okPayload.addProperty("decision_timeout_seconds", 0);
        JsonArray humanSeats = new JsonArray();
        humanSeats.add(0);
        okPayload.add("human_seats", humanSeats);

        JsonObject okResp = send(bridge, "ok-create", "create_full_game", okPayload);
        assertTrue(okResp.get("success").getAsBoolean(), okResp.toString());
        JsonObject payload = okResp.getAsJsonObject("payload");
        assertEquals(0, payload.get("decision_timeout_seconds").getAsInt());
        assertEquals(1, payload.getAsJsonArray("human_seats").size());
        assertEquals(0, payload.getAsJsonArray("human_seats").get(0).getAsInt());

        // Start full game and poll until the first pending decision is published.
        JsonObject started = send(bridge, "start-1", "start_full_game", new JsonObject());
        assertTrue(started.get("success").getAsBoolean(), started.toString());
        JsonObject statusPayload = started.getAsJsonObject("payload");
        JsonObject decision = statusPayload.has("decision") && statusPayload.get("decision").isJsonObject()
                ? statusPayload.getAsJsonObject("decision")
                : null;
        long deadline = System.currentTimeMillis() + 5_000L;
        while (decision == null && System.currentTimeMillis() < deadline) {
            Thread.sleep(25);
            JsonObject poll = send(bridge, "poll-" + System.nanoTime(), "get_full_game_decision", new JsonObject());
            assertTrue(poll.get("success").getAsBoolean(), poll.toString());
            JsonObject pollPayload = poll.getAsJsonObject("payload");
            if (pollPayload.has("decision") && pollPayload.get("decision").isJsonObject()) {
                decision = pollPayload.getAsJsonObject("decision");
            }
        }
        assertNotNull(decision);
        assertTrue(decision.get("timeout_millis").getAsLong() > 120_000L);
        String humanActorId = decision.get("actor_id").getAsString();
        JsonObject offerReq = new JsonObject();
        offerReq.addProperty("player_id", humanActorId);
        JsonObject offerResp = send(bridge, "offer-1", "get_concede_offer", offerReq);
        assertTrue(offerResp.get("success").getAsBoolean(), offerResp.toString());
        assertTrue(offerResp.getAsJsonObject("payload").get("concede_available").getAsBoolean());
        // Cleanly end the test session.
        JsonObject shutdown = send(bridge, "shut-1", "shutdown_game", new JsonObject());
        assertTrue(shutdown.get("success").getAsBoolean(), shutdown.toString());
    }

    @Test
    void createFullGameEchoesZeroWhenPropertySetsUnlimitedTimeout() {
        System.setProperty(XmageFullGameDecisionController.DECISION_TIMEOUT_SECONDS_PROPERTY, "0");
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        assertTrue(startFullGameLane(bridge));
        List<String> handles = List.of(
                importSampleDeck(bridge, "prop0-d1"),
                importSampleDeck(bridge, "prop0-d2")
        );
        JsonArray handleArray = new JsonArray();
        handles.forEach(handleArray::add);
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", "prop-zero-timeout");
        payload.add("deck_handles", handleArray);
        payload.addProperty("seed", 19);
        payload.addProperty("starting_player_seat", 0);
        JsonObject resp = send(bridge, "create-prop-0", "create_full_game", payload);
        assertTrue(resp.get("success").getAsBoolean(), resp.toString());
        assertEquals(0, resp.getAsJsonObject("payload").get("decision_timeout_seconds").getAsInt());
    }

    private static boolean startFullGameLane(XmageFullGameJsonlBridge bridge) {
        JsonObject resp = send(bridge, "start-engine", "start_engine", new JsonObject());
        return resp.get("success").getAsBoolean();
    }

    private static String importSampleDeck(XmageFullGameJsonlBridge bridge, String id) {
        JsonObject deck = new JsonObject();
        deck.addProperty("deck_id", id);
        deck.addProperty("deck_hash", "hash-" + id);
        JsonArray commanders = new JsonArray();
        commanders.add("Isamaru, Hound of Konda");
        deck.add("commander_names", commanders);
        JsonArray mainboard = new JsonArray();
        for (int i = 0; i < 99; i++) {
            mainboard.add("Plains");
        }
        deck.add("mainboard", mainboard);
        deck.add("sideboard", new JsonArray());

        JsonObject payload = new JsonObject();
        payload.add("deck", deck);
        JsonObject resp = send(bridge, "imp-" + id, "import_deck", payload);
        assertTrue(resp.get("success").getAsBoolean(), resp.toString());
        return resp.getAsJsonObject("payload").getAsJsonObject("deck_handle").get("handle_id").getAsString();
    }

    private static JsonObject send(
            XmageFullGameJsonlBridge bridge,
            String requestId,
            String type,
            JsonObject payload
    ) {
        JsonObject req = new JsonObject();
        req.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        req.addProperty("request_id", requestId);
        req.addProperty("message_type", type);
        req.add("payload", payload);
        XmageFullGameJsonlBridge.Result res = bridge.handle(req.toString());
        return JsonParser.parseString(res.json()).getAsJsonObject();
    }
}

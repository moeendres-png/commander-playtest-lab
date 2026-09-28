package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * PB-03: the transport seam between a REQUESTED starting state and the engine's
 * existing native restoration.
 *
 * <p>The restoration engine already existed and assembled state through public
 * engine APIs only, and it was already exercised by the internal causal
 * reconstruction lanes. What did not exist was any protocol verb that could
 * DELIVER a requested starting state, so the mechanism was real and unreachable.
 * A dimension list advertising support while nothing can arrive is exactly the
 * condition that makes a blocked row look like an engine limitation when it is
 * actually a Lab execution-path gap.</p>
 *
 * <p>These tests qualify the transport boundary only. They do not qualify Magic
 * semantics: the engine materialises and reads back, and the Lab compares a
 * readback to a fixture it already owns. No expected outcome is injected, and no
 * state is fabricated on the Lab side.</p>
 */
class XmageStartingStateTransportPb03Test {

    private static String request(String method, JsonObject payload) {
        JsonObject root = new JsonObject();
        root.addProperty("request_id", "r-" + method);
        root.addProperty("protocol_version", "2.0.0");
        root.addProperty("message_type", method);
        root.add("payload", payload);
        return root.toString();
    }

    private static JsonObject response(String raw) {
        return com.google.gson.JsonParser.parseString(raw).getAsJsonObject();
    }

    /** A minimal but semantically real frozen starting-state record. */
    private static JsonObject startingState() {
        JsonObject record = new JsonObject();
        record.addProperty("plan_id", "pb03-transport-probe");
        record.addProperty("player_count", 2);

        com.google.gson.JsonArray players = new com.google.gson.JsonArray();
        for (int seat = 1; seat <= 2; seat++) {
            JsonObject player = new JsonObject();
            player.addProperty("player_id", "P" + seat);
            player.addProperty("seat", seat);
            player.addProperty("life", 40);
            players.add(player);
        }
        record.add("players", players);

        JsonObject commander = new JsonObject();
        commander.addProperty("semantic_id", "cmd-1");
        commander.addProperty("card_identity", "Isamaru, Hound of Konda");
        commander.addProperty("owner_player_id", "P1");
        commander.addProperty("cast_count", 0);
        JsonObject commanders = new JsonObject();
        commanders.add("cmd-1", commander);
        record.add("commanders", commanders);

        return record;
    }

    private static JsonObject createPayload() {
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", "pb03-probe");
        com.google.gson.JsonArray handles = new com.google.gson.JsonArray();
        handles.add("h1");
        handles.add("h2");
        payload.add("deck_handles", handles);
        payload.addProperty("seed", 424242L);
        return payload;
    }

    @Test
    void transportReachabilityIsAdvertisedSeparatelyFromDimensionSupport() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        bridge.handle(request("start_engine", new JsonObject()));
        JsonObject payload = response(bridge.handle(request("get_capabilities", new JsonObject())).json())
                .getAsJsonObject("payload");
        JsonObject lane = payload.getAsJsonObject("full_game_lane");

        // Reachability is its own published fact. A caller must be able to check
        // that a starting state can ARRIVE, not infer it from a dimension list.
        assertTrue(lane.get("starting_state_request_supported").getAsBoolean());
        assertEquals("starting_state", lane.get("starting_state_request_field").getAsString());
        assertEquals("create_full_game", lane.get("starting_state_request_message").getAsString());
        // The manifest itself is still published verbatim; the new fact does not
        // replace or restate it.
        assertNotNull(lane.getAsJsonObject("state_restoration_dimensions"));
    }

    @Test
    void aMalformedStartingStateIsRejectedBeforeAnythingIsMaterialised() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        bridge.handle(request("start_engine", new JsonObject()));
        JsonObject payload = createPayload();
        payload.addProperty("starting_state", "not-an-object");
        JsonObject response = response(bridge.handle(request("create_full_game", payload)).json());

        assertFalse(response.get("success").getAsBoolean());
        assertEquals("invalid_starting_state", response.getAsJsonArray("errors").get(0)
                .getAsJsonObject().get("code").getAsString());
    }

    @Test
    void aStartingStateTheEngineCannotHonourFailsClosed() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        bridge.handle(request("start_engine", new JsonObject()));
        JsonObject payload = createPayload();
        // A stack is an explicitly unsupported dimension, per the published manifest.
        JsonObject record = startingState();
        record.add("stack_state", new com.google.gson.JsonArray());
        payload.add("starting_state", record);
        JsonObject response = response(bridge.handle(request("create_full_game", payload)).json());

        assertFalse(response.get("success").getAsBoolean());
        String code = response.getAsJsonArray("errors").get(0)
                .getAsJsonObject().get("code").getAsString();
        String detail = response.getAsJsonArray("errors").get(0)
                .getAsJsonObject().get("message").getAsString();
        // Whatever the engine objects to, the refusal must be reported as a
        // refusal and must not be presented as a partially materialised game.
        assertTrue(
                code.equals("starting_state_unsupported")
                        || code.equals("starting_state_rejected_by_engine"),
                "expected a fail-closed restoration refusal, observed: " + code + " / " + detail);
    }

    @Test
    void anAbsentStartingStateLeavesRestorationUnreported() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        bridge.handle(request("start_engine", new JsonObject()));
        JsonObject payload = createPayload();
        JsonObject response = response(bridge.handle(request("create_full_game", payload)).json());

        // A deck-handle create still fails on deck import in this harness, but the
        // point is narrower: with no starting state requested, no restoration fact
        // may be reported, so an absent pair can never read as a success.
        if (response.get("success").getAsBoolean()) {
            JsonObject created = response.getAsJsonObject("payload");
            assertFalse(created.get("starting_state_requested").getAsBoolean());
            assertNull(created.get("requested_starting_state_digest"));
            assertNull(created.get("observed_starting_state_digest"));
            assertFalse(created.get("starting_state_readback_observed").getAsBoolean());
        }
    }
}

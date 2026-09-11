package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageFullGameBridgeContractTest {

    @Test
    void advertisesDedicatedTwoThroughFivePlayerSeededTechnicalLaneWithoutGlobalPromotion() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();

        JsonObject start = response(bridge.handle(request("start_engine", new JsonObject())).json());
        assertTrue(start.get("success").getAsBoolean());
        JsonObject started = start.getAsJsonObject("payload");
        assertEquals("xmage_full_game_external_pilots", started.get("lane").getAsString());
        assertEquals(2, started.get("min_players").getAsInt());
        assertEquals(5, started.get("max_players").getAsInt());
        assertEquals("technical_conformance_only", started.get("evidence_class").getAsString());

        JsonObject capabilitiesResponse = response(
                bridge.handle(request("get_capabilities", new JsonObject())).json()
        );
        JsonObject payload = capabilitiesResponse.getAsJsonObject("payload");
        JsonObject capabilities = payload.getAsJsonObject("capabilities");
        JsonObject lane = payload.getAsJsonObject("full_game_lane");

        assertTrue(capabilities.get("commander_supported").getAsBoolean());
        assertTrue(capabilities.get("partner_supported").getAsBoolean());
        assertTrue(capabilities.get("multiplayer_supported").getAsBoolean());
        assertEquals(2, capabilities.get("min_players").getAsInt());
        assertEquals(5, capabilities.get("max_players").getAsInt());
        assertSupportedPlayerCounts(capabilities.getAsJsonArray("supported_player_counts"));
        assertTrue(capabilities.get("seed_supported").getAsBoolean());
        assertTrue(capabilities.get("target_selection_supported").getAsBoolean());
        assertTrue(capabilities.get("mode_selection_supported").getAsBoolean());
        assertTrue(capabilities.get("trigger_order_supported").getAsBoolean());
        assertTrue(capabilities.get("mulligan_supported").getAsBoolean());
        assertFalse(capabilities.get("legal_actions_supported").getAsBoolean());
        assertFalse(capabilities.get("action_submission_supported").getAsBoolean());
        assertFalse(capabilities.get("starting_state_injection_supported").getAsBoolean());
        assertFalse(capabilities.get("scenario_injection_supported").getAsBoolean());

        assertEquals(2, lane.get("min_players").getAsInt());
        assertEquals(5, lane.get("max_players").getAsInt());
        assertSupportedPlayerCounts(lane.getAsJsonArray("supported_player_counts"));
        assertTrue(lane.get("one_game_per_process").getAsBoolean());
        assertFalse(lane.get("generic_capability_promotion").getAsBoolean());
        assertFalse(lane.get("bit_exact_replay_validated").getAsBoolean());
        assertEquals(
                XmageFullGameDecisionController.PROTOCOL_VERSION,
                lane.get("decision_protocol_version").getAsString()
        );
    }

    @Test
    void acceptsTwoThroughFivePlayerCardinalityBeforeDeckResolution() {
        for (int playerCount = 2; playerCount <= 5; playerCount++) {
            XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
            JsonObject response = response(
                    bridge.handle(request(
                            "create_full_game",
                            unresolvedGamePayload("positive-" + playerCount + "p", playerCount)
                    )).json()
            );
            assertFalse(response.get("success").getAsBoolean());
            JsonArray errors = response.getAsJsonArray("errors");
            assertEquals(1, errors.size());
            assertEquals(
                    "full_game_creation_failed",
                    errors.get(0).getAsJsonObject().get("code").getAsString(),
                    "supported cardinality must advance past the player-count gate: " + playerCount
            );
        }
    }

    @Test
    void rejectsOneAndSixPlayerFullGamesBeforeDeckResolution() {
        for (int playerCount : new int[]{1, 6}) {
            XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
            JsonObject response = response(
                    bridge.handle(request(
                            "create_full_game",
                            unresolvedGamePayload("negative-" + playerCount + "p", playerCount)
                    )).json()
            );
            assertFalse(response.get("success").getAsBoolean());
            JsonArray errors = response.getAsJsonArray("errors");
            assertEquals(1, errors.size());
            assertEquals(
                    "invalid_player_count",
                    errors.get(0).getAsJsonObject().get("code").getAsString()
            );
        }
    }

    private static JsonObject unresolvedGamePayload(String gameId, int playerCount) {
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", gameId);
        payload.addProperty("seed", 17);
        JsonArray handles = new JsonArray();
        for (int index = 0; index < playerCount; index++) {
            handles.add("not-resolved-" + index);
        }
        payload.add("deck_handles", handles);
        return payload;
    }

    private static void assertSupportedPlayerCounts(JsonArray counts) {
        assertEquals(4, counts.size());
        for (int index = 0; index < counts.size(); index++) {
            assertEquals(index + 2, counts.get(index).getAsInt());
        }
    }

    private static String request(String messageType, JsonObject payload) {
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        request.addProperty("request_id", "test-" + messageType);
        request.addProperty("message_type", messageType);
        request.add("payload", payload);
        return request.toString();
    }

    private static JsonObject response(String json) {
        return JsonParser.parseString(json).getAsJsonObject();
    }
}

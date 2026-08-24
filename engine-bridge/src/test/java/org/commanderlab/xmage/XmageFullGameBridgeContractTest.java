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
    void advertisesDedicatedFourPlayerSeededTechnicalLaneWithoutGlobalPromotion() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();

        JsonObject start = response(bridge.handle(request("start_engine", new JsonObject())).json());
        assertTrue(start.get("success").getAsBoolean());
        JsonObject started = start.getAsJsonObject("payload");
        assertEquals("xmage_full_game_external_pilots", started.get("lane").getAsString());
        assertEquals(4, started.get("operational_pod_size").getAsInt());
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
        assertTrue(capabilities.get("seed_supported").getAsBoolean());
        assertTrue(capabilities.get("target_selection_supported").getAsBoolean());
        assertTrue(capabilities.get("mode_selection_supported").getAsBoolean());
        assertTrue(capabilities.get("trigger_order_supported").getAsBoolean());
        assertTrue(capabilities.get("mulligan_supported").getAsBoolean());
        assertFalse(capabilities.get("legal_actions_supported").getAsBoolean());
        assertFalse(capabilities.get("action_submission_supported").getAsBoolean());
        assertFalse(capabilities.get("starting_state_injection_supported").getAsBoolean());
        assertFalse(capabilities.get("scenario_injection_supported").getAsBoolean());

        assertEquals(4, lane.get("operational_pod_size").getAsInt());
        assertTrue(lane.get("one_game_per_process").getAsBoolean());
        assertFalse(lane.get("generic_capability_promotion").getAsBoolean());
        assertFalse(lane.get("bit_exact_replay_validated").getAsBoolean());
        assertEquals(
                XmageFullGameDecisionController.PROTOCOL_VERSION,
                lane.get("decision_protocol_version").getAsString()
        );
    }

    @Test
    void rejectsNonFourPlayerFullGameBeforeDeckResolution() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", "negative-3p");
        payload.addProperty("seed", 17);
        JsonArray handles = new JsonArray();
        handles.add("not-resolved-1");
        handles.add("not-resolved-2");
        handles.add("not-resolved-3");
        payload.add("deck_handles", handles);

        JsonObject response = response(bridge.handle(request("create_full_game", payload)).json());
        assertFalse(response.get("success").getAsBoolean());
        JsonArray errors = response.getAsJsonArray("errors");
        assertEquals(1, errors.size());
        assertEquals(
                "invalid_player_count",
                errors.get(0).getAsJsonObject().get("code").getAsString()
        );
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

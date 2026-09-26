package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS204 generic Protocol-2 boundary on the dedicated full-game lane.
 *
 * <p>Decision-scoped {@code get_legal_actions}/{@code submit_action} must fail
 * closed without a game and must keep global promotion flags false.</p>
 */
class XmageFullGameGenericBridgeTest {

    @Test
    void genericActionsWithoutGameFailClosed() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();

        JsonObject legal = response(bridge.handle(request("get_legal_actions", new JsonObject())).json());
        assertFalse(legal.get("success").getAsBoolean());

        JsonObject payload = new JsonObject();
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "p1");
        proposal.addProperty("actor_id", "actor");
        proposal.addProperty("legal_action_id", "decision:option");
        proposal.addProperty("action_type", "pass_priority");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        proposal.add("choices", new JsonObject());
        payload.add("proposal", proposal);
        JsonObject submitted = response(bridge.handle(request("submit_action", payload)).json());
        assertFalse(submitted.get("success").getAsBoolean());
    }

    @Test
    void malformedSubmitProposalFailsClosedWithoutGame() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        JsonObject payload = new JsonObject();
        payload.addProperty("unexpected", "shape");
        JsonObject response = response(bridge.handle(request("submit_action", payload)).json());
        assertFalse(response.get("success").getAsBoolean());
        assertEquals(
                "invalid_full_game_decision",
                response.getAsJsonArray("errors").get(0).getAsJsonObject().get("code").getAsString()
        );
    }

    @Test
    void genericCapabilityFlagsRemainUnpromoted() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        JsonObject capabilities = response(
                bridge.handle(request("get_capabilities", new JsonObject())).json()
        ).getAsJsonObject("payload").getAsJsonObject("capabilities");
        assertFalse(capabilities.get("legal_actions_supported").getAsBoolean());
        assertFalse(capabilities.get("action_submission_supported").getAsBoolean());
        assertTrue(capabilities.get("notes").toString().contains("WS204"));
    }

    private static String request(String messageType, JsonObject payload) {
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        request.addProperty("request_id", "ws204-" + messageType);
        request.addProperty("message_type", messageType);
        request.add("payload", payload);
        return request.toString();
    }

    private static JsonObject response(String json) {
        return JsonParser.parseString(json).getAsJsonObject();
    }
}

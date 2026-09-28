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


    @Test
    void nativeStateTransportRequiresExactDigestAndExternalDecisions() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        JsonObject record = XmageNativeStateRestorationTest.frozenRecord("WS05-CMD-TAX-2");

        JsonObject createPayload = new JsonObject();
        createPayload.addProperty("game_id", "pb03-transport-tax2");
        createPayload.addProperty("seed", 424242L);
        createPayload.add("record", record.deepCopy());

        JsonObject created = response(
                bridge.handle(request("create_native_state_game", createPayload)).json());
        assertTrue(created.get("success").getAsBoolean(), created.toString());
        JsonObject createdPayload = created.getAsJsonObject("payload");
        assertTrue(createdPayload.get("native_state_transport").getAsBoolean());
        assertFalse(createdPayload.get("generic_starting_state_capability_promoted").getAsBoolean());
        assertEquals(
                record.get("requested_state_digest").getAsString(),
                createdPayload.get("requested_state_digest").getAsString());

        JsonObject started = response(
                bridge.handle(request("start_full_game", new JsonObject())).json());
        assertTrue(started.get("success").getAsBoolean(), started.toString());

        for (int step = 0; step < 50; step++) {
            JsonObject receipt = response(
                    bridge.handle(request(
                            "get_native_state_restoration_receipt",
                            new JsonObject())).json());
            if (receipt.get("success").getAsBoolean()) {
                JsonObject payload = receipt.getAsJsonObject("payload");
                assertTrue(payload.get("match").getAsBoolean(), payload.toString());
                assertEquals(0, payload.get("mismatch_count").getAsInt());
                assertFalse(payload.get("hidden_identity_emitted").getAsBoolean());
                assertFalse(payload.get("generic_starting_state_capability_promoted").getAsBoolean());
                assertEquals(
                        record.get("requested_state_digest").getAsString(),
                        payload.get("requested_state_digest").getAsString());
                return;
            }

            JsonObject error = receipt.getAsJsonArray("errors").get(0).getAsJsonObject();
            assertEquals("native_state_target_not_reached", error.get("code").getAsString());

            JsonObject legalResponse = response(
                    bridge.handle(request("get_legal_actions", new JsonObject())).json());
            assertTrue(legalResponse.get("success").getAsBoolean(), legalResponse.toString());
            JsonObject legal = legalResponse.getAsJsonObject("payload");
            JsonObject action = transportAction(legal);

            JsonObject submitPayload = new JsonObject();
            submitPayload.add("proposal", genericProposal(
                    "pb03-transport-" + step,
                    legal.get("actor_id").getAsString(),
                    action.get("action_id").getAsString(),
                    action.get("action_type").getAsString()));
            JsonObject submitted = response(
                    bridge.handle(request("submit_action", submitPayload)).json());
            assertTrue(submitted.get("success").getAsBoolean(), submitted.toString());
        }
        throw new AssertionError("PB-03 native-state transport did not reach its frozen checkpoint");
    }

    @Test
    void nativeStateTransportRejectsTamperedRequestedStateDigestBeforeSessionCreation() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        JsonObject record = XmageNativeStateRestorationTest.frozenRecord("WS05-CMD-TAX-2").deepCopy();
        record.addProperty(
                "requested_state_digest",
                "0000000000000000000000000000000000000000000000000000000000000000");

        JsonObject createPayload = new JsonObject();
        createPayload.addProperty("game_id", "pb03-transport-tampered");
        createPayload.addProperty("seed", 424242L);
        createPayload.add("record", record);

        JsonObject rejected = response(
                bridge.handle(request("create_native_state_game", createPayload)).json());
        assertFalse(rejected.get("success").getAsBoolean());
        assertEquals(
                "native_state_digest_mismatch",
                rejected.getAsJsonArray("errors").get(0).getAsJsonObject()
                        .get("code").getAsString());

        JsonObject noSession = response(
                bridge.handle(request("start_full_game", new JsonObject())).json());
        assertFalse(noSession.get("success").getAsBoolean(),
                "digest rejection must occur before any session is created");
    }

    private static JsonObject transportAction(JsonObject legal) {
        String decisionClass = legal.get("decision_class").getAsString();
        String actor = legal.get("actor_id").getAsString();
        JsonArray actions = legal.getAsJsonArray("actions");
        JsonObject match = null;
        for (var element : actions) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type")
                    && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            boolean selected = switch (decisionClass) {
                case "mulligan" -> "keep".equals(optionType);
                case "choose_object" -> action.get("action_id").getAsString()
                        .endsWith(":" + actor);
                case "priority" -> "pass_priority".equals(
                        action.get("action_type").getAsString());
                default -> false;
            };
            if (!selected) {
                continue;
            }
            if (match != null) {
                throw new AssertionError(
                        "ambiguous transport action for decision class " + decisionClass);
            }
            match = action;
        }
        if (match == null) {
            throw new AssertionError(
                    "unsupported transport decision class " + decisionClass + ": " + legal);
        }
        return match;
    }

    private static JsonObject genericProposal(
            String proposalId, String actorId, String actionId, String actionType) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", actionId);
        proposal.addProperty("action_type", actionType);
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "pb03-native-state-transport");
        return proposal;
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

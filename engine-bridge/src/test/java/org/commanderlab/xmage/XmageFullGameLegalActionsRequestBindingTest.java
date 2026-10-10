package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 (SLOT-06 L3, AF01 {@code fail_closed_unsupported_decision}): a
 * {@code get_legal_actions} request that names a game, an actor or a decision
 * class is bound to the exact pending decision on the full-game lane.
 *
 * <p>A mismatch fails closed with a typed error and carries no part of the
 * pending decision. The control shows that the same request with matching fields,
 * or with no fields, still receives the decision. The read changes nothing: the
 * decision identity is the same before and after every rejected request.</p>
 */
class XmageFullGameLegalActionsRequestBindingTest {

    private static final String GAME_ID = "issue662-legal-actions-binding";

    @Test
    void mismatchedRequestFieldsFailClosedWithoutLeakingTheDecision() {
        XmageFullGameJsonlBridge bridge = startedBridge();
        JsonObject pending = ok(bridge, "get_legal_actions", new JsonObject());
        String decisionId = pending.get("decision_id").getAsString();
        String actor = pending.get("actor_id").getAsString();
        String decisionClass = pending.get("decision_class").getAsString();

        assertRejected(bridge, field("decision_class", "wsr22_unsupported_decision_class"),
                "UNSUPPORTED_DECISION_CLASS");
        assertRejected(bridge, field("actor_id", "not-the-pending-actor"), "WRONG_ACTOR");
        assertRejected(bridge, field("game_id", "another-game"), "UNKNOWN_GAME");

        JsonObject matching = field("actor_id", actor);
        matching.addProperty("decision_class", decisionClass);
        matching.addProperty("game_id", GAME_ID);
        JsonObject again = ok(bridge, "get_legal_actions", matching);
        assertEquals(decisionId, again.get("decision_id").getAsString(),
                "rejected reads must not advance or mutate the pending decision");
        assertTrue(again.getAsJsonArray("actions").size() > 0);
    }

    private static void assertRejected(
            XmageFullGameJsonlBridge bridge, JsonObject payload, String code) {
        JsonObject response = response(bridge.handle(request("get_legal_actions", payload)).json());
        assertFalse(response.get("success").getAsBoolean(), "must fail closed for " + payload);
        String message = response.getAsJsonArray("errors").get(0).getAsJsonObject()
                .get("message").getAsString();
        assertTrue(message.startsWith(code), message);
        JsonObject body = response.has("payload") && response.get("payload").isJsonObject()
                ? response.getAsJsonObject("payload") : new JsonObject();
        assertFalse(body.has("actions"), "a rejected read must not carry offered actions");
        assertFalse(body.has("decision"), "a rejected read must not carry the decision");
    }

    private static XmageFullGameJsonlBridge startedBridge() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        ok(bridge, "start_engine", new JsonObject());
        JsonArray handles = new JsonArray();
        for (int seat = 0; seat < 2; seat++) {
            JsonObject deckPayload = new JsonObject();
            deckPayload.add("deck", deck("issue662-" + seat));
            JsonObject imported = ok(bridge, "import_deck", deckPayload);
            handles.add(imported.getAsJsonObject("deck_handle").get("handle_id").getAsString());
        }
        JsonObject create = new JsonObject();
        create.addProperty("game_id", GAME_ID);
        create.add("deck_handles", handles);
        create.addProperty("seed", 6620L);
        create.addProperty("starting_player_seat", 0);
        create.addProperty("starting_life", 40);
        ok(bridge, "create_full_game", create);
        ok(bridge, "start_full_game", new JsonObject());
        return bridge;
    }

    private static JsonObject deck(String deckId) {
        JsonObject deck = new JsonObject();
        deck.addProperty("deck_id", deckId);
        deck.addProperty("deck_hash", "0".repeat(64));
        JsonArray commanders = new JsonArray();
        commanders.add("Isamaru, Hound of Konda");
        deck.add("commander_names", commanders);
        JsonArray mainboard = new JsonArray();
        for (int index = 0; index < 99; index++) {
            mainboard.add("Plains");
        }
        deck.add("mainboard", mainboard);
        deck.add("sideboard", new JsonArray());
        return deck;
    }

    private static JsonObject field(String name, String value) {
        JsonObject payload = new JsonObject();
        payload.addProperty(name, value);
        return payload;
    }

    private static JsonObject ok(XmageFullGameJsonlBridge bridge, String type, JsonObject payload) {
        JsonObject response = response(bridge.handle(request(type, payload)).json());
        assertTrue(response.get("success").getAsBoolean(), type + " failed: " + response);
        return response.getAsJsonObject("payload");
    }

    private static String request(String messageType, JsonObject payload) {
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        request.addProperty("request_id", "issue662-" + messageType);
        request.addProperty("message_type", messageType);
        request.add("payload", payload);
        return request.toString();
    }

    private static JsonObject response(String json) {
        return JsonParser.parseString(json).getAsJsonObject();
    }
}

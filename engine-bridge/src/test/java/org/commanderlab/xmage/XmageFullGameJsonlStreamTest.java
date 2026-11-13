package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayOutputStream;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;

/**
 * Bridge-lean #1264 step 4 (NEUTRAL): the JSONL bridge's response goes to the
 * output without an intermediate string and without the defensive copy of the
 * pending frame, and the bytes on the wire are the same.
 */
class XmageFullGameJsonlStreamTest {

    @AfterEach
    void clearProperty() {
        System.clearProperty(XmageFullGameJsonlBridge.GAMES_PER_JVM_PROPERTY);
    }

    /** What Main wrote before: println of the response text. */
    private static byte[] before(XmageFullGameJsonlBridge.Result result) {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        PrintWriter output = new PrintWriter(bytes, true, StandardCharsets.UTF_8);
        output.println(result.json());
        output.flush();
        return bytes.toByteArray();
    }

    /** What Main writes now. */
    private static byte[] after(XmageFullGameJsonlBridge.Result result) throws java.io.IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        PrintWriter output = new PrintWriter(bytes, true, StandardCharsets.UTF_8);
        XmageJsonStreams.write(result.response(), output);
        output.println();
        output.flush();
        return bytes.toByteArray();
    }

    private static void assertSameBytes(XmageFullGameJsonlBridge.Result result, String what)
            throws java.io.IOException {
        byte[] expected = before(result);
        assertArrayEquals(expected, after(result), what);
        assertTrue(expected.length > 2 && expected[expected.length - 1] == '\n', what);
    }

    private static XmageFullGameJsonlBridge.Result call(
            XmageFullGameJsonlBridge bridge, String type, JsonObject payload) {
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        request.addProperty("request_id", "lean-1264-" + type + "-é <>&😀");
        request.addProperty("message_type", type);
        request.add("payload", payload);
        return bridge.handle(request.toString());
    }

    @Test
    void protocolAndErrorResponsesAreByteIdentical() throws Exception {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        assertSameBytes(bridge.handle("not json"), "invalid_json");
        assertSameBytes(call(bridge, "start_engine", new JsonObject()), "start_engine");
        assertSameBytes(call(bridge, "get_provider_version", new JsonObject()), "provider version");
        assertSameBytes(call(bridge, "get_capabilities", new JsonObject()), "capabilities");
        assertSameBytes(call(bridge, "no_such_message_é \"<", new JsonObject()), "unsupported");
        assertSameBytes(call(bridge, "get_full_game_decision", new JsonObject()), "no session");
        JsonObject wrongVersion = new JsonObject();
        wrongVersion.addProperty("protocol_version", "x <script>");
        wrongVersion.addProperty("request_id", "r\ud83d");
        assertSameBytes(bridge.handle(wrongVersion.toString()), "version mismatch with a lone surrogate");
    }

    @Test
    void liveGameResponsesAreByteIdenticalAndTheSharedFrameEqualsTheCopy() throws Exception {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        assertSameBytes(call(bridge, "start_engine", new JsonObject()), "start_engine");
        JsonArray handles = new JsonArray();
        for (int seat = 0; seat < 2; seat++) {
            JsonObject deckPayload = new JsonObject();
            deckPayload.add("deck", deck("lean-1264-" + seat));
            XmageFullGameJsonlBridge.Result imported = call(bridge, "import_deck", deckPayload);
            assertSameBytes(imported, "import_deck");
            handles.add(JsonParser.parseString(imported.json()).getAsJsonObject().getAsJsonObject("payload")
                    .getAsJsonObject("deck_handle").get("handle_id").getAsString());
        }
        JsonObject create = new JsonObject();
        create.addProperty("game_id", "lean-1264-stream");
        create.add("deck_handles", handles);
        create.addProperty("seed", 6620L);
        create.addProperty("starting_player_seat", 0);
        create.addProperty("starting_life", 40);
        XmageFullGameJsonlBridge.Result created = call(bridge, "create_full_game", create);
        assertSameBytes(created, "create_full_game");
        assertTrue(JsonParser.parseString(created.json()).getAsJsonObject().get("success").getAsBoolean());
        assertSameBytes(call(bridge, "start_full_game", new JsonObject()), "start_full_game");

        XmageFullGameSession session = XmageFullGameHiddenInformationTest.field(
                bridge, "session", XmageFullGameSession.class);
        XmageFullGameDecisionController controller = XmageFullGameHiddenInformationTest.field(
                session, "controller", XmageFullGameDecisionController.class);

        int bridgeSubmits = 0;
        int decisions = 0;
        for (int step = 0; step < 60; step++) {
            XmageFullGameJsonlBridge.Result decision = call(bridge, "get_full_game_decision", new JsonObject());
            assertSameBytes(decision, "get_full_game_decision step " + step);
            JsonObject payload = JsonParser.parseString(decision.json()).getAsJsonObject().getAsJsonObject("payload");
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            decisions++;
            // The engine is parked: the frame in the response is the controller's frame, byte for byte.
            assertEquals(controller.pendingDecision().toString(), payload.get("decision").toString(),
                    "step " + step);
            // Serializing the response left the live frame untouched.
            String frameAfter = controller.pendingDecision().toString();
            assertEquals(frameAfter, payload.get("decision").toString());

            JsonObject pending = payload.getAsJsonObject("decision");
            XmageFullGameJsonlBridge.Result legal = call(bridge, "get_legal_actions", new JsonObject());
            assertSameBytes(legal, "get_legal_actions step " + step);
            assertEquals(frameAfter,
                    JsonParser.parseString(legal.json()).getAsJsonObject().getAsJsonObject("payload")
                            .get("decision").toString());

            JsonObject pass = passPriorityProposal(pending, JsonParser.parseString(legal.json())
                    .getAsJsonObject().getAsJsonObject("payload").getAsJsonArray("actions"));
            if (pass != null) {
                JsonObject submit = new JsonObject();
                submit.add("proposal", pass);
                XmageFullGameJsonlBridge.Result submitted = call(bridge, "submit_action", submit);
                assertSameBytes(submitted, "submit_action step " + step);
                JsonObject response = JsonParser.parseString(submitted.json()).getAsJsonObject();
                assertTrue(response.get("success").getAsBoolean(), submitted.json());
                JsonObject result = response.getAsJsonObject("payload");
                if (!result.get("decision").isJsonNull()) {
                    assertEquals(controller.pendingDecision().toString(), result.get("decision").toString());
                }
                bridgeSubmits++;
            } else {
                XmageFullGameHiddenInformationTest.answerNeutrally(session, pending);
            }
        }
        assertTrue(decisions >= 10, "decisions covered: " + decisions);
        assertTrue(bridgeSubmits >= 3, "submit_action responses covered through the bridge: " + bridgeSubmits);
        assertFalse(call(bridge, "get_full_game_result", new JsonObject()).json().isEmpty());
        assertSameBytes(call(bridge, "get_full_game_result", new JsonObject()), "get_full_game_result");
        assertSameBytes(call(bridge, "shutdown_game", new JsonObject()), "shutdown_game");
    }

    private static JsonObject passPriorityProposal(JsonObject pending, JsonArray actions) {
        if (!"priority".equals(pending.get("decision_class").getAsString())) {
            return null;
        }
        for (JsonElement element : actions) {
            JsonObject candidate = element.getAsJsonObject();
            if ("pass_priority".equals(candidate.get("action_type").getAsString())) {
                JsonObject proposal = new JsonObject();
                proposal.addProperty("proposal_id", "lean-1264-pass");
                proposal.addProperty("actor_id", pending.get("actor_id").getAsString());
                proposal.addProperty("legal_action_id", candidate.get("action_id").getAsString());
                proposal.addProperty("action_type", candidate.get("action_type").getAsString());
                proposal.add("target_ids", new JsonArray());
                proposal.add("selected_modes", new JsonArray());
                JsonObject choices = new JsonObject();
                choices.add("ordering", new JsonArray());
                proposal.add("choices", choices);
                return proposal;
            }
        }
        return null;
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
}

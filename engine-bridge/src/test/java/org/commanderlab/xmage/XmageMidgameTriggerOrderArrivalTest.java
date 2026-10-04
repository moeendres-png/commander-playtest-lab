package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * PILOT_TRIGGER_ORDER on the production midgame lane (#425 section C).
 *
 * <p>The frozen record restores Phyrexian Arena and Mystic Remora (counters
 * {@code {"age": 0}}) at P1's upkeep, where both trigger together and the engine
 * asks P1 to order them before anyone receives priority. Two defects kept the row
 * off the lane:</p>
 * <ul>
 *   <li>a counter map whose only kind has count zero was rejected as a counter
 *       request, although it places no counter;</li>
 *   <li>arrival completion re-ran {@code checkStateAndTriggered} from the bridge
 *       thread while the engine thread was parked inside
 *       {@code GameImpl.checkTriggered} on the ordering decision, which re-entered
 *       it and failed with a concurrent pending decision.</li>
 * </ul>
 */
class XmageMidgameTriggerOrderArrivalTest {

    private static final long SEED = 424242L;

    private record Lane(XmageMidgameJsonlBridge bridge, List<JsonObject> tape) {

        JsonObject call(String messageType, JsonObject payload) {
            JsonObject request = new JsonObject();
            request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
            request.addProperty("request_id", messageType + "-" + tape.size());
            request.addProperty("message_type", messageType);
            if (payload != null) {
                request.add("payload", payload);
                request.add("params", payload);
            }
            XmageMidgameJsonlBridge.Result result = bridge.handle(request.toString());
            JsonObject response = JsonParser.parseString(result.json()).getAsJsonObject();
            tape.add(response);
            return response;
        }

        JsonObject ok(String messageType, JsonObject payload) {
            JsonObject response = call(messageType, payload);
            if (!response.get("success").getAsBoolean()) {
                fail(messageType + " must succeed: " + response.getAsJsonArray("errors"));
            }
            return response.getAsJsonObject("payload");
        }
    }

    private static Path repoRoot() {
        Path candidate = Path.of("").toAbsolutePath();
        while (candidate != null) {
            if (Files.isDirectory(candidate.resolve("qualification/ws47"))) {
                return candidate;
            }
            candidate = candidate.getParent();
        }
        throw new AssertionError("repository root with qualification/ws47 not found");
    }

    private static JsonObject frozenRecord(String fixtureId) {
        try {
            JsonObject materialization = JsonParser.parseString(Files.readString(
                    repoRoot().resolve(
                            "qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json")))
                    .getAsJsonObject();
            for (JsonElement element : materialization.getAsJsonArray("records")) {
                JsonObject record = element.getAsJsonObject();
                if (record.get("fixture_id").getAsString().equals(fixtureId)) {
                    return record;
                }
            }
        } catch (Exception exc) {
            throw new AssertionError(exc);
        }
        throw new AssertionError("frozen record missing: " + fixtureId);
    }

    private static JsonObject createRequest(String fixtureId) {
        JsonObject request = new JsonObject();
        request.addProperty("game_id", "trigger-order-" + fixtureId);
        request.addProperty("plan_id", "trigger-order-" + fixtureId);
        request.addProperty("seed", SEED);
        request.add("requested_starting_state", frozenRecord(fixtureId));
        return request;
    }

    private static JsonObject counters(String kind, JsonElement count) {
        JsonObject counters = new JsonObject();
        counters.add(kind, count);
        return counters;
    }

    @Test
    void aZeroCountPlacesNoCounterAndAnythingElseStaysACounterRequest() {
        assertFalse(XmageNativeStateRestoration.hasNonZeroCounter(new JsonObject()));
        assertFalse(XmageNativeStateRestoration.hasNonZeroCounter(
                counters("age", JsonParser.parseString("0"))));
        assertTrue(XmageNativeStateRestoration.hasNonZeroCounter(
                counters("age", JsonParser.parseString("1"))));
        assertTrue(XmageNativeStateRestoration.hasNonZeroCounter(
                counters("loyalty", JsonParser.parseString("3"))));
        assertTrue(XmageNativeStateRestoration.hasNonZeroCounter(
                counters("age", JsonParser.parseString("-1"))));
        assertTrue(XmageNativeStateRestoration.hasNonZeroCounter(
                counters("age", JsonParser.parseString("\"0\""))));
    }

    /**
     * Loyalty is restored only on a first-turn placement (it must be in place
     * before the first state-based action check); an unrestored counter type on
     * the same planeswalker is still refused before any game exists.
     */
    @Test
    void anUnrestoredCounterOnAPlaneswalkerIsStillRejected() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject record = frozenRecord("PILOT_CHOOSE_ABILITY").deepCopy();
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            if ("obj:jeska".equals(object.get("semantic_id").getAsString())) {
                object.getAsJsonObject("counters").addProperty("charge", 1);
            }
        }
        JsonObject request = createRequest("PILOT_CHOOSE_ABILITY");
        request.add("requested_starting_state", record);
        JsonObject response = lane.call("create_midgame_game", request);
        assertFalse(response.get("success").getAsBoolean());
        String message = response.getAsJsonArray("errors").get(0).getAsJsonObject()
                .get("message").getAsString();
        assertTrue(message.contains("UNSUPPORTED_COUNTERS"), message);
    }

    @Test
    void theOrderingDecisionIsTheCheckpointAndCompletionLeavesItPending() {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        lane.ok("create_midgame_game", createRequest("PILOT_TRIGGER_ORDER"));
        lane.ok("start_midgame_game", null);

        JsonObject ordering = null;
        for (int step = 0; step < 60 && ordering == null; step++) {
            JsonObject pending = pendingDecision(lane);
            if (pending == null) {
                break;
            }
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = pending.get("actor_id").getAsString();
            switch (decisionClass) {
                case "trigger_order" -> ordering = pending;
                case "mulligan" -> submit(lane, pending, actor, optionOfType(pending, "keep"));
                case "choice", "choose_object" ->
                        submit(lane, pending, actor, optionLabelled(pending, "Full Game Seat 1"));
                case "priority" -> submit(lane, pending, actor, optionOfType(pending, "pass_priority"));
                default -> fail("unexpected decision before the checkpoint: " + decisionClass);
            }
        }
        if (ordering == null) {
            fail("the engine never asked P1 to order the simultaneous upkeep triggers");
        }
        assertEquals(2, ordering.getAsJsonArray("legal_options").size());

        JsonObject arrival = lane.ok("complete_midgame_arrival", new JsonObject());
        assertTrue(arrival.get("construction_match").getAsBoolean(),
                "the restored state must read back exactly: " + arrival.get("mismatches"));
        JsonObject observation = arrival.getAsJsonObject("observation");
        assertEquals("BEGINNING", observation.get("phase").getAsString());
        assertEquals("UPKEEP", observation.get("step").getAsString());

        // The completion neither answered nor re-asked the ordering.
        JsonObject still = pendingDecision(lane);
        assertEquals(ordering.get("decision_id").getAsString(),
                still.get("decision_id").getAsString());
        // A second completion is still a pure query.
        lane.ok("complete_midgame_arrival", new JsonObject());
        assertEquals(ordering.get("decision_id").getAsString(),
                pendingDecision(lane).get("decision_id").getAsString());
    }

    private static JsonObject pendingDecision(Lane lane) {
        for (int attempt = 0; attempt < 40; attempt++) {
            JsonObject payload = lane.ok("get_midgame_decision", null);
            if (payload.has("decision") && !payload.get("decision").isJsonNull()) {
                return payload.getAsJsonObject("decision");
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                fail("interrupted while polling the pending decision");
            }
        }
        return null;
    }

    private static String optionOfType(JsonObject pending, String optionType) {
        List<String> matches = new ArrayList<>();
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (optionType.equals(option.get("option_type").getAsString())) {
                matches.add(option.get("option_id").getAsString());
            }
        }
        assertEquals(1, matches.size(), "offered: " + pending.getAsJsonArray("legal_options"));
        return matches.get(0);
    }

    private static String optionLabelled(JsonObject pending, String label) {
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (option.get("label").getAsString().endsWith(label)) {
                return option.get("option_id").getAsString();
            }
        }
        throw new AssertionError("no option labelled " + label);
    }

    private static void submit(Lane lane, JsonObject pending, String actor, String optionId) {
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", pending.get("decision_id").getAsString());
        response.addProperty("actor_id", actor);
        com.google.gson.JsonArray selected = new com.google.gson.JsonArray();
        selected.add(optionId);
        response.add("selected_option_ids", selected);
        response.add("ordering", new com.google.gson.JsonArray());
        JsonObject request = new JsonObject();
        request.add("response", response);
        lane.ok("submit_midgame_decision", request);
    }
}

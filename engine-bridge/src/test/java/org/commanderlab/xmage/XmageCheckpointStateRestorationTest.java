package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Checkpoint state on the mid-game lane: a requested library, tapped state and
 * counters are the state AT the requested checkpoint, and a transforming
 * double-faced card is requested by both face names.
 *
 * <p>The records are the effective successors of the AF07 rows (the frozen
 * base plus the current successor contract's overlay), so a contract change
 * reaches these tests. Arrival completion is queried at every priority before
 * the checkpoint, as the production arrival driver does; that is what used to
 * place the active player's library before its first-turn draw.</p>
 */
class XmageCheckpointStateRestorationTest {

    private static final long SEED = 424242L;

    private record Lane(XmageMidgameJsonlBridge bridge, List<String> responses) {

        JsonObject call(String messageType, JsonObject payload) {
            JsonObject request = new JsonObject();
            request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
            request.addProperty("request_id", messageType + "-" + responses.size());
            request.addProperty("message_type", messageType);
            if (payload != null) {
                request.add("payload", payload);
                request.add("params", payload);
            }
            String json = bridge.handle(request.toString()).json();
            responses.add(json);
            return JsonParser.parseString(json).getAsJsonObject();
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
        Path here = Path.of("").toAbsolutePath();
        for (Path candidate = here; candidate != null; candidate = candidate.getParent()) {
            if (Files.exists(candidate.resolve("qualification/CURRENT_PRE_FREEZE_CONTRACT.json"))) {
                return candidate;
            }
        }
        throw new AssertionError("repository root not found from " + here);
    }

    private static JsonObject json(String relative) {
        try {
            return JsonParser.parseString(Files.readString(repoRoot().resolve(relative))).getAsJsonObject();
        } catch (java.io.IOException exc) {
            throw new AssertionError(exc);
        }
    }

    /** The frozen base record with the current successor contract's replace overlay applied. */
    private static JsonObject effectiveRecord(String fixtureId) {
        JsonObject record = null;
        for (JsonElement element : json("qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json")
                .getAsJsonArray("records")) {
            if (fixtureId.equals(element.getAsJsonObject().get("fixture_id").getAsString())) {
                record = element.getAsJsonObject().deepCopy();
            }
        }
        assertNotNull(record, "base record missing: " + fixtureId);
        JsonObject contract = json(json("qualification/CURRENT_PRE_FREEZE_CONTRACT.json")
                .getAsJsonObject("full107").get("successor_contract").getAsString());
        for (JsonElement element : contract.getAsJsonArray("record_successors")) {
            JsonObject patch = element.getAsJsonObject();
            if (fixtureId.equals(patch.get("fixture_id").getAsString())) {
                for (Map.Entry<String, JsonElement> entry : patch.getAsJsonObject("replace").entrySet()) {
                    record.add(entry.getKey(), entry.getValue().deepCopy());
                }
            }
        }
        return record;
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

    private static String option(JsonObject decision, String optionType) {
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (optionType.equals(option.get("option_type").getAsString())) {
                return option.get("option_id").getAsString();
            }
        }
        fail("no " + optionType + " option in " + decision.get("decision_class"));
        return null;
    }

    private static String labelled(JsonObject decision, String label) {
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (option.get("label").getAsString().endsWith(label)) {
                return option.get("option_id").getAsString();
            }
        }
        fail("no option labelled " + label);
        return null;
    }

    private static void submit(Lane lane, JsonObject decision, String optionId) {
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", decision.get("decision_id").getAsString());
        response.addProperty("actor_id", decision.get("actor_id").getAsString());
        JsonArray selected = new JsonArray();
        selected.add(optionId);
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());
        JsonObject request = new JsonObject();
        request.add("response", response);
        lane.ok("submit_midgame_decision", request);
    }

    /** Drives to the record's precombat-main checkpoint, completing the arrival at every priority. */
    private static JsonObject arrive(String fixtureId) {
        return arrive(fixtureId, new ArrayList<>());
    }

    private static JsonObject arrive(String fixtureId, List<String> earlierArrivals) {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        JsonObject create = new JsonObject();
        create.addProperty("game_id", fixtureId);
        create.addProperty("plan_id", fixtureId);
        create.addProperty("seed", SEED);
        create.add("requested_starting_state", effectiveRecord(fixtureId));
        lane.ok("create_midgame_game", create);
        lane.ok("start_midgame_game", null);
        for (int step = 0; step < 80; step++) {
            JsonObject decision = pendingDecision(lane);
            assertNotNull(decision, "the engine stopped offering decisions before the checkpoint");
            String decisionClass = decision.get("decision_class").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submit(lane, decision, option(decision, "keep"));
            } else if ("choice".equals(decisionClass) || "choose_object".equals(decisionClass)) {
                // The starting-player choice: seat 1, the record's active player.
                submit(lane, decision, labelled(decision, "Full Game Seat 1"));
            } else if ("priority".equals(decisionClass)) {
                JsonObject arrival = lane.ok("complete_midgame_arrival", new JsonObject());
                if ("PRECOMBAT_MAIN".equals(arrival.getAsJsonObject("observation").get("phase").getAsString())) {
                    return arrival;
                }
                earlierArrivals.add(arrival.toString());
                submit(lane, decision, option(decision, "pass_priority"));
            } else {
                fail("unexpected decision during arrival: " + decisionClass);
            }
        }
        fail("the checkpoint was never reached");
        return null;
    }

    private static void assertExact(JsonObject arrival, String kind, int count) {
        assertTrue(arrival.get("construction_match").getAsBoolean(),
                "the checkpoint must construct exactly: " + arrival.getAsJsonArray("mismatches"));
        JsonObject checks = arrival.getAsJsonObject("lossless_hidden_checks");
        assertTrue(checks.has(kind) && checks.get(kind).getAsInt() == count,
                kind + " checks must run " + count + " times: " + checks);
    }

    /**
     * Fail-before: the active player's requested library used to be placed at
     * the first arrival completion (its upkeep), so its first-turn draw took
     * the requested top card and the checkpoint library was incomplete.
     */
    @Test
    void theActivePlayersRequestedLibraryIsTheLibraryAtTheCheckpoint() {
        JsonObject arrival = arrive("CARD_09");
        assertExact(arrival, "library_object", 2);
        assertExact(arrival, "library_order", 1);
    }

    /**
     * Fail-before (found by the AF05 knowledge-projection regression): while
     * the libraries waited for the checkpoint, every earlier arrival response
     * listed each requested library object as "not placed", naming its
     * semantic id to a requester who may not know such a card was requested.
     */
    @Test
    void noArrivalBeforeTheCheckpointNamesARequestedLibraryObject() {
        List<String> earlier = new ArrayList<>();
        assertExact(arrive("CARD_12", earlier), "library_object", 7);
        assertFalse(earlier.isEmpty(), "the arrival must have been completed before the checkpoint");
        for (String response : earlier) {
            assertFalse(response.contains("obj:card12-lib"), "an early arrival named a library object");
            assertTrue(response.contains("the requested checkpoint was not reached"), response);
        }
    }

    /**
     * A requested library object that shares its identity with the template
     * (a Mountain on top of Mountains) holds its own requested position.
     */
    @Test
    void aRequestedLibraryObjectHoldsItsPositionAmongIdenticalTemplateCards() {
        JsonObject arrival = arrive("CARD_12");
        assertExact(arrival, "library_object", 7);
    }

    /** Fail-before: tapped permanents were refused (UNSUPPORTED_TAPPED). */
    @Test
    void requestedTappedPermanentsAreTappedAtTheCheckpoint() {
        JsonObject arrival = arrive("CARD_15");
        assertExact(arrival, "tapped", 5);
    }

    /** Fail-before: counters were refused (UNSUPPORTED_COUNTERS). */
    @Test
    void requestedCountersAreOnTheirPermanentsAtTheCheckpoint() {
        JsonObject arrival = arrive("CARD_28");
        assertExact(arrival, "counters", 2);
    }

    /** Fail-before: "Front // Back" was refused (CARD_IDENTITY_MISMATCH). */
    @Test
    void aTransformingDoubleFacedCardIsRequestedByBothFaceNames() {
        assertEquals("Boseiju Reaches Skyward",
                XmageNativeStateRestoration.canonicalCardIdentity(
                        "Boseiju Reaches Skyward // Branch of Boseiju"));
        assertEquals("Wear // Tear", XmageNativeStateRestoration.canonicalCardIdentity("Wear // Tear"));
        assertEquals("Boseiju Reaches Skyward // Not Its Back",
                XmageNativeStateRestoration.canonicalCardIdentity("Boseiju Reaches Skyward // Not Its Back"));
        JsonObject arrival = arrive("CARD_29");
        assertTrue(arrival.get("construction_match").getAsBoolean(), arrival.toString());
    }

    @Test
    void anUnrestoredCounterTypeStillFailsClosed() {
        assertEquals(mage.counters.CounterType.P1P1, XmageNativeStateRestoration.counterType("+1/+1"));
        assertFalse(XmageNativeStateRestoration.counterType("loyalty") != null);
    }
}

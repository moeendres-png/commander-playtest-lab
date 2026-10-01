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
import java.util.function.Consumer;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * AF05 on the mid-game lane: SLOT-04 lossless HIDDEN construction and the
 * actor-entitled knowledge projection.
 *
 * <p>The records are the effective 1.0.8 successors: the frozen 1.0.5 base
 * record with the successor contract's own {@code replace} overlay applied, so
 * a contract change reaches these tests rather than being shadowed by a local
 * copy. Every card name below is a record identity whose visibility the record
 * itself declares: Demonic Tutor sits in P2's hand, Vampiric Tutor on top of
 * P2's library, Grizzly Bears face down under P1's control.</p>
 */
class XmageMidgameKnowledgeProjectionTest {

    private static final long SEED = 424242L;
    private static final String HAND_SECRET = "Demonic Tutor";
    private static final String LIBRARY_SECRET = "Vampiric Tutor";
    private static final String FACE_DOWN_SECRET = "Grizzly Bears";
    private static final String SENTINEL = "WS30_HONEY_P2_PRIVATE_7F3A";

    private record Lane(XmageMidgameJsonlBridge bridge, List<String> responses) {

        String raw(String messageType, JsonObject payload) {
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
            return json;
        }

        JsonObject ok(String messageType, JsonObject payload) {
            JsonObject response = JsonParser.parseString(raw(messageType, payload)).getAsJsonObject();
            if (!response.get("success").getAsBoolean()) {
                fail(messageType + " must succeed: " + response.getAsJsonArray("errors"));
            }
            return response.getAsJsonObject("payload");
        }

        JsonObject rejected(String messageType, JsonObject payload) {
            JsonObject response = JsonParser.parseString(raw(messageType, payload)).getAsJsonObject();
            if (response.get("success").getAsBoolean()) {
                fail(messageType + " must fail closed, but succeeded");
            }
            return response;
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

    private static JsonObject json(String relative) {
        try {
            return JsonParser.parseString(Files.readString(repoRoot().resolve(relative)))
                    .getAsJsonObject();
        } catch (Exception exc) {
            throw new AssertionError(exc);
        }
    }

    private static JsonObject baseRecord(String fixtureId) {
        JsonObject base = json("qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json");
        for (JsonElement element : base.getAsJsonArray("records")) {
            JsonObject record = element.getAsJsonObject();
            if (fixtureId.equals(record.get("fixture_id").getAsString())) {
                return record.deepCopy();
            }
        }
        throw new AssertionError("base record missing: " + fixtureId);
    }

    /** The base record with the current successor contract's replace overlay applied. */
    private static JsonObject successorRecord(String fixtureId) {
        JsonObject record = baseRecord(fixtureId);
        JsonObject authority = json("qualification/CURRENT_PRE_FREEZE_CONTRACT.json");
        JsonObject contract = json(authority.getAsJsonObject("full107")
                .get("successor_contract").getAsString());
        for (JsonElement element : contract.getAsJsonArray("record_successors")) {
            JsonObject patch = element.getAsJsonObject();
            if (fixtureId.equals(patch.get("fixture_id").getAsString())) {
                for (Map.Entry<String, JsonElement> entry
                        : patch.getAsJsonObject("replace").entrySet()) {
                    record.add(entry.getKey(), entry.getValue().deepCopy());
                }
                return record;
            }
        }
        throw new AssertionError("no successor overlay for " + fixtureId);
    }

    private static JsonObject createRequest(String gameId, JsonObject record) {
        JsonObject request = new JsonObject();
        request.addProperty("game_id", gameId);
        request.addProperty("plan_id", gameId);
        request.addProperty("seed", SEED);
        request.add("requested_starting_state", record);
        return request;
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

    private static String option(JsonObject decision, String optionType, String labelSuffix) {
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            boolean typed = optionType != null
                    && optionType.equals(option.get("option_type").getAsString());
            boolean labelled = labelSuffix != null
                    && option.get("label").getAsString().endsWith(labelSuffix);
            if (typed || labelled) {
                return option.get("option_id").getAsString();
            }
        }
        fail("the engine offered no matching option: " + decision.get("decision_class"));
        return null;
    }

    private static void submit(Lane lane, JsonObject decision, String optionId) {
        assertNotNull(optionId);
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

    /**
     * Drives the arrival to P1's precombat-main priority, handing every frame
     * the engine asks to {@code onFrame} first.
     */
    private static void arrive(Lane lane, Consumer<JsonObject> onFrame) {
        for (int step = 0; step < 80; step++) {
            JsonObject decision = pendingDecision(lane);
            assertNotNull(decision, "the engine stopped offering decisions before the checkpoint");
            onFrame.accept(decision);
            String decisionClass = decision.get("decision_class").getAsString();
            if ("mulligan".equals(decisionClass)) {
                submit(lane, decision, option(decision, "keep", null));
            } else if ("choice".equals(decisionClass) || "choose_object".equals(decisionClass)) {
                submit(lane, decision, option(decision, null, "Full Game Seat 1"));
            } else if ("priority".equals(decisionClass)) {
                JsonObject observation = lane.ok("complete_midgame_arrival", new JsonObject())
                        .getAsJsonObject("observation");
                if ("PRECOMBAT_MAIN".equals(observation.get("phase").getAsString())) {
                    return;
                }
                submit(lane, decision, option(decision, "pass_priority", null));
            } else {
                fail("unexpected decision during arrival: " + decisionClass);
            }
        }
        fail("the checkpoint was never reached");
    }

    private static JsonObject actorRequest(String actor) {
        JsonObject request = new JsonObject();
        if (actor != null) {
            request.addProperty("actor_id", actor);
        }
        return request;
    }

    private static Lane arrivedLane(String gameId, Consumer<JsonObject> onFrame) {
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        lane.ok("create_midgame_game", createRequest(gameId, successorRecord("HIDDEN_04")));
        lane.ok("start_midgame_game", null);
        arrive(lane, onFrame);
        return lane;
    }

    @Test
    void theLosslessSuccessorConstructsExactlyAndCountsEveryCheckWithoutNamingIt() {
        Lane lane = arrivedLane("kp-exact", frame -> { });
        for (String requester : new String[]{"P1", null}) {
            String raw = lane.raw("complete_midgame_arrival", actorRequest(requester));
            JsonObject payload = JsonParser.parseString(raw).getAsJsonObject()
                    .getAsJsonObject("payload");
            assertTrue(payload.get("construction_match").getAsBoolean(),
                    "the lossless successor must construct exactly: "
                            + payload.getAsJsonArray("mismatches"));
            assertEquals(0, payload.getAsJsonArray("mismatches").size());
            JsonObject checks = payload.getAsJsonObject("lossless_hidden_checks");
            assertEquals(1, checks.get("library_order").getAsInt());
            assertEquals(1, checks.get("library_object").getAsInt());
            assertEquals(4, checks.get("hand_composition").getAsInt());
            assertEquals(1, checks.get("face_down").getAsInt());
            // Counts only: the observation names no object whose state the
            // requester may not know was requested, and no hidden identity.
            for (String forbidden : List.of("obj:hidden-lib-0", "obj:hidden-hand",
                    HAND_SECRET, LIBRARY_SECRET, SENTINEL)) {
                assertFalse(raw.contains(forbidden), requester + " arrival names " + forbidden);
            }
        }
    }

    /**
     * Fail-before for the pre-start face-down: turned face down at the first
     * priority, the permanent sat face up through the mulligans and every
     * opponent's mulligan frame named it.
     */
    @Test
    void noOpponentFrameEverNamesTheFaceDownPermanent() {
        List<String> opponentFrames = new ArrayList<>();
        List<String> controllerFrames = new ArrayList<>();
        String[] p1 = new String[1];
        arrivedLane("kp-face-down", frame -> {
            int seat = frame.get("seat").getAsInt();
            if (seat == 0) {
                p1[0] = frame.get("actor_id").getAsString();
                controllerFrames.add(frame.toString());
            } else {
                opponentFrames.add(frame.toString());
            }
        });
        assertFalse(opponentFrames.isEmpty(), "the opponents' mulligan frames must be observed");
        for (String frame : opponentFrames) {
            assertFalse(frame.contains(FACE_DOWN_SECRET),
                    "an opponent's frame named the face-down permanent: " + frame);
        }
        // The controller is entitled, from the very first frame on.
        assertTrue(controllerFrames.get(0).contains("\"private_identity\":\"" + FACE_DOWN_SECRET + "\""),
                "the controller must see its face-down permanent from the first frame");
        assertNotNull(p1[0]);
    }

    @Test
    void everyPrincipalReceivesExactlyItsEntitledProjection() {
        Lane lane = arrivedLane("kp-projection", frame -> { });
        for (String label : List.of("P1", "P2", "P3", "P4")) {
            String raw = lane.raw("get_midgame_projection", actorRequest(label));
            JsonObject payload = JsonParser.parseString(raw).getAsJsonObject()
                    .getAsJsonObject("payload");
            assertEquals(label, payload.get("actor_id").getAsString());
            assertEquals("principal_scoped", payload.get("observation_scope").getAsString());
            JsonArray seatLabels = payload.getAsJsonArray("seat_labels");
            assertEquals("[\"P1\",\"P2\",\"P3\",\"P4\"]", seatLabels.toString());
            // Nobody, the owner included, may see a library card.
            assertFalse(raw.contains(LIBRARY_SECRET), label + " sees a library card");
            assertFalse(raw.contains(SENTINEL), label + " received the honey sentinel");
            assertEquals("P2".equals(label), raw.contains(HAND_SECRET),
                    "only P2 may see its own hand card");
            assertEquals("P1".equals(label), raw.contains(FACE_DOWN_SECRET),
                    "only P1 may see its own face-down permanent");
            JsonObject view = payload.getAsJsonObject("view");
            for (JsonElement element : view.getAsJsonArray("players")) {
                JsonObject player = element.getAsJsonObject();
                String playerLabel = seatLabels.get(player.get("seat").getAsInt()).getAsString();
                assertEquals(playerLabel.equals(label), player.has("hand"),
                        "a hand array only for the requester");
                if ("P2".equals(playerLabel)) {
                    assertEquals(8, player.get("hand_count").getAsInt());
                    assertEquals(93, player.get("library_count").getAsInt());
                    assertEquals(1, player.get("exile_count").getAsInt());
                    assertTrue(player.getAsJsonArray("exile").toString().contains("Sol Ring"),
                            "face-up exile is public to " + label);
                }
            }
        }
    }

    @Test
    void theProjectionHasNoUnscopedVariant() {
        Lane lane = arrivedLane("kp-refusals", frame -> { });
        for (String requester : new String[]{null, "*", "ALL", "P9", "op-1"}) {
            JsonObject response = lane.rejected("get_midgame_projection", actorRequest(requester));
            assertEquals("midgame_projection_failed", response.getAsJsonArray("errors")
                    .get(0).getAsJsonObject().get("code").getAsString());
            assertFalse(response.toString().contains(HAND_SECRET));
            assertFalse(response.toString().contains(FACE_DOWN_SECRET));
        }
        JsonObject capabilities = lane.ok("get_capabilities", null).getAsJsonObject("capabilities");
        assertTrue(capabilities.get("knowledge_projection_supported").getAsBoolean());
        assertFalse(capabilities.get("omniscient_state_api").getAsBoolean());
        assertFalse(capabilities.get("raw_engine_object_graph_api").getAsBoolean());
        assertEquals("principal_scoped_required_requester", capabilities
                .getAsJsonObject("observation_scopes").get("get_midgame_projection").getAsString());
    }

    @Test
    void theUntypedOrPartialPredecessorStillFailsClosed() {
        // The 1.0.5 predecessor: untyped face_down=true and a partial library.
        Lane lane = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>());
        String predecessor = lane.rejected("create_midgame_game",
                createRequest("kp-legacy", baseRecord("HIDDEN_04"))).toString();
        assertFalse(predecessor.contains(FACE_DOWN_SECRET));

        JsonObject partial = successorRecord("HIDDEN_04");
        for (JsonElement element : partial.getAsJsonArray("deck_state")) {
            element.getAsJsonObject().remove("checkpoint_library");
        }
        String partialError = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>())
                .rejected("create_midgame_game", createRequest("kp-partial", partial)).toString();
        assertTrue(partialError.contains("PARTIAL_LIBRARY_REQUEST"), partialError);
        assertFalse(partialError.contains(LIBRARY_SECRET));

        JsonObject manual = successorRecord("HIDDEN_04");
        for (JsonElement element : manual.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            if (object.has("face_down_type")) {
                object.addProperty("face_down_type", "MANUAL");
            }
        }
        String manualError = new Lane(new XmageMidgameJsonlBridge(), new ArrayList<>())
                .rejected("create_midgame_game", createRequest("kp-manual", manual)).toString();
        assertTrue(manualError.contains("INVALID_FACE_DOWN_TYPE"), manualError);
        assertFalse(manualError.contains(FACE_DOWN_SECRET));
    }
}

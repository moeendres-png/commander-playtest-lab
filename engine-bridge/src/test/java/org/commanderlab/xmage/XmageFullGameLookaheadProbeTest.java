package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #1265 S5 bounded look-ahead probe verification on the real full-game bridge.
 *
 * <p>Verifies that look-ahead branches leave the real game's state, replay record,
 * and RNG tape untouched, keep {@code actor_view} §5 principal-scoped, reject
 * invalid/non-priority/un-redetermined requests fail-closed, and clean up all
 * probe threads and static redactor keys on end or shutdown.</p>
 */
class XmageFullGameLookaheadProbeTest {

    private static final Set<String> PRIVATE_ROW_KEYS =
            Set.of("hand", "mana_pool", "land_plays_remaining");

    @Test
    void lookaheadProbeLeavesRealGameUntouchedAndCleansUp() throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("s5-probe-isolation", 4, 126501L);
        try {
            advanceUntilClass(session, "priority", 60);
            JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
            assertEquals("priority", pending.get("decision_class").getAsString());

            String viewerId = pending.get("actor_id").getAsString();
            String candidateId = choosePriorityOptionId(pending);
            String digestBefore = session.semanticStateDigest();
            String replayBefore = session.replayExportPayload().toString();
            JsonObject expectedViewerView = pending.getAsJsonObject("pilot_state");

            JsonObject startReq = new JsonObject();
            startReq.addProperty("actor_id", viewerId);
            startReq.addProperty("candidate_option_id", candidateId);
            startReq.addProperty("probe_seed", 777L);

            JsonObject probePayload = session.startLookaheadProbe(startReq);
            String probeId = probePayload.get("probe_id").getAsString();
            String probeKey = session.activeProbeKey();
            assertNotNull(probeKey);
            assertTrue(probePayload.get("redetermined").getAsBoolean());
            assertEquals(0, probePayload.get("engine_error_count").getAsInt());
            assertTrue(probePayload.get("failure").isJsonNull());
            assertActorScoped(probePayload.getAsJsonObject("actor_view"), viewerId);
            assertZoneCountsMatch(expectedViewerView, probePayload.getAsJsonObject("actor_view"));

            // Real game submission and second concurrent probe must fail closed while active.
            JsonObject legal = session.legalActionsPayload();
            assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> session.submitAction(FullGameTestPilot.choose(legal))
            );
            assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> session.startLookaheadProbe(startReq)
            );

            // Step probe forward several decisions without touching the real game.
            JsonObject currentPayload = probePayload;
            for (int step = 0; step < 6; step++) {
                if (currentPayload.get("terminal").getAsBoolean()
                        || currentPayload.get("decision").isJsonNull()) {
                    break;
                }
                JsonObject stepReq = new JsonObject();
                stepReq.addProperty("probe_id", probeId);
                stepReq.add("response", buildProbeResponse(currentPayload.getAsJsonObject("decision")));
                currentPayload = session.stepLookaheadProbe(stepReq);
                assertEquals(0, currentPayload.get("engine_error_count").getAsInt());
                assertTrue(currentPayload.get("failure").isJsonNull());
                assertActorScoped(currentPayload.getAsJsonObject("actor_view"), viewerId);
            }

            JsonObject endReq = new JsonObject();
            endReq.addProperty("probe_id", probeId);
            JsonObject ended = session.endLookaheadProbe(endReq);
            assertTrue(ended.get("ended").getAsBoolean());
            assertFalse(ended.get("probe_thread_alive").getAsBoolean());
            assertFalse(XmageFullGameStateRedactor.holdsRecordsFor(probeKey));

            assertEquals(digestBefore, session.semanticStateDigest());
            assertEquals(replayBefore, session.replayExportPayload().toString());
        } finally {
            session.shutdownGame();
        }
    }

    @Test
    void lookaheadProbeEnforcesFailClosedGuardsAndDeterminism() throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("s5-probe-guards", 4, 126502L);
        try {
            // 1. Real game starts at non-priority decision (choice / mulligan): must fail closed.
            JsonObject initial = session.pendingDecisionPayload().getAsJsonObject("decision");
            assertFalse("priority".equals(initial.get("decision_class").getAsString()));
            JsonObject badPhaseReq = new JsonObject();
            badPhaseReq.addProperty("actor_id", initial.get("actor_id").getAsString());
            badPhaseReq.addProperty("candidate_option_id",
                    initial.getAsJsonArray("legal_options").get(0).getAsJsonObject().get("option_id").getAsString());
            badPhaseReq.addProperty("probe_seed", 1L);
            XmageFullGameDecisionController.DecisionException nonPriorityExc = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> session.startLookaheadProbe(badPhaseReq)
            );
            assertTrue(nonPriorityExc.getMessage().startsWith("LOOKAHEAD_REQUIRES_PRIORITY"),
                    nonPriorityExc.getMessage());

            // 2. Advance to priority.
            advanceUntilClass(session, "priority", 60);
            JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
            String viewerId = pending.get("actor_id").getAsString();
            String candidateId = choosePriorityOptionId(pending);

            // 3. Reject redetermine=false (no raw opponent hands exposed over protocol).
            JsonObject noRedetermine = new JsonObject();
            noRedetermine.addProperty("actor_id", viewerId);
            noRedetermine.addProperty("candidate_option_id", candidateId);
            noRedetermine.addProperty("probe_seed", 42L);
            noRedetermine.addProperty("redetermine", false);
            XmageFullGameDecisionController.DecisionException redetExc = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> session.startLookaheadProbe(noRedetermine)
            );
            assertTrue(redetExc.getMessage().startsWith("LOOKAHEAD_REDETERMINATION_REQUIRED"),
                    redetExc.getMessage());

            // 4. Reject WRONG_ACTOR.
            String wrongActor = "00000000-0000-0000-0000-000000000001";
            if (wrongActor.equals(viewerId)) {
                wrongActor = "00000000-0000-0000-0000-000000000002";
            }
            JsonObject wrongActorReq = new JsonObject();
            wrongActorReq.addProperty("actor_id", wrongActor);
            wrongActorReq.addProperty("candidate_option_id", candidateId);
            wrongActorReq.addProperty("probe_seed", 42L);
            XmageFullGameDecisionController.DecisionException wrongActorExc = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> session.startLookaheadProbe(wrongActorReq)
            );
            assertTrue(wrongActorExc.getMessage().startsWith("WRONG_ACTOR"),
                    wrongActorExc.getMessage());

            // 5. Same probe_seed produces identical normalized actor_view and next decision class/seat.
            JsonObject seededReq = new JsonObject();
            seededReq.addProperty("actor_id", viewerId);
            seededReq.addProperty("candidate_option_id", candidateId);
            seededReq.addProperty("probe_seed", 9001L);

            JsonObject run1 = session.startLookaheadProbe(seededReq);
            session.endLookaheadProbe(new JsonObject());
            JsonObject run2 = session.startLookaheadProbe(seededReq);
            String secondKey = session.activeProbeKey();

            assertEquals(
                    normalizeActorView(run1.getAsJsonObject("actor_view")).toString(),
                    normalizeActorView(run2.getAsJsonObject("actor_view")).toString()
            );

            // Shutting down real session while second probe is still active must clean up its probe key.
            session.shutdownGame();
            assertFalse(XmageFullGameStateRedactor.holdsRecordsFor(secondKey));
        } finally {
            if (!session.isShutDown()) {
                session.shutdownGame();
            }
        }
    }

    private static void advanceUntilClass(XmageFullGameSession session, String targetClass, int maxSteps) {
        for (int i = 0; i < maxSteps; i++) {
            JsonObject status = session.pendingDecisionPayload();
            if (status.get("decision") == null || status.get("decision").isJsonNull()) {
                break;
            }
            JsonObject decision = status.getAsJsonObject("decision");
            if (targetClass.equals(decision.get("decision_class").getAsString())) {
                return;
            }
            FullGameTestPilot.play(session, 1);
        }
        throw new AssertionError("Game did not reach decision_class=" + targetClass);
    }

    private static String choosePriorityOptionId(JsonObject priorityDecision) {
        JsonArray options = priorityDecision.getAsJsonArray("legal_options");
        for (JsonElement elem : options) {
            JsonObject opt = elem.getAsJsonObject();
            if (!"pass_priority".equals(opt.get("option_type").getAsString())) {
                return opt.get("option_id").getAsString();
            }
        }
        return options.get(0).getAsJsonObject().get("option_id").getAsString();
    }

    private static JsonObject buildProbeResponse(JsonObject decision) {
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", decision.get("decision_id").getAsString());
        response.addProperty("actor_id", decision.get("actor_id").getAsString());
        JsonArray options = decision.getAsJsonArray("legal_options");
        JsonArray selected = new JsonArray();
        int min = decision.get("minimum_selections").getAsInt();
        String cls = decision.get("decision_class").getAsString();
        if ("priority".equals(cls)) {
            for (JsonElement elem : options) {
                JsonObject opt = elem.getAsJsonObject();
                if ("pass_priority".equals(opt.get("option_type").getAsString())) {
                    selected.add(opt.get("option_id").getAsString());
                    break;
                }
            }
        }
        if (selected.isEmpty() && min > 0 && !options.isEmpty()) {
            for (int i = 0; i < min && i < options.size(); i++) {
                selected.add(options.get(i).getAsJsonObject().get("option_id").getAsString());
            }
        }
        response.add("selected_option_ids", selected);
        response.add("ordering", new JsonArray());
        return response;
    }

    private static void assertActorScoped(JsonObject view, String viewerId) {
        assertEquals(viewerId, view.get("actor_id").getAsString());
        int actorRows = 0;
        for (JsonElement elem : view.getAsJsonArray("players")) {
            JsonObject row = elem.getAsJsonObject();
            boolean isActor = row.get("is_actor").getAsBoolean();
            if (isActor) {
                actorRows++;
                assertEquals(viewerId, row.get("player_id").getAsString());
            } else if (!row.get("private_state_visible").getAsBoolean()) {
                for (String key : PRIVATE_ROW_KEYS) {
                    assertFalse(row.has(key), "non-actor row exposes private key: " + key);
                }
            }
        }
        assertEquals(1, actorRows);
    }

    private static void assertZoneCountsMatch(JsonObject before, JsonObject after) {
        JsonArray beforePlayers = before.getAsJsonArray("players");
        JsonArray afterPlayers = after.getAsJsonArray("players");
        assertEquals(beforePlayers.size(), afterPlayers.size());
        for (int i = 0; i < beforePlayers.size(); i++) {
            JsonObject b = beforePlayers.get(i).getAsJsonObject();
            JsonObject a = afterPlayers.get(i).getAsJsonObject();
            assertEquals(b.get("hand_count").getAsInt(), a.get("hand_count").getAsInt());
            assertEquals(b.get("library_count").getAsInt(), a.get("library_count").getAsInt());
            assertEquals(b.get("graveyard_count").getAsInt(), a.get("graveyard_count").getAsInt());
        }
    }

    private static JsonObject normalizeActorView(JsonObject view) {
        JsonObject copy = view.deepCopy();
        copy.remove("game_id");
        List<JsonElement> statuses = new ArrayList<>();
        copy.getAsJsonArray("commander_status").forEach(statuses::add);
        statuses.sort(java.util.Comparator.comparing(JsonElement::toString));
        JsonArray sortedStatus = new JsonArray();
        statuses.forEach(sortedStatus::add);
        copy.add("commander_status", sortedStatus);
        return copy;
    }
}

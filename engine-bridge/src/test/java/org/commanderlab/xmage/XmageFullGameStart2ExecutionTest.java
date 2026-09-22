package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * FULL107 Phase C execution: WS05-CMD-START-2 fixture run (execution
 * evidence only; no mapping promotion in this workstream).
 *
 * <p><b>BLOCKED — disabled by design.</b> The pinned engine's
 * CommanderFreeForAll hardcodes {@code startingPlayerSkipsDraw = false},
 * so P1 draws on turn 1 (hand 8 at the draw step) against the frozen
 * {@code first_turn_draw:false} requirement. Enabling the skip via the
 * engine TurnMod path removes the draw-step priority entirely, leaving
 * the requested temporal point (turn 1, beginning/draw, priority P1)
 * unobservable — so the fixture is unsatisfiable as specified on this
 * engine either way. See BLOCKER record in the workstream docs. Enable
 * this test only after engine draw-skip semantics plus fixture temporal
 * expectations are adjudicated and implemented.</p>
 */
class XmageFullGameStart2ExecutionTest {

    static final List<String> events = new ArrayList<>();

    static String[] temporalStrings(String phaseName, String stepName) {
        if (phaseName.equals("PRECOMBAT_MAIN") && stepName.equals("PRECOMBAT_MAIN")) {
            return new String[]{"precombat_main", "main"};
        }
        if (phaseName.equals("BEGINNING") && stepName.equals("UPKEEP")) {
            return new String[]{"beginning", "upkeep"};
        }
        if (phaseName.equals("BEGINNING") && stepName.equals("DRAW")) {
            return new String[]{"beginning", "draw"};
        }
        throw new AssertionError("unsupported temporal point for digest: "
                + phaseName + "/" + stepName);
    }

    @Test
    @org.junit.jupiter.api.Disabled("BLOCKED: pinned engine draws on turn 1 "
            + "(CommanderFreeForAll hardcodes startingPlayerSkipsDraw=false); "
            + "enabling the TurnMod skip removes the draw-step priority, "
            + "leaving the requested temporal unobservable. See workstream "
            + "BLOCKER record for the S1/S2 analysis and authority questions.")
    void start2DrawStepObservedWithNoDraw() {
        events.clear();
        JsonObject requested = XmageDigestCreditTest.frozenRecord("WS05-CMD-START-2");
        long seed = XmageDigestCreditTest.manifestSeed("WS05-CMD-START-2");
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        requested, "exec-start2", seed);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(
                        importer, plan, "exec-start2");
        XmageFullGameSession session = new XmageFullGameSession(
                "WS05-CMD-START-2", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        Player p1 = seats.get("P1");

        boolean atDraw = false;
        boolean upkeepSeen = false;
        for (int step = 0; step < 40; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            if (readback.get("turn_number").getAsInt() == 1
                    && readback.get("phase").getAsString().equals("BEGINNING")
                    && readback.get("step").getAsString().equals("UPKEEP")) {
                for (JsonElement element : readback.getAsJsonArray("seats")) {
                    JsonObject seat = element.getAsJsonObject();
                    if (seat.get("player_id").getAsString().equals("P1")) {
                        assertEquals(7, seat.get("hand_count").getAsInt(),
                                "P1 hand must still be opening seven at upkeep");
                        upkeepSeen = true;
                    }
                }
            }
            if (readback.get("turn_number").getAsInt() == 1
                    && readback.get("phase").getAsString().equals("BEGINNING")
                    && readback.get("step").getAsString().equals("DRAW")) {
                atDraw = true;
                break;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before draw step");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            if ("mulligan".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, "exec-start2-keep-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "mulligan", "keep"));
            } else if ("choose_object".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, "exec-start2-start-" + step,
                        XmageFullGameTaxExecutionTest.singleSelfAction(legal, actorId));
            } else if ("priority".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, "exec-start2-pass-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "pass_priority", null));
            } else {
                fail("unexpected decision class en route to draw step: " + decisionClass);
            }
        }
        assertTrue(atDraw, "engine must park priority at the turn-1 draw step");
        restoration.restoreCommanderCasts(session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        assertTrue(restoration.compare(observed, seats).match(),
                "construction must match before observation");

        assertEquals("P1", observed.get("active_player").getAsString(),
                "starting_player:P1");
        events.add("starting_player:P1");
        assertEquals("P1", observed.get("priority_player").getAsString());
        JsonObject p1Seat = null;
        for (JsonElement element : observed.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            if (seat.get("player_id").getAsString().equals("P1")) {
                p1Seat = seat;
            }
        }
        assertTrue(p1Seat != null, "P1 seat observed");
        assertEquals(7, p1Seat.get("hand_count").getAsInt(),
                "first_turn_draw:false — P1 hand unchanged through the draw step");
        assertEquals(92, p1Seat.get("library_count").getAsInt());
        events.add("first_turn_draw:false");

        List<String> seatPids = new ArrayList<>(seats.keySet());
        JsonObject projected = new JsonObject();
        projected.addProperty("execution_entry_mode", "NATIVE_STATE_LOAD");
        projected.add("players", XmageDigestCreditTest.playersProjection(
                plan.players(), observed, 40, requested));
        assertFalse(requested.has("deck_state"), "START-2 carries no deck_state");
        projected.add("commander_state", XmageDigestCreditTest.commanderStateProjection(
                requested, observed, plan));
        projected.add("semantic_objects",
                XmageDigestCreditTest.transferBattlefieldIds(requested, observed));
        String[] phaseStep = temporalStrings(
                observed.get("phase").getAsString(), observed.get("step").getAsString());
        JsonObject temporalOut = new JsonObject();
        temporalOut.addProperty("active_player", observed.get("active_player").getAsString());
        temporalOut.add("extra_turn_queue", new JsonArray());
        temporalOut.addProperty("phase", phaseStep[0]);
        temporalOut.addProperty("priority_player",
                observed.get("priority_player").getAsString());
        temporalOut.addProperty("step", phaseStep[1]);
        temporalOut.addProperty("turn_number", 1);
        JsonObject temporal = requested.getAsJsonObject("temporal_state");
        assertEquals(temporal.get("active_player").getAsString(),
                temporalOut.get("active_player").getAsString());
        assertEquals(temporal.get("priority_player").getAsString(),
                temporalOut.get("priority_player").getAsString());
        assertEquals(temporal.get("phase").getAsString(), phaseStep[0]);
        assertEquals(temporal.get("step").getAsString(), phaseStep[1]);
        projected.add("temporal_state", temporalOut);
        projected.add("knowledge_state", XmageDigestCreditTest.knowledgeProjection(requested,
                seatPids, Set.of("Rograkh, Son of Rohgahh", "Grizzly Bears", "Mountain"),
                Set.of()));
        projected.add("rules_randomness", requested.get("rules_randomness"));
        assertEquals(seed, observed.get("rules_seed").getAsLong());
        assertTrue(observed.get("rules_seed_explicit").getAsBoolean());
        assertTrue(session.restorationGame().getStack().isEmpty());
        projected.add("stack_state", new JsonArray());
        assertFalse(requested.has("combat_state"), "combat state unsupported in v1");
        projected.add("setup_validation", requested.get("setup_validation"));
        XmageDigestCreditTest.assertProjectionKeys(projected, requested);
        assertEquals(requested.get("requested_state_digest").getAsString(),
                XmageNativeStateRestoration.constructedDigest(projected),
                "construction digest must equal frozen hex");
        assertTrue(events.contains("starting_player:P1"));
        assertTrue(events.contains("first_turn_draw:false"));
    }
}

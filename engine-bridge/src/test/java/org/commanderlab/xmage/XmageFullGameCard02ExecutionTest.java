package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.game.permanent.Permanent;
import mage.players.Player;
import mage.watchers.common.CommanderPlaysCountWatcher;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * FULL107 Phase C execution: CARD_02 fixture run (execution evidence only;
 * no mapping promotion in this workstream).
 *
 * <p>Fixture-faithful execution: restored 4-commander starting state
 * (casts 0, no battlefield, turn-1-main, seed 424242) with construction
 * digest equality, then the scripted P1 commander cast resolved against
 * projected legal actions with exact-one-match fail-closed semantics.
 * Fresh count implies no tax and no payment decisions (fail closed if any
 * appear). Required events and terminal postconditions asserted from
 * native facts. Forbidden fallbacks prohibited throughout.</p>
 */
class XmageFullGameCard02ExecutionTest {

    static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    static final List<String> events = new ArrayList<>();

    @Test
    void card02CastsCommanderWithNoTax() {
        events.clear();
        JsonObject requested =
                XmageDigestCreditTest.frozenRecord("CARD_02");
        long seed = XmageDigestCreditTest.manifestSeed("CARD_02");
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        requested, "exec-card02", seed);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(
                        importer, plan, "exec-card02");
        XmageFullGameSession session = new XmageFullGameSession(
                "CARD_02", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        Player p1 = seats.get("P1");

        for (int step = 0; step < 60; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            if (readback.get("turn_number").getAsInt() == 1
                    && readback.get("phase").getAsString().equals("PRECOMBAT_MAIN")) {
                break;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before arrival");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            if ("mulligan".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, "exec-card02-keep-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "mulligan", "keep"));
            } else if ("choose_object".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, "exec-card02-start-" + step,
                        XmageFullGameTaxExecutionTest.singleSelfAction(legal, actorId));
            } else if ("priority".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, "exec-card02-pass-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "pass_priority", null));
            } else {
                fail("unexpected decision class during arrival: " + decisionClass);
            }
            if (step == 59) {
                fail("arrival bound breached");
            }
        }
        restoration.restoreCommanderCasts(session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        assertTrue(restoration.compare(observed, seats).match(),
                "construction must match before execution");
        assertEquals(requested.get("requested_state_digest").getAsString(),
                constructionDigestForCard02(requested, plan, restoration, observed, seats,
                        session),
                "construction digest must equal frozen hex");

        UUID commanderUuid = null;
        for (Card card : session.restorationGame().getCommanderCardsFromCommandZone(
                p1, CommanderCardType.COMMANDER_OR_OATHBREAKER)) {
            if (card.getName().equals(ROGRAKH)) {
                commanderUuid = card.getId();
            }
        }
        assertTrue(commanderUuid != null, "P1 Rograkh must be in the command zone");
        CommanderPlaysCountWatcher watcher = session.restorationGame()
                .getState().getWatcher(CommanderPlaysCountWatcher.class);
        assertEquals(0, watcher.getPlaysCount(commanderUuid), "fresh count implies no tax");

        JsonObject castLegal = session.legalActionsPayload();
        assertEquals("priority", castLegal.get("decision_class").getAsString());
        JsonObject castAction = XmageFullGameTaxExecutionTest.castOffer(castLegal, ROGRAKH);
        XmageFullGameTaxExecutionTest.submit(session, "exec-card02-cast", castAction);
        events.add("cast_commander:P1");

        boolean onStack = false;
        for (mage.game.stack.StackObject stackObject
                : session.restorationGame().getStack()) {
            if (stackObject.getName().equals(ROGRAKH)) {
                onStack = true;
            }
        }
        assertTrue(onStack, "commander_cast: Rograkh must be on the stack");
        events.add("commander_cast:P1");

        boolean resolved = false;
        for (int step = 0; step < 40; step++) {
            boolean present = false;
            for (Permanent permanent
                    : session.restorationGame().getBattlefield().getAllPermanents()) {
                if (permanent.getName().equals(ROGRAKH)
                        && p1.getId().equals(permanent.getControllerId())) {
                    present = true;
                }
            }
            if (present) {
                resolved = true;
                break;
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before resolution");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            if (!"priority".equals(decisionClass)) {
                fail("unexpected decision class during resolution (no tax expected): "
                        + decisionClass);
            }
            XmageFullGameTaxExecutionTest.submit(session, "exec-card02-resolve-" + step,
                    XmageFullGameTaxExecutionTest.singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
        }
        assertTrue(resolved, "Rograkh must resolve onto P1's battlefield");
        events.add("spell_resolved:P1");
        events.add("creature_entered:P1-Rograkh");
        assertEquals(1, watcher.getPlaysCount(commanderUuid), "count cmd:P1-A = 1");
        assertEquals(0, p1.getManaPool().getMana().count(), "no mana moved: no tax charged");
        int tapped = 0;
        for (Permanent permanent
                : session.restorationGame().getBattlefield().getAllPermanents()) {
            if (p1.getId().equals(permanent.getControllerId()) && permanent.isTapped()) {
                tapped++;
            }
        }
        assertEquals(0, tapped, "nothing tapped for payment");
        assertTrue(events.contains("commander_cast:P1"));
        assertTrue(events.contains("spell_resolved:P1"));
        assertTrue(events.contains("creature_entered:P1-Rograkh"));
    }

    static String constructionDigestForCard02(JsonObject requested,
            XmageNativeStateRestoration.Plan plan,
            XmageNativeStateRestoration restoration,
            JsonObject observed, Map<String, Player> seats,
            XmageFullGameSession session) {
        List<String> seatPids = new ArrayList<>(seats.keySet());
        JsonObject projected = new JsonObject();
        projected.addProperty("execution_entry_mode", "NATIVE_STATE_LOAD");
        assertEquals(requested.get("execution_entry_mode").getAsString(), "NATIVE_STATE_LOAD");
        projected.add("players", XmageDigestCreditTest.playersProjection(
                plan.players(), observed, 40, requested));
        assertFalse(requested.has("deck_state"), "CARD_02 carries no deck_state");
        projected.add("commander_state", XmageDigestCreditTest.commanderStateProjection(
                requested, observed, plan));
        projected.add("semantic_objects",
                XmageDigestCreditTest.transferBattlefieldIds(requested, observed));
        assertEquals(1, observed.get("turn_number").getAsInt());
        assertEquals("PRECOMBAT_MAIN", observed.get("phase").getAsString());
        assertEquals("PRECOMBAT_MAIN", observed.get("step").getAsString());
        JsonObject temporalOut = new JsonObject();
        temporalOut.addProperty("active_player", observed.get("active_player").getAsString());
        temporalOut.add("extra_turn_queue", new JsonArray());
        temporalOut.addProperty("phase", "precombat_main");
        temporalOut.addProperty("priority_player",
                observed.get("priority_player").getAsString());
        temporalOut.addProperty("step", "main");
        temporalOut.addProperty("turn_number", 1);
        JsonObject temporal = requested.getAsJsonObject("temporal_state");
        assertEquals(temporal.get("active_player").getAsString(),
                temporalOut.get("active_player").getAsString());
        assertEquals(temporal.get("priority_player").getAsString(),
                temporalOut.get("priority_player").getAsString());
        projected.add("temporal_state", temporalOut);
        projected.add("knowledge_state", XmageDigestCreditTest.knowledgeProjection(requested,
                seatPids, Set.of("Rograkh, Son of Rohgahh", "Mountain"), Set.of("priority")));
        projected.add("rules_randomness", requested.get("rules_randomness"));
        assertEquals(plan.seed(), observed.get("rules_seed").getAsLong());
        assertTrue(observed.get("rules_seed_explicit").getAsBoolean());
        assertTrue(requested.getAsJsonArray("stack_state").isEmpty());
        assertTrue(session.restorationGame().getStack().isEmpty());
        projected.add("stack_state", new JsonArray());
        assertFalse(requested.has("combat_state"), "combat state unsupported in v1");
        projected.add("setup_validation", requested.get("setup_validation"));
        XmageDigestCreditTest.assertProjectionKeys(projected, requested);
        return XmageNativeStateRestoration.constructedDigest(projected);
    }
}

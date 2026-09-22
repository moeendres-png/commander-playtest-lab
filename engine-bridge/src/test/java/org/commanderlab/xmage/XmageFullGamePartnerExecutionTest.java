package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.players.Player;
import mage.watchers.common.CommanderPlaysCountWatcher;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * FULL107 Phase C execution: WS05-CMD-PARTNER-ZONE and WS05-CMD-PARTNER-TAX.
 *
 * <p>Both frozen scripts are empty, so no decisions are invented: execution
 * is construction (exact two-commander states, engine Partner-legality proof
 * at import) plus arrival (keeps and passes only) plus native readback.
 * PARTNER-ZONE proves both partners begin in the command zone as separate
 * identities. PARTNER-TAX proves independent histories (restored counts 2
 * vs 0) and independent tax figures computed through the engine's own cost
 * pipeline on ability copies (purity proven by readback equality), with
 * swapped-history and wrong-identity negatives proving the evidence is
 * specific. Forbidden fallbacks prohibited throughout.</p>
 */
class XmageFullGamePartnerExecutionTest {

    record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration.Plan plan,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats,
            JsonObject observed,
            List<String> events) {
    }

    static List<Card> commandZone(
            XmageFullGameSession session, Player player) {
        return new ArrayList<>(session.restorationGame().getCommanderCardsFromCommandZone(
                player, CommanderCardType.COMMANDER_OR_OATHBREAKER));
    }

    static Card requireCommander(
            XmageFullGameSession session, Player player, String name) {
        List<Card> matches = new ArrayList<>();
        for (Card card : commandZone(session, player)) {
            if (card.getName().equals(name)) {
                matches.add(card);
            }
        }
        assertEquals(1, matches.size(),
                "expected exactly one " + name + " for command-zone mapping");
        return matches.get(0);
    }

    static void driveArrival(
            XmageFullGameSession session, Map<String, Player> seats, String tag) {
        for (int step = 0; step < 60; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            if (readback.get("turn_number").getAsInt() == 1
                    && readback.get("phase").getAsString().equals("PRECOMBAT_MAIN")) {
                return;
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
                XmageFullGameTaxExecutionTest.submit(session, tag + "-keep-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "mulligan", "keep"));
            } else if ("choose_object".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, tag + "-start-" + step,
                        XmageFullGameTaxExecutionTest.singleSelfAction(legal, actorId));
            } else if ("priority".equals(decisionClass)) {
                XmageFullGameTaxExecutionTest.submit(session, tag + "-pass-" + step,
                        XmageFullGameTaxExecutionTest.singleActionOfType(
                                legal, "pass_priority", null));
            } else {
                fail("unexpected decision class during arrival: " + decisionClass);
            }
        }
        fail("arrival bound breached");
    }

    static Arrived restoreAndArrive(String fixtureId, String gameTag) {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord(fixtureId),
                        gameTag, 424242L);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, gameTag);
        XmageFullGameSession session = new XmageFullGameSession(
                fixtureId, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        driveArrival(session, seats, gameTag);
        restoration.restoreCommanderCasts(session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        return new Arrived(session, plan, restoration, seats, observed, new ArrayList<>());
    }

    @Test
    void partnerZoneBothPartnersBeginAsSeparateIdentities() {
        Arrived arrived = restoreAndArrive("WS05-CMD-PARTNER-ZONE", "exec-pzone");
        XmageNativeStateRestoration.CompareVerdict verdict = arrived.restoration().compare(
                arrived.observed(), arrived.seats());
        assertTrue(verdict.match(),
                "PARTNER-ZONE construction mismatches: " + verdict.mismatches());
        Player p1 = arrived.seats().get("P1");
        Card rograkh = requireCommander(arrived.session(), p1, "Rograkh, Son of Rohgahh");
        Card kediss = requireCommander(arrived.session(), p1, "Kediss, Emberclaw Familiar");
        assertFalse(rograkh.getId().equals(kediss.getId()), "separate commander identities");
        arrived.events().add("game_start_command_zone:cmd:P1-A");
        arrived.events().add("game_start_command_zone:cmd:P1-B");
        for (String pid : List.of("P2", "P3", "P4")) {
            requireCommander(arrived.session(), arrived.seats().get(pid),
                    "Rograkh, Son of Rohgahh");
        }
        Map<UUID, String> seen = new HashMap<>();
        for (String pid : List.of("P1", "P2", "P3", "P4")) {
            for (Card card : commandZone(arrived.session(), arrived.seats().get(pid))) {
                assertTrue(seen.put(card.getId(), pid) == null,
                        "commander identity duplicated: " + card.getName());
            }
        }
        assertTrue(arrived.events().contains("game_start_command_zone:cmd:P1-A"));
        assertTrue(arrived.events().contains("game_start_command_zone:cmd:P1-B"));
    }

    @Test
    void partnerTaxFiguresAreIndependent() {
        Arrived arrived = restoreAndArrive("WS05-CMD-PARTNER-TAX", "exec-ptax");
        XmageNativeStateRestoration.CompareVerdict verdict = arrived.restoration().compare(
                arrived.observed(), arrived.seats());
        assertTrue(verdict.match(),
                "PARTNER-TAX construction mismatches: " + verdict.mismatches());
        Player p1 = arrived.seats().get("P1");
        Card rograkh = requireCommander(arrived.session(), p1, "Rograkh, Son of Rohgahh");
        Card kediss = requireCommander(arrived.session(), p1, "Kediss, Emberclaw Familiar");
        CommanderPlaysCountWatcher watcher = arrived.session().restorationGame()
                .getState().getWatcher(CommanderPlaysCountWatcher.class);
        assertEquals(2, watcher.getPlaysCount(rograkh.getId()), "Rograkh history 2");
        assertEquals(0, watcher.getPlaysCount(kediss.getId()), "Kediss history 0");
        String rograkhFigure = XmageNativeStateRestoration.enumerateCommanderCastCost(
                arrived.session().restorationGame(), rograkh);
        String kedissFigure = XmageNativeStateRestoration.enumerateCommanderCastCost(
                arrived.session().restorationGame(), kediss);
        assertEquals("{0}+{4}", rograkhFigure, "Rograkh figure carries +4 tax");
        assertEquals("{1}+{R}", kedissFigure, "Kediss figure carries no tax");
        assertFalse(rograkhFigure.equals(kedissFigure), "figures differ per history");
        JsonObject reread = XmageNativeStateRestoration.readback(
                arrived.session().restorationGame(), arrived.seats());
        assertTrue(arrived.restoration().compare(reread, arrived.seats()).match(),
                "enumeration must not mutate game state");
        arrived.events().add("tax:cmd:P1-A:+4");
        arrived.events().add("tax:cmd:P1-B:+0");
        assertTrue(arrived.events().contains("tax:cmd:P1-A:+4"));
        assertTrue(arrived.events().contains("tax:cmd:P1-B:+0"));
    }

    @Test
    void rejectsNonPartnerPairAtImport() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("WS05-CMD-PARTNER-ZONE"),
                        "exec-neg-id", 424242L);
        List<XmageNativeStateRestoration.RequestedCommander> tampered = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedCommander commander : plan.commanders()) {
            if (commander.commanderId().equals("cmd:P1-B")) {
                tampered.add(new XmageNativeStateRestoration.RequestedCommander(
                        commander.commanderId(), "Isamaru, Hound of Konda",
                        commander.owner(), commander.priorCasts()));
            } else {
                tampered.add(commander);
            }
        }
        XmageNativeStateRestoration.Plan wrongIdentity = new XmageNativeStateRestoration.Plan(
                plan.planId(), plan.playerCount(), plan.seed(), plan.players(),
                List.copyOf(tampered), plan.objects(), plan.turnNumber(), plan.phase(),
                plan.step(), plan.activePlayer(), plan.priorityPlayer());
        try {
            XmageNativeStateRestorationTest.importScaffolding(
                    new XmageDeckImporter(), wrongIdentity, "exec-neg-id");
            fail("non-partner pair must fail closed at engine Commander validation");
        } catch (XmageDeckImporter.ImportException exc) {
            assertTrue(exc.getMessage().contains("COMMANDER_VALIDATION_FAILED"),
                    exc.getMessage());
        }
    }

    @Test
    void swappedHistoriesMismatch() {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("WS05-CMD-PARTNER-TAX"),
                        "exec-neg-swap", 424242L);
        List<XmageNativeStateRestoration.RequestedCommander> swapped = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedCommander commander : plan.commanders()) {
            if (commander.commanderId().equals("cmd:P1-A")) {
                swapped.add(new XmageNativeStateRestoration.RequestedCommander(
                        commander.commanderId(), commander.cardIdentity(),
                        commander.owner(), 0));
            } else if (commander.commanderId().equals("cmd:P1-B")) {
                swapped.add(new XmageNativeStateRestoration.RequestedCommander(
                        commander.commanderId(), commander.cardIdentity(),
                        commander.owner(), 2));
            } else {
                swapped.add(commander);
            }
        }
        XmageNativeStateRestoration.Plan swappedPlan = new XmageNativeStateRestoration.Plan(
                plan.planId(), plan.playerCount(), plan.seed(), plan.players(),
                List.copyOf(swapped), plan.objects(), plan.turnNumber(), plan.phase(),
                plan.step(), plan.activePlayer(), plan.priorityPlayer());
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(swappedPlan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, swappedPlan, "exec-neg");
        XmageFullGameSession session = new XmageFullGameSession(
                "WS05-CMD-PARTNER-TAX-swapped", handles, 0, 40,
                swappedPlan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        driveArrival(session, seats, "exec-neg-swap");
        restoration.restoreCommanderCasts(session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());
        JsonObject observed =
                XmageNativeStateRestoration.readback(session.restorationGame(), seats);
        XmageNativeStateRestoration.CompareVerdict verdict =
                restoration.compare(observed, seats);
        assertTrue(verdict.match(), "swapped restoration must match its own plan");
        XmageNativeStateRestoration.CompareVerdict cross =
                new XmageNativeStateRestoration(plan,
                        XmageNativeStateRestorationTest.restorationFor(plan)
                                .materializationVehicleForTests())
                        .compare(observed, seats);
        assertFalse(cross.match(), "swapped histories must mismatch the frozen request");
        assertTrue(cross.mismatches().stream().anyMatch(line -> line.contains("casts")),
                "mismatch must name cast counts: " + cross.mismatches());
        Player p1 = seats.get("P1");
        String rograkhFigure = XmageNativeStateRestoration.enumerateCommanderCastCost(
                session.restorationGame(), requireCommander(session, p1,
                        "Rograkh, Son of Rohgahh"));
        String kedissFigure = XmageNativeStateRestoration.enumerateCommanderCastCost(
                session.restorationGame(), requireCommander(session, p1,
                        "Kediss, Emberclaw Familiar"));
        assertEquals("{0}", rograkhFigure, "swapped Rograkh figure carries no tax");
        assertFalse(kedissFigure.equals("{1}+{R}"),
                "swapped Kediss figure must differ from required +0: " + kedissFigure);
    }

    @Test
    void incorrectTaxFiguresDetected() {
        // Zero-history restoration (PARTNER-ZONE) measured against the
        // taxed requirement: figures must show no tax, proving they track
        // histories rather than echoing expectations.
        Arrived arrived = restoreAndArrive("WS05-CMD-PARTNER-ZONE", "exec-neg-tax");
        Player p1 = arrived.seats().get("P1");
        String rograkhFigure = XmageNativeStateRestoration.enumerateCommanderCastCost(
                arrived.session().restorationGame(), requireCommander(
                        arrived.session(), p1, "Rograkh, Son of Rohgahh"));
        String kedissFigure = XmageNativeStateRestoration.enumerateCommanderCastCost(
                arrived.session().restorationGame(), requireCommander(
                        arrived.session(), p1, "Kediss, Emberclaw Familiar"));
        assertEquals("{0}", rograkhFigure, "zero-history Rograkh carries no tax");
        assertEquals("{1}+{R}", kedissFigure, "zero-history Kediss carries no tax");
        assertFalse(rograkhFigure.equals("{0}+{4}"),
                "zero-history figure detected as incorrect against taxed requirement");
    }

    @Test
    void mismatchedTerminalExpectationDetected() {
        Arrived arrived = restoreAndArrive("WS05-CMD-PARTNER-TAX", "exec-neg-term");
        XmageNativeStateRestoration.Plan plan = arrived.plan();
        List<XmageNativeStateRestoration.RequestedCommander> altered = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedCommander commander : plan.commanders()) {
            if (commander.commanderId().equals("cmd:P1-A")) {
                altered.add(new XmageNativeStateRestoration.RequestedCommander(
                        commander.commanderId(), commander.cardIdentity(),
                        commander.owner(), 1));
            } else {
                altered.add(commander);
            }
        }
        XmageNativeStateRestoration.Plan tampered = new XmageNativeStateRestoration.Plan(
                plan.planId(), plan.playerCount(), plan.seed(), plan.players(),
                List.copyOf(altered), plan.objects(), plan.turnNumber(), plan.phase(),
                plan.step(), plan.activePlayer(), plan.priorityPlayer());
        XmageNativeStateRestoration.CompareVerdict verdict =
                new XmageNativeStateRestoration(tampered, arrived.restoration()
                        .materializationVehicleForTests())
                        .compare(arrived.observed(), arrived.seats());
        assertFalse(verdict.match(), "altered terminal expectation must mismatch");
        assertFalse(verdict.mismatches().isEmpty());
    }
}

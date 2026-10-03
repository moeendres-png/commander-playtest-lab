package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.constants.Zone;
import mage.counters.CounterType;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The restoration's first-turn setup (CR 103.6a): restored permanents enter
 * when the first turn begins as new objects, the setup itself never reaches the
 * public event tape, and control history is verified rather than assumed.
 */
class XmageFirstTurnSetupTest {

    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats) {
    }

    private static XmageNativeStateRestoration.Plan plan(
            String planId, Map<String, Boolean> controlledSinceTurnBegan) {
        return new XmageNativeStateRestoration.Plan(
                planId, 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(),
                List.of(new XmageNativeStateRestoration.RequestedObject(
                                "obj:p1-narset", "Narset, Parter of Veils", "P1", "P1",
                                Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:p1-bears", "Grizzly Bears", "P1", "P1", Zone.BATTLEFIELD, false),
                        new XmageNativeStateRestoration.RequestedObject(
                                "obj:p2-elves", "Llanowar Elves", "P2", "P2", Zone.BATTLEFIELD, false)),
                1, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, "P1", "P1",
                Map.of(), controlledSinceTurnBegan);
    }

    /** P2's commander requested on the battlefield; P1 takes the first turn. */
    private static XmageNativeStateRestoration.Plan commanderPlan(
            String planId, Map<String, Boolean> controlledSinceTurnBegan) {
        return commanderPlan(planId, "Rograkh, Son of Rohgahh", "P1", controlledSinceTurnBegan);
    }

    /** Both commanders requested on the battlefield; {@code active} takes the first turn. */
    private static XmageNativeStateRestoration.Plan commanderPlan(
            String planId, String p1Commander, String active,
            Map<String, Boolean> controlledSinceTurnBegan) {
        return new XmageNativeStateRestoration.Plan(
                planId, 2, 424242L,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", p1Commander, "P1", 0,
                                Zone.BATTLEFIELD, "obj:p1-commander"),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0,
                                Zone.BATTLEFIELD, "obj:p2-commander")),
                List.of(),
                List.of(),
                1, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, active, active,
                Map.of(), controlledSinceTurnBegan);
    }

    private static Arrived arrive(XmageNativeStateRestoration.Plan plan) {
        return arrive(plan, 0);
    }

    /** {@code startingSeat} is the seat the bridge starts with (its starting_player_seat). */
    private static Arrived arrive(XmageNativeStateRestoration.Plan plan, int startingSeat) {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, plan.planId());
        XmageFullGameSession session = new XmageFullGameSession(
                plan.planId(), handles, startingSeat, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Arrived(session, restoration, seats);
    }

    private static Permanent permanent(Arrived arrived, String semanticId) {
        Permanent permanent = arrived.session().restorationGame()
                .getPermanent(arrived.restoration().injectedObjectId(semanticId));
        assertNotNull(permanent, semanticId + " must be on the battlefield");
        return permanent;
    }

    @Test
    void theSetupPlacementNeverReachesThePublicTape() {
        Arrived arrived = arrive(plan("setup-tape", Map.of()));
        // The planeswalker entered with its loyalty, as an entering planeswalker
        // does (CR 306.5b) ...
        assertEquals(5, permanent(arrived, "obj:p1-narset").getCounters(
                arrived.session().restorationGame()).getCount(CounterType.LOYALTY));
        // ... but those counters are setup: the public tape, which a pre-start
        // placement never reached either, carries no counter event for them.
        XmagePublicEventWatcher tape = arrived.session().restorationGame()
                .getState().getWatcher(XmagePublicEventWatcher.class);
        for (JsonObject event : tape.eventsAfter(0)) {
            assertFalse("COUNTER_ADDED".equals(event.get("type").getAsString()),
                    "setup counter reached the public tape: " + event);
        }
    }

    @Test
    void onlyTheFirstActivePlayersPermanentsAreControlledSinceTheTurnBegan() {
        Arrived arrived = arrive(plan("setup-sickness", Map.of()));
        // CR 302.6: P1's turn began with its restored creature on the battlefield;
        // P2 has had no turn, so its restored creature is still summoning sick.
        assertTrue(permanent(arrived, "obj:p1-bears").wasControlledFromStartOfControllerTurn());
        assertFalse(permanent(arrived, "obj:p2-elves").wasControlledFromStartOfControllerTurn());
    }

    @Test
    void aRequestedControlHistoryIsVerifiedNeverSet() {
        Arrived arrived = arrive(plan("setup-history", Map.of(
                "obj:p1-bears", true,
                "obj:p2-elves", true)));
        XmageLosslessHiddenPlan.Verification verification = arrived.restoration()
                .losslessHiddenVerification(arrived.session().restorationGame(), arrived.seats());
        assertTrue(verification.checks().contains("controlled_since_turn_began:obj:p1-bears"));
        assertEquals(List.of("controlled_since_turn_began obj:p2-elves: requested true observed false"),
                verification.mismatches());
        assertFalse(permanent(arrived, "obj:p2-elves").wasControlledFromStartOfControllerTurn(),
                "the request never sets the history");
    }

    @Test
    void aBattlefieldCommanderLeavesTheCommandZoneWhenTheFirstTurnBegins() {
        Arrived arrived = arrive(commanderPlan("setup-commander", Map.of()));
        Permanent p1 = permanent(arrived, "obj:p1-commander");
        Permanent p2 = permanent(arrived, "obj:p2-commander");
        // The genuine commanders, not setup copies ...
        assertTrue(arrived.session().restorationGame()
                .getCommandersIds(arrived.seats().get("P1"),
                        mage.constants.CommanderCardType.ANY, false).contains(p1.getId()));
        assertTrue(arrived.session().restorationGame()
                .getCommandersIds(arrived.seats().get("P2"),
                        mage.constants.CommanderCardType.ANY, false).contains(p2.getId()));
        // ... that entered as new objects when the first turn began (CR 302.6):
        // the first active player's is controlled since its turn began; P2 has
        // had no turn, so its commander is not.
        assertTrue(p1.wasControlledFromStartOfControllerTurn());
        assertFalse(p2.wasControlledFromStartOfControllerTurn());
        XmageFirstTurnSetupWatcher setup = arrived.session().restorationGame()
                .getState().getWatcher(XmageFirstTurnSetupWatcher.class);
        assertTrue(setup.placedIds().containsAll(List.of(p1.getId(), p2.getId())));
    }

    @Test
    void aBattlefieldCommandersControlHistoryIsVerifiedNeverSet() {
        Arrived arrived = arrive(commanderPlan("setup-commander-history", Map.of(
                "obj:p1-commander", true,
                "obj:p2-commander", true)));
        XmageLosslessHiddenPlan.Verification verification = arrived.restoration()
                .losslessHiddenVerification(arrived.session().restorationGame(), arrived.seats());
        assertEquals(List.of("controlled_since_turn_began obj:p2-commander: requested true observed false"),
                verification.mismatches());
    }

    @Test
    void theCommandObjectLeavesTheCommandZone() {
        Arrived arrived = arrive(commanderPlan("setup-command-zone", Map.of()));
        UUID p1 = permanent(arrived, "obj:p1-commander").getId();
        UUID p2 = permanent(arrived, "obj:p2-commander").getId();
        for (mage.game.command.CommandObject object
                : arrived.session().restorationGame().getState().getCommand()) {
            assertFalse(object.getId().equals(p1) || object.getId().equals(p2),
                    "a placed commander is still a command object: " + object.getName());
        }
    }

    @Test
    void onP2sFirstTurnP1sBattlefieldCommanderIsNotControlledSinceItsTurnBegan() {
        // The MICRO_COSTS shape (CR 302.6): P2 takes turn 1, P1 has had no turn.
        Arrived arrived = arrive(commanderPlan("setup-micro-costs", "Rograkh, Son of Rohgahh", "P2",
                Map.of("obj:p1-commander", false, "obj:p2-commander", true)), 1);
        assertFalse(permanent(arrived, "obj:p1-commander").wasControlledFromStartOfControllerTurn());
        assertTrue(permanent(arrived, "obj:p2-commander").wasControlledFromStartOfControllerTurn());
        XmageLosslessHiddenPlan.Verification verification = arrived.restoration()
                .losslessHiddenVerification(arrived.session().restorationGame(), arrived.seats());
        assertTrue(verification.checks().containsAll(List.of(
                "controlled_since_turn_began:obj:p1-commander",
                "controlled_since_turn_began:obj:p2-commander")));
        assertEquals(List.of(), verification.mismatches());
    }

    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings = {
            "Esika, God of the Tree",   // modal double-faced
            "Kytheon, Hero of Akros"})  // transforming double-faced
    void aDoubleFacedBattlefieldCommanderIsRefusedBeforeGameStart(String commander) {
        XmageNativeStateRestoration.Plan plan =
                commanderPlan("setup-dfc-" + commander.length(), commander, "P1", Map.of());
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, plan.planId());
        // Refused while the restoration is applied, before the game starts.
        RuntimeException refused = org.junit.jupiter.api.Assertions.assertThrows(
                RuntimeException.class, () -> new XmageFullGameSession(
                        plan.planId(), handles, 0, 40, plan.seed(), importer, restoration).start());
        Throwable cause = refused;
        while (cause != null && !(cause instanceof XmageNativeStateRestoration.RestorationException)) {
            cause = cause.getCause();
        }
        assertNotNull(cause, "expected a coded restoration refusal, got " + refused);
        assertTrue(cause.getMessage().contains("UNSUPPORTED_COMMANDER_FACE"), cause.getMessage());
    }
}

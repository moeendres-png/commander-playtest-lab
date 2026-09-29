package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.stack.StackObject;
import mage.players.Player;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * CR 603.3b / 101.4 (APNAP) with actual cards at 3–6 players on the
 * full-game lane.
 *
 * <p>Every seat controls one Sulfuric Vortex (Oracle: "At the beginning of
 * each player's upkeep, this enchantment deals 2 damage to that player.").
 * At the next player's upkeep, one trigger per controller goes on the stack
 * at once. CR 603.3b: each player, in APNAP order, puts the triggered
 * abilities they control on the stack. CR 101.4: APNAP is the active player,
 * then the other players in turn order. So the new active player's trigger is
 * at the bottom and the trigger of the player just before them in turn order
 * is on top and resolves first. The restored active seat varies, so the
 * turn-order wrap past the last seat is exercised, not only seat 1.</p>
 */
class XmageMultiplayerApnapTriggerTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    private static final String VORTEX = "Sulfuric Vortex";

    @ParameterizedTest(name = "{0} players, restored active {1}")
    @CsvSource({"3, P1", "4, P1", "4, P3", "5, P3", "5, P5", "6, P4"})
    void eachUpkeepTriggersAreStackedInApnapOrder(int playerCount, String restoredActive) {
        String tag = "apnap-" + playerCount + "p-" + restoredActive;
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", ROGRAKH, pid, 0));
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-" + pid + "-0-SulfuricVortex", VORTEX, pid, pid,
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, playerCount, 424242L, List.copyOf(players), List.copyOf(commanders),
                List.copyOf(objects), 1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                PhaseStep.PRECOMBAT_MAIN, restoredActive, restoredActive);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : players) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck(tag + "-" + player.playerId(),
                    tag + "-hash", mainboard, List.of(ROGRAKH)).deckHandle());
        }
        int activeSeat = Integer.parseInt(restoredActive.substring(1));
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, activeSeat - 1, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        Game game = session.restorationGame();
        assertEquals(seats.get(restoredActive).getId(), game.getActivePlayerId(),
                "restored active seat");
        // Arrival drives the restored turn through its beginning phase with
        // the Vortexes already in play, so the restored active player has
        // taken their own upkeep's triggers (restoration finding F-15).
        // Measure this upkeep against the post-arrival baseline.
        Map<String, Integer> baseline = new LinkedHashMap<>();
        seats.forEach((pid, player) -> baseline.put(pid, player.getLife()));
        assertEquals(40 - 2 * playerCount, baseline.get(restoredActive),
                "F-15: arrival upkeep resolved one Vortex trigger per seat");

        // The engine seats counterclockwise: turns (and priority) pass in
        // descending seat order, wrapping from P1 to PN (the documented live
        // topology, see XmagePb03Tier2StackTest). APNAP must follow that same
        // turn order: new active player first, the restored active player
        // (the one just before them in turn order) last, hence on top.
        String nextActive = "P" + (activeSeat == 1 ? playerCount : activeSeat - 1);
        List<String> expectedTopToBottom = new ArrayList<>();
        for (int offset = 0; offset < playerCount; offset++) {
            expectedTopToBottom.add("P" + ((activeSeat - 1 + offset) % playerCount + 1));
        }
        List<String> turnsSeen = new ArrayList<>();

        List<String> observedTopToBottom = null;
        Map<Integer, String> topBySize = new LinkedHashMap<>();
        for (int step = 0; step < 200; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("engine terminal before the upkeep triggers resolved");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String cls = pending.get("decision_class").getAsString();
            if ("choose_object".equals(cls) && game.getStep().getType() == PhaseStep.CLEANUP) {
                // Discard to hand size; every hand holds only Mountains.
                XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(session, seats, restoration),
                        tag + "-discard-" + step, "Mountain",
                        Math.max(1, pending.get("minimum_selections").getAsInt()));
                continue;
            }
            if (!"priority".equals(cls)) {
                fail("unexpected decision " + cls + " at " + game.getStep().getType());
            }
            String activeNow = pidOf(seats, game.getActivePlayerId());
            if (turnsSeen.isEmpty() || !turnsSeen.get(turnsSeen.size() - 1).equals(activeNow)) {
                turnsSeen.add(activeNow);
            }
            boolean nextUpkeep = seats.get(nextActive).getId().equals(game.getActivePlayerId())
                    && game.getStep().getType() == PhaseStep.UPKEEP;
            if (nextUpkeep && observedTopToBottom == null) {
                observedTopToBottom = controllers(game, seats);
            }
            if (nextUpkeep && !game.getStack().isEmpty()) {
                topBySize.putIfAbsent(game.getStack().size(),
                        pidOf(seats, game.getStack().getFirstOrNull().getControllerId()));
            }
            if (observedTopToBottom != null && game.getStack().isEmpty()) {
                break;
            }
            XmageFullGameTaxExecutionTest.submit(session, tag + "-pass-" + step,
                    XmageNativeStateRestorationTest.singleActionOfType(
                            session.legalActionsPayload(), "pass_priority", null));
        }

        assertEquals(List.of(restoredActive, nextActive), turnsSeen,
                "the turn passes to the next seat in the engine's turn order");
        assertNotNull(observedTopToBottom, "never reached " + nextActive + "'s upkeep");
        assertEquals(expectedTopToBottom, observedTopToBottom,
                "CR 603.3b: triggers stacked in APNAP order from " + nextActive);
        List<String> resolvedOrder = new ArrayList<>();
        for (int size = playerCount; size >= 1; size--) {
            resolvedOrder.add(topBySize.get(size));
        }
        assertEquals(expectedTopToBottom, resolvedOrder,
                "the triggers resolve last-in first-out");
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            int expected = baseline.get(entry.getKey())
                    - (entry.getKey().equals(nextActive) ? 2 * playerCount : 0);
            assertEquals(expected, entry.getValue().getLife(),
                    "each Vortex damages only the player whose upkeep it is: " + entry.getKey());
        }
    }

    private static List<String> controllers(Game game, Map<String, Player> seats) {
        List<String> out = new ArrayList<>();
        for (StackObject object : game.getStack()) {
            assertEquals(VORTEX, game.getObject(object.getSourceId()).getName(),
                    "only Vortex triggers are expected on the stack");
            out.add(pidOf(seats, object.getControllerId()));
        }
        return out;
    }

    private static String pidOf(Map<String, Player> seats, UUID id) {
        return XmageNativeStateRestorationTest.pidOf(seats, id.toString());
    }
}

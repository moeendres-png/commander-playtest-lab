package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Extra turns given to other players at 4P and 5P on the full-game lane.
 *
 * <p>Time Warp (Oracle): "Target player takes an extra turn after this one."
 * CR 500.7: extra turns are added directly after the specified turn, and the
 * most recently created turn is taken first. After them, the turn order
 * resumes with the player who would have been next (P2).</p>
 *
 * <ul>
 *   <li>P1 gives P3 an extra turn, then P2: turns P1, P2 (extra), P3 (extra),
 *       then P2 again in normal order.</li>
 *   <li>P1 gives P3 an extra turn and P3 concedes before it: a player who left
 *       the game takes no turns (800.4a), so the next turns are P2 then the seat
 *       after P3.</li>
 * </ul>
 */
class XmageMultiplayerExtraTurnOrderTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void theMostRecentlyCreatedExtraTurnIsTakenFirst(int playerCount) {
        XmageMultiplayerScenario s = start("warp-order-" + playerCount + "p", playerCount, 2);
        warp(s, "Seat 3");
        warp(s, "Seat 2");
        List<String> turns = turnsAfter(s, 4);
        assertEquals(List.of("P1", "P2", "P3", "P2"), turns,
                "500.7: P2's extra turn (created last) first, then P3's, then normal order from P2");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aPlayerWhoLeftTakesNoExtraTurn(int playerCount) {
        XmageMultiplayerScenario s = start("warp-leave-" + playerCount + "p", playerCount, 1);
        warp(s, "Seat 3");
        String id = s.seats.get("P3").getId().toString();
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", "P3-concede");
        concede.addProperty("actor_id", id);
        concede.addProperty("player_id", id);
        assertTrue(s.session.submitConcede(concede).get("failure").isJsonNull());
        assertFalse(s.seats.get("P3").isInGame(), "P3 left the game");
        List<String> turns = turnsAfter(s, 3);
        assertEquals(List.of("P1", "P2", "P4"), turns, "800.4a: the departed P3 takes neither its extra nor its normal turn");
    }

    private static XmageMultiplayerScenario start(String tag, int playerCount, int warps) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int i = 0; i < warps; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Time Warp", i, Zone.HAND));
        }
        for (int i = 0; i < 10; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", 10 + i, Zone.BATTLEFIELD));
        }
        return XmageMultiplayerScenario.start(tag, playerCount, "P1", objects);
    }

    /** P1 casts one Time Warp at {@code seat} and passes until it has resolved. */
    private static void warp(XmageMultiplayerScenario s, String seat) {
        Game game = s.session.restorationGame();
        int inHand = count(s, "Time Warp");
        s.submit(s.action("activate_ability", "Cast Time Warp"));
        for (int i = 0; i < 60; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            if ("priority".equals(cls) && "P1".equals(actor) && game.getStack().isEmpty()
                    && count(s, "Time Warp") < inHand) {
                return;
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Island");
                case "target" -> s.submit(pick(s, seat));
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail("Time Warp at " + seat + " did not resolve");
    }

    private static int count(XmageMultiplayerScenario s, String name) {
        return (int) s.seats.get("P1").getHand().getCards(s.session.restorationGame()).stream()
                .filter(card -> name.equals(card.getName())).count();
    }

    /** Passes everything and records the active player of each new turn, starting with the current one. */
    private static List<String> turnsAfter(XmageMultiplayerScenario s, int wanted) {
        Game game = s.session.restorationGame();
        List<String> turns = new ArrayList<>();
        int lastTurn = -1;
        for (int i = 0; i < 4000 && turns.size() < wanted; i++) {
            if (game.getTurnNum() != lastTurn) {
                lastTurn = game.getTurnNum();
                turns.add(s.pidOf(game.getActivePlayerId().toString()));
                if (turns.size() == wanted) {
                    break;
                }
            }
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            switch (cls) {
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_object", "target" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "discard-" + i, "Mountain",
                        s.session.pendingDecisionPayload().getAsJsonObject("decision")
                                .get("minimum_selections").getAsInt());
                default -> fail("unexpected " + cls + " for " + s.actor() + " " + s.labels() + " " + s.prompt());
            }
        }
        return turns;
    }

    private static JsonObject pick(XmageMultiplayerScenario s, String labelPart) {
        for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            String label = e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString();
            if (label.equals(labelPart) || label.contains(labelPart)) {
                return e.getAsJsonObject();
            }
        }
        fail("no option " + labelPart + " in " + s.labels());
        return null;
    }
}

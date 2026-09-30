package org.commanderlab.xmage;

import com.google.gson.JsonArray;
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
 * F-27: controlling another player's turn, with actual cards at 2P through 5P
 * on the full-game lane.
 *
 * <p>Mindslaver's Oracle reminder text says the controller sees all cards the
 * player could see and makes all decisions for that player. P1 targets P2, the
 * next player in turn order. During P2's turn every decision goes to P1,
 * marked as made for P2; P1 makes P2 cast its own Lightning Bolt at P2. The
 * turn after is decided normally again. This exercises CR 723.</p>
 */
class XmageMultiplayerTurnControlTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 3, 4, 5})
    void theControllerMakesEveryDecisionForTheControlledPlayer(int playerCount) {
        String controlled = "P2";
        String afterControlled = playerCount == 2 ? "P1" : "P3";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Mindslaver", 0, Zone.BATTLEFIELD));
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        objects.add(XmageMultiplayerScenario.obj(controlled, "Lightning Bolt", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj(controlled, "Mountain", 1, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "turn-control-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        int controlledSeat = XmageFullGameStateRedactor.seat(game, s.seats.get(controlled).getId());
        int controlledLife = s.seats.get(controlled).getLife();

        boolean activated = false;
        boolean boltCast = false;
        boolean sawControlledTurn = false;
        for (int i = 0; i < 200; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            String active = XmageNativeStateRestorationTest.pidOf(
                    s.seats, game.getActivePlayerId().toString());
            JsonObject decision = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            boolean actingFor = decision.has("acting_for_seat");

            if (afterControlled.equals(active) && sawControlledTurn) {
                assertTrue(sawControlledTurn, "P1 made decisions for P2 during its turn");
                assertEquals(afterControlled, actor, "the next turn is decided by its own player");
                assertFalse(actingFor, "no one acts for another player now");
                assertEquals(controlledLife - 3, s.seats.get(controlled).getLife(), "P1 made P2 bolt itself");
                assertControlledSeatInExportedTranscript(s.session, controlledSeat);
                return;
            }
            if (controlled.equals(active)) {
                assertFalse(
                        controlled.equals(actor),
                        "CR 723: P2 is never asked during its controlled turn (" + cls + ")"
                );
                if (actingFor) {
                    sawControlledTurn = true;
                    assertEquals("P1", actor, "a decision made for P2 goes to P1 (" + cls + ")");
                    assertEquals(controlledSeat, decision.get("acting_for_seat").getAsInt());
                    assertTrue(
                            handOf(decision.getAsJsonObject("pilot_state"), controlledSeat)
                                    .contains("Lightning Bolt") || boltCast,
                            "P1 sees P2's hand"
                    );
                }
            } else {
                assertFalse(actingFor, "before P2's turn, everyone decides for themselves");
            }

            switch (cls) {
                case "priority" -> {
                    if (!activated && "P1".equals(active)) {
                        s.submit(s.action("activate_ability", "Mindslaver"));
                        activated = true;
                    } else if (controlled.equals(active) && "P1".equals(actor) && !boltCast
                            && game.getStack().isEmpty()
                            && s.action("activate_ability", "Cast Lightning Bolt") != null) {
                        s.submit(s.action("activate_ability", "Cast Lightning Bolt"));
                        boltCast = true;
                    } else {
                        s.submit(s.action("pass_priority", "Pass"));
                    }
                }
                case "mana_payment" -> s.payWith(controlled.equals(active) ? "Mountain" : "Island");
                case "target" -> s.submit(s.action("choose_targets", "Seat 2"));
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null),
                        "d" + i,
                        "Mountain",
                        decision.get("minimum_selections").getAsInt()
                );
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail("the turn after P2's was not reached");
    }

    private static void assertControlledSeatInExportedTranscript(
            XmageFullGameSession session, int controlledSeat) {
        JsonArray transcript = session.resultPayload().getAsJsonArray("transcript");
        boolean requested = false;
        boolean accepted = false;
        for (JsonElement element : transcript) {
            JsonObject event = element.getAsJsonObject();
            if (!event.has("acting_for_seat")
                    || event.get("acting_for_seat").getAsInt() != controlledSeat) {
                continue;
            }
            String kind = event.has("kind") ? event.get("kind").getAsString() : "";
            requested |= "decision_requested".equals(kind);
            accepted |= "decision_accepted".equals(kind);
        }
        assertTrue(requested, "exported transcript binds controlled seat on request");
        assertTrue(accepted, "exported transcript binds controlled seat on acceptance");
    }

    private static List<String> handOf(JsonObject pilotState, int seat) {
        List<String> names = new ArrayList<>();
        for (JsonElement e : pilotState.getAsJsonArray("players")) {
            JsonObject player = e.getAsJsonObject();
            if (player.get("seat").getAsInt() == seat && player.has("hand")) {
                for (JsonElement card : player.getAsJsonArray("hand")) {
                    names.add(card.getAsJsonObject().get("name").getAsString());
                }
            }
        }
        return names;
    }
}

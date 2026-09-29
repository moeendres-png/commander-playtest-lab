package org.commanderlab.xmage;

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
 * F-34: a player who controls another player's turn and leaves the game never
 * makes that player's decisions again, with actual cards at 4P and 5P.
 *
 * <p>P1 activates Mindslaver ("You control target player during that
 * player's next turn") targeting P4 and concedes while it is making one of
 * P4's decisions. CR 800.4a: when a player leaves the game, effects that give
 * that player control of another player end. The engine decides who now
 * controls P4's turn; the bridge only follows it:</p>
 * <ul>
 *   <li>engine returned control (the repin donor fix): the unanswered frame
 *   is re-addressed to P4 itself, and P4 answers its own turn;</li>
 *   <li>engine still names the departed P1 (pin {@code f79e4168}): the lane
 *   fails closed with {@code TURN_CONTROLLER_LEFT}.</li>
 * </ul>
 * <p>Before the fix the departed P1 kept being asked P4's decisions.</p>
 */
class XmageMultiplayerControllerLeavesTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aDepartedControllerNeverDecidesForTheControlledPlayer(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Mindslaver", 0, Zone.BATTLEFIELD));
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("slaver-leave-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        String p1 = s.seats.get("P1").getId().toString();
        boolean activated = false;
        for (int i = 0; i < 160; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            JsonObject decision = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            if (decision.has("acting_for_seat")) {
                assertEquals("P1", actor, "control: P1 makes P4's decisions during the Mindslaver turn");
                assertEquals(s.seats.get("P4").getId(), game.getActivePlayerId(), "control: it is P4's turn");
                concedeAndCheck(s, game, p1);
                return;
            }
            if (!activated && "priority".equals(cls) && "P1".equals(actor)) {
                s.submit(s.action("activate_ability", "Mindslaver"));
                activated = true;
                continue;
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Island");
                case "target" -> s.submit(s.action("choose_targets", "Seat 4"));
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "d" + i, "Mountain",
                        decision.get("minimum_selections").getAsInt());
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail("P1 never made a decision for P4");
    }

    private static void concedeAndCheck(XmageMultiplayerScenario s, Game game, String p1) {
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", "p1-concede");
        concede.addProperty("actor_id", p1);
        concede.addProperty("player_id", p1);
        JsonObject result = s.session.submitConcede(concede);
        assertFalse(s.seats.get("P1").isInGame(), "P1 left the game");

        if (s.seats.get("P1").getId().equals(s.seats.get("P4").getTurnControlledBy())) {
            // The engine still names the departed P1: nobody may be asked.
            assertTrue(result.get("decision").isJsonNull(), "no frame for a departed controller: " + result);
            assertTrue(result.getAsJsonObject("failure").get("message").getAsString()
                    .startsWith("TURN_CONTROLLER_LEFT"), "fails closed: " + result.get("failure"));
            return;
        }

        assertEquals(s.seats.get("P4").getId(), s.seats.get("P4").getTurnControlledBy(),
                "the engine returned P4's turn to P4");
        String p4 = s.seats.get("P4").getId().toString();
        int p4Decisions = 0;
        for (int i = 0; i < 60 && game.getActivePlayerId().equals(s.seats.get("P4").getId()); i++) {
            JsonObject decision = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            String actorId = decision.get("actor_id").getAsString();
            assertFalse(p1.equals(actorId), "the departed P1 is asked " + decision.get("decision_class"));
            assertFalse(decision.has("acting_for_seat"), "nobody acts for P4 any more");
            if (p4.equals(actorId)) {
                p4Decisions++;
            }
            switch (s.decisionClass()) {
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "p" + i, "Mountain",
                        decision.get("minimum_selections").getAsInt());
                default -> fail("unexpected " + s.decisionClass() + " " + s.labels());
            }
        }
        assertTrue(p4Decisions > 0, "P4 answered its own turn, starting with the re-addressed frame");
    }
}

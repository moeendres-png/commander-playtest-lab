package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * The controlled player leaves during its own controlled turn, at 4P and 5P.
 *
 * <p>P1 activates Mindslaver ("You control target player during that player's
 * next turn") targeting P4. During P4's turn P1 makes P4's decisions. P4 then
 * concedes. CR 800.4a: a player who left makes no decisions, so nobody (P1
 * included) is asked anything on P4's behalf again; the turn continues
 * without an active player and the next turn belongs to the seat after P4.
 * The lane must go on or fail closed; it must never publish a decision for
 * the departed P4.</p>
 */
class XmageMultiplayerControlledPlayerLeavesTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void nobodyDecidesForAControlledPlayerWhoLeft(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Mindslaver", 0, Zone.BATTLEFIELD));
        for (int i = 1; i <= 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("slaver-victim-leaves-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        UUID p4 = s.seats.get("P4").getId();
        boolean activated = false;
        boolean left = false;
        int turnAfterLeave = -1;
        List<String> afterLeave = new ArrayList<>();
        for (int i = 0; i < 400; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            if (!payload.get("failure").isJsonNull()) {
                String message = payload.getAsJsonObject("failure").get("message").getAsString();
                assertTrue(left, "failure before P4 left: " + message);
                // Fail closed is acceptable; a decision for P4 is not.
                System.out.println("CONTROLLED-LEAVE " + playerCount + "P fail-closed: " + message);
                return;
            }
            String cls = s.decisionClass();
            String actor = s.actor();
            JsonObject decision = payload.getAsJsonObject("decision");
            if (left) {
                afterLeave.add(actor + ":" + cls);
                assertFalse("P4".equals(actor), "P4 is asked " + cls + " after it left");
                if (decision.has("acting_for_seat")) {
                    // F-39 design: a departed player's last priority round is pass-only.
                    assertEquals("priority", cls, "nobody decides for the departed P4: " + cls + " to " + actor);
                    assertEquals(List.of("Pass"), s.labels().stream().map(l -> l.startsWith("Pass") ? "Pass" : l).toList(),
                            "a frame for the departed P4 offers only pass: " + s.labels());
                    afterLeave.add("acting_for=" + decision.get("acting_for_seat") + " labels=" + s.labels());
                }
                if (game.getTurnNum() != turnAfterLeave) {
                    assertEquals(playerCount == 4 ? s.seats.get("P1").getId() : s.seats.get("P5").getId(),
                            game.getActivePlayerId(), "the next turn belongs to the seat after P4");
                    System.out.println("CONTROLLED-LEAVE " + playerCount + "P after-leave decisions " + afterLeave);
                    return;
                }
            }
            if (!left && decision.has("acting_for_seat")) {
                assertEquals("P1", actor, "control: P1 makes P4's decisions during the Mindslaver turn");
                assertEquals(p4, game.getActivePlayerId(), "control: it is P4's turn");
                String id = p4.toString();
                JsonObject concede = new JsonObject();
                concede.addProperty("proposal_id", "p4-concede");
                concede.addProperty("actor_id", id);
                concede.addProperty("player_id", id);
                JsonObject result = s.session.submitConcede(concede);
                left = true;
                turnAfterLeave = game.getTurnNum();
                assertFalse(s.seats.get("P4").isInGame(), "P4 left the game: " + result);
                continue;
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
        fail("P4's turn after the concession never ended; left=" + left + " after=" + afterLeave);
    }
}

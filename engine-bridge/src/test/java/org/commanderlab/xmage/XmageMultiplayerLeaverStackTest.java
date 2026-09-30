package org.commanderlab.xmage;

import com.google.gson.JsonArray;
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
 * F-39: a player who leaves while holding priority, with actual cards at 4P
 * and 5P on the full-game lane.
 *
 * <p>On P1's turn P2 casts Lightning Bolt ("Lightning Bolt deals 3 damage to
 * any target.") at P3, keeps priority with a second Lightning Bolt castable,
 * and concedes. CR 800.4a: P2's objects leave the game and its spell on the
 * stack ceases to exist, so P3 takes no damage, and a player who left takes
 * no actions.</p>
 *
 * <p>P2's unanswered priority frame is re-issued with only the pass option.
 * Before the fix it still offered "Cast Lightning Bolt", which the engine no
 * longer executes, so picking it failed the lane with
 * {@code XMAGE_ACTION_EXECUTION_FAILED}.</p>
 */
class XmageMultiplayerLeaverStackTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aPlayerWhoLeftWhileHoldingPriorityIsOfferedNoAction(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P2", "Lightning Bolt", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P2", "Lightning Bolt", 1, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P2", "Mountain", 2, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Mountain", 3, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("leaver-stack-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        String p2 = s.seats.get("P2").getId().toString();
        boolean cast = false;
        for (int i = 0; i < 40; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            if (cast && "P2".equals(actor) && "priority".equals(cls)) {
                assertEquals(1, game.getStack().size(), "control: P2's Bolt is on the stack");
                assertTrue(s.labels().contains("Lightning Bolt — Cast Lightning Bolt"),
                        "control: P2 could cast its second Bolt");
                concedeAndCheck(s, game, p2);
                return;
            }
            switch (cls) {
                case "priority" -> s.submit(!cast && "P2".equals(actor)
                        ? s.action("activate_ability", "Cast Lightning Bolt")
                        : s.action("pass_priority", "Pass"));
                case "target" -> {
                    s.submit(s.action("choose_targets", "Seat 3"));
                    cast = true;
                }
                case "mana_payment" -> s.payWith("Mountain");
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        fail("P2 never held priority over its Bolt");
    }

    private static void concedeAndCheck(XmageMultiplayerScenario s, Game game, String p2) {
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", "p2-concede");
        concede.addProperty("actor_id", p2);
        concede.addProperty("player_id", p2);
        JsonObject result = s.session.submitConcede(concede);
        assertFalse(s.seats.get("P2").isInGame(), "P2 left the game");
        assertTrue(game.getStack().isEmpty(), "P2's Bolt ceased to exist (800.4a)");
        assertTrue(result.get("failure").isJsonNull(), "the lane goes on: " + result.get("failure"));

        JsonObject frame = result.getAsJsonObject("decision");
        assertEquals(p2, frame.get("actor_id").getAsString(), "P2 still answers its own frame");
        assertEquals("priority", frame.get("decision_class").getAsString());
        JsonArray options = frame.getAsJsonArray("legal_options");
        assertEquals(1, options.size(), "only the pass option remains: " + options);
        assertEquals("pass_priority", options.get(0).getAsJsonObject().get("option_type").getAsString());
        assertTrue(frame.getAsJsonObject("context").get("actor_left_game").getAsBoolean());

        s.submit(s.action("pass_priority", "Pass"));
        for (int i = 0; i < 2 * s.seats.size(); i++) {
            JsonObject next = s.session.pendingDecisionPayload().getAsJsonObject("decision");
            assertFalse(p2.equals(next.get("actor_id").getAsString()), "P2 is never asked again");
            s.submit(s.action("pass_priority", "Pass"));
        }
        assertEquals(40, s.seats.get("P3").getLife(), "P3 took no damage from the departed Bolt");
    }
}

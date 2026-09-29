package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Join forces with an actual card at 4P on the full-game lane.
 *
 * <p>Minds Aglow (Oracle: "Join forces — Starting with you, each player may pay
 * any amount of mana. Each player draws X cards, where X is the total amount of
 * mana paid this way."). P1 casts it; every player controls two Islands.</p>
 *
 * <ul>
 *   <li>Enabled: every player, starting with the caster and in turn order
 *       (P1, P4, P3, P2), announces its own payment through the external
 *       surface; P1, P4 and P3 pay 1 and P2 pays 0, so every player draws
 *       exactly 3.</li>
 *   <li>After P3 left the game earlier in the turn, only players in the game
 *       are asked (P1, P4, P2). Unlike voting (F-23, #335), this already holds
 *       at the pin: the payment helper skips a player who left, although the
 *       card iterates players in range including players who left.</li>
 * </ul>
 */
class XmageMultiplayerJoinForcesTest {

    private static XmageMultiplayerScenario board(String tag) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Minds Aglow", 0, Zone.HAND));
        for (int seat = 1; seat <= 4; seat++) {
            objects.add(XmageMultiplayerScenario.obj("P" + seat, "Island", 1, Zone.BATTLEFIELD));
            objects.add(XmageMultiplayerScenario.obj("P" + seat, "Island", 2, Zone.BATTLEFIELD));
        }
        return XmageMultiplayerScenario.start(tag, 4, "P1", objects);
    }

    /** Casts Minds Aglow and answers each payment announcement; returns who was asked, in order. */
    private static List<String> castAndPay(XmageMultiplayerScenario s, Map<String, Integer> payments) {
        s.submit(s.action("activate_ability", "Cast Minds Aglow"));
        List<String> asked = new ArrayList<>();
        StringBuilder trace = new StringBuilder();
        for (int i = 0; i < 80; i++) {
            String cls = s.decisionClass();
            if ("priority".equals(cls) && !asked.isEmpty()
                    && s.session.restorationGame().getStack().isEmpty()) {
                return asked;
            }
            String actor = s.actor();
            trace.append(actor).append(':').append(cls).append('\n');
            switch (cls) {
                case "mana_payment" -> s.payWith("Island");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "announce_x" -> {
                    asked.add(actor);
                    Integer amount = payments.get(actor);
                    assertNotNull(amount, actor + " was not expected to be asked; trace\n" + trace);
                    JsonObject pending = s.session.pendingDecisionPayload().getAsJsonObject("decision");
                    JsonObject proposal = new JsonObject();
                    proposal.addProperty("proposal_id", "jf-" + i);
                    proposal.addProperty("actor_id", s.session.legalActionsPayload().get("actor_id").getAsString());
                    proposal.addProperty("legal_action_id", pending.get("decision_id").getAsString() + ":numeric");
                    proposal.addProperty("action_type", "structural_decision");
                    proposal.add("target_ids", new JsonArray());
                    proposal.add("selected_modes", new JsonArray());
                    JsonObject choices = new JsonObject();
                    choices.addProperty("numeric_choice", amount);
                    proposal.add("choices", choices);
                    s.session.submitAction(proposal);
                }
                default -> fail("unexpected " + cls + " for " + actor + "; trace\n" + trace);
            }
        }
        fail("Minds Aglow did not resolve; trace\n" + trace);
        return asked;
    }

    private static Map<String, Integer> hands(XmageMultiplayerScenario s) {
        Map<String, Integer> out = new HashMap<>();
        s.seats.forEach((pid, player) -> out.put(pid, player.getHand().size()));
        return out;
    }

    @Test
    void everyPlayerStartingWithTheCasterMayPayAndEveryoneDrawsTheTotal() {
        XmageMultiplayerScenario s = board("jf-4p");
        Map<String, Integer> before = hands(s);
        List<String> asked = castAndPay(s, Map.of("P1", 1, "P4", 1, "P3", 1, "P2", 0));
        assertEquals(List.of("P1", "P4", "P3", "P2"), asked, "starting with you, in turn order");
        Map<String, Integer> after = hands(s);
        for (String pid : List.of("P2", "P3", "P4")) {
            assertEquals(before.get(pid) + 3, after.get(pid), pid + " drew X = 3");
        }
        assertEquals(before.get("P1") - 1 + 3, after.get("P1"), "P1 cast Minds Aglow and drew 3");
    }

    @Test
    void aPlayerWhoLeftThisTurnIsNotAskedToPay() {
        XmageMultiplayerScenario s = board("jf-left-4p");
        String p3 = s.seats.get("P3").getId().toString();
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", "jf-left-concede");
        concede.addProperty("actor_id", p3);
        concede.addProperty("player_id", p3);
        s.session.submitConcede(concede);
        assertEquals(false, s.seats.get("P3").isInGame());
        List<String> asked = castAndPay(s, Map.of("P1", 1, "P4", 1, "P2", 0));
        assertEquals(List.of("P1", "P4", "P2"), asked, "only players in the game are asked");
    }
}

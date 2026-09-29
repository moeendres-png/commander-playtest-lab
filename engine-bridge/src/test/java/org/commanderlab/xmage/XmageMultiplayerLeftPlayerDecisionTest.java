package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.Zone;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * A player who left the game must never be offered a decision.
 *
 * <p>Tempt with Discovery (Oracle: "Tempting offer — Search your library for a
 * land card and put it onto the battlefield. Each opponent may search their
 * library for a land card and put it onto the battlefield. For each opponent
 * who does, search your library for a land card and put it onto the
 * battlefield. Then each player who searched their library this way
 * shuffles."). 4P; P3 concedes on P1's turn; P1 then casts it.</p>
 */
class XmageMultiplayerLeftPlayerDecisionTest {

    @Test
    void temptingOfferIsNotOfferedToAPlayerWhoLeft() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Tempt with Discovery", 0, Zone.HAND));
        for (int i = 0; i < 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("tempt-left", 4, "P1", objects);
        String p3 = s.seats.get("P3").getId().toString();
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", "tempt-left-concede");
        concede.addProperty("actor_id", p3);
        concede.addProperty("player_id", p3);
        s.session.submitConcede(concede);
        assertEquals(false, s.seats.get("P3").isInGame());

        s.submit(s.action("activate_ability", "Cast Tempt with Discovery"));
        List<String> offered = new ArrayList<>();
        StringBuilder trace = new StringBuilder();
        for (int i = 0; i < 60; i++) {
            String cls = s.decisionClass();
            if ("priority".equals(cls) && !offered.isEmpty()
                    && s.session.restorationGame().getStack().isEmpty()) {
                assertEquals(List.of("P4", "P2"), offered,
                        "only opponents still in the game are offered the tempting offer");
                return;
            }
            String actor = s.actor();
            trace.append(actor).append(':').append(cls).append(' ').append(s.prompt()).append('\n');
            switch (cls) {
                case "mana_payment" -> s.payWith("Forest");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_use" -> {
                    offered.add(actor);
                    JsonObject no = null;
                    for (var e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
                        JsonObject a = e.getAsJsonObject();
                        if ("No".equals(a.getAsJsonObject("metadata").get("label").getAsString())) {
                            no = a;
                        }
                    }
                    if (no == null) {
                        fail("no 'No' option; " + s.labels() + "\\n" + trace);
                    }
                    s.submit(no);
                }
                case "choose_object", "target" -> {
                    // P1's own search: take a Mountain if offered, else none
                    JsonObject pick = s.action("choose_targets", "Mountain");
                    if (pick == null) {
                        fail("search: " + s.labels() + "\n" + trace);
                    } else {
                        s.submit(pick);
                    }
                }
                default -> fail("unexpected " + cls + " " + s.labels() + "\n" + trace);
            }
        }
        fail("did not resolve\n" + trace);
    }
}

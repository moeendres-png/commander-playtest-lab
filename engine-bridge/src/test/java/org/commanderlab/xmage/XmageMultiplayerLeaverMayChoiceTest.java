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
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * F-40: a player who leaves while its own "may" choice of another player's
 * spell is pending makes no choice, with actual cards at 4P and 5P.
 *
 * <p>P1 casts Tempt with Discovery (Oracle: "Tempting offer — Search your
 * library for a land card and put it onto the battlefield. Each opponent may
 * search their library for a land card and put it onto the battlefield. For
 * each opponent who does, search your library for a land card and put it onto
 * the battlefield. ..."). The first opponent asked concedes while its "may" is
 * open; every remaining opponent accepts. CR 800.4a: a player who left makes
 * no choices, so P1 searches once for itself and once for each <em>remaining</em>
 * opponent. Before the fix the departed player's stale frame was still
 * answered and counted, and P1 searched once more.</p>
 */
class XmageMultiplayerLeaverMayChoiceTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aDepartedOpponentsTemptingOfferIsNotCounted(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Tempt with Discovery", 0, Zone.HAND));
        for (int i = 0; i < 4; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Forest", i + 1, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("may-leave-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        s.submit(s.action("activate_ability", "Cast Tempt with Discovery"));
        String leaver = null;
        int p1SearchesAfterLeave = 0;
        List<String> accepted = new ArrayList<>();
        for (int i = 0; i < 80; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            String actor = s.actor();
            if (leaver != null) {
                assertFalse(leaver.equals(actor), "no " + cls + " frame is exposed to " + leaver + " after it left");
                if ("priority".equals(cls) && game.getStack().isEmpty()) {
                    break;
                }
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Forest");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_use" -> {
                    if (leaver == null) {
                        leaver = actor;
                        concede(s, actor);
                        assertFalse(s.seats.get(actor).isInGame(), actor + " left the game");
                    } else {
                        accepted.add(actor);
                        s.submit(labelled(s, "Yes"));
                    }
                }
                case "choose_object", "target" -> {
                    if (leaver != null && "P1".equals(actor)) {
                        p1SearchesAfterLeave++;
                    }
                    XmageActualCardCorpusTest.chooseNamed(
                            new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "o" + i, "Mountain", 1);
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        assertNotNull(leaver, "control: an opponent was asked the tempting offer");
        assertEquals(playerCount - 2, accepted.size(), "every remaining opponent was asked once and accepted");
        assertEquals(accepted.size(), p1SearchesAfterLeave,
                "P1 searches once per remaining opponent who accepted; the departed player's offer is not counted");
        boolean cancelled = false;
        for (JsonElement event : s.session.resultPayload().getAsJsonArray("transcript")) {
            JsonObject e = event.getAsJsonObject();
            if ("engine_decision_cancelled".equals(e.get("event_type") == null ? null : e.get("event_type").getAsString())) {
                cancelled |= e.getAsJsonObject("payload").get("reason").getAsString().equals("player_left_game");
            }
        }
        assertTrue(cancelled, "the retirement of the departed player's frame is recorded");
    }

    private static void concede(XmageMultiplayerScenario s, String pid) {
        String id = s.seats.get(pid).getId().toString();
        JsonObject concede = new JsonObject();
        concede.addProperty("proposal_id", pid + "-concede");
        concede.addProperty("actor_id", id);
        concede.addProperty("player_id", id);
        assertTrue(s.session.submitConcede(concede).get("failure").isJsonNull());
    }

    private static JsonObject labelled(XmageMultiplayerScenario s, String label) {
        for (JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            if (label.equals(e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString())) {
                return e.getAsJsonObject();
            }
        }
        fail("no " + label + " in " + s.labels());
        return null;
    }
}

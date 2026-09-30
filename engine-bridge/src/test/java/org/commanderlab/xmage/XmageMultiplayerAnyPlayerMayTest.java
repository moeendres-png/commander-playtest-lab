package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * "Any player may" punisher choices at 4P and 5P on the full-game lane.
 *
 * <p>Browbeat (Oracle): "Any player may have Browbeat deal 5 damage to them.
 * If no one does, target player draws three cards." Only what the Oracle text
 * fixes is asserted: when nobody accepts, every player in the game was offered
 * the choice (none silently skipped) and the target draws three; when exactly
 * one player accepts and everyone else declines, that player takes 5 and the
 * target draws nothing. The order in which players are asked is recorded but
 * not asserted.</p>
 */
class XmageMultiplayerAnyPlayerMayTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void nobodyAcceptsSoEveryoneWasAskedAndTheTargetDraws(int playerCount) {
        Result r = browbeat(playerCount, "none");
        List<String> all = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            all.add("P" + seat);
        }
        assertEquals(new TreeSet<>(all), new TreeSet<>(r.asked),
                "every player in the game is offered the choice: asked in order " + r.asked);
        assertEquals(r.handBefore + 3, r.handAfter, "no one took the damage: P2 draws three");
        for (int seat = 1; seat <= playerCount; seat++) {
            assertEquals(40, r.life.get("P" + seat), "P" + seat + " took no damage");
        }
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void oneAcceptsSoItTakesFiveAndTheTargetDrawsNothing(int playerCount) {
        Result r = browbeat(playerCount, "P3");
        assertTrue(r.asked.contains("P3"), "P3 was offered the choice: " + r.asked);
        assertEquals(r.handBefore, r.handAfter, "someone took the damage: P2 draws nothing");
        assertEquals(35, r.life.get("P3"), "P3 took 5");
        for (int seat = 1; seat <= playerCount; seat++) {
            if (seat != 3) {
                assertEquals(40, r.life.get("P" + seat), "P" + seat + " took no damage");
            }
        }
    }

    private record Result(List<String> asked, int handBefore, int handAfter, Map<String, Integer> life) {
    }

    private static Result browbeat(int playerCount, String acceptor) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Browbeat", 0, Zone.HAND));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", i, Zone.BATTLEFIELD));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "browbeat-" + acceptor + "-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        int handBefore = s.seats.get("P2").getHand().size();
        s.submit(s.action("activate_ability", "Cast Browbeat"));
        List<String> asked = new ArrayList<>();
        boolean cast = false;
        for (int i = 0; i < 120; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            String actor = s.actor();
            if ("priority".equals(cls) && game.getStack().isEmpty() && cast) {
                break;
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Mountain");
                case "target" -> {
                    cast = true;
                    s.submit(pick(s, "Seat 2"));
                }
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_use" -> {
                    asked.add(actor);
                    s.submit(pick(s, acceptor.equals(actor) ? "Yes" : "No"));
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels() + " " + s.prompt());
            }
        }
        Map<String, Integer> life = new TreeMap<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            life.put("P" + seat, s.seats.get("P" + seat).getLife());
        }
        System.out.println("BROWBEAT " + playerCount + "P acceptor=" + acceptor + " asked=" + asked);
        return new Result(asked, handBefore, s.seats.get("P2").getHand().size(), life);
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

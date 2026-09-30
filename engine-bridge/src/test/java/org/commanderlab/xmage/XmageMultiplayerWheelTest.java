package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * A wheel whose draw count depends on every player's hand, at 4P and 5P on the
 * full-game lane.
 *
 * <p>Windfall (Oracle): "Each player discards their hand, then draws cards
 * equal to the greatest number of cards a player discarded this way." P3 is
 * given three extra cards, so it holds the largest hand. After resolution
 * every player holds exactly that greatest number, and each player's
 * graveyard gained exactly the cards it discarded.</p>
 */
class XmageMultiplayerWheelTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void everyPlayerDrawsTheGreatestNumberAnyPlayerDiscarded(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Windfall", 0, Zone.HAND));
        for (int i = 1; i <= 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", "Island", i, Zone.BATTLEFIELD));
        }
        for (int i = 0; i < 3; i++) {
            objects.add(XmageMultiplayerScenario.obj("P3", "Grizzly Bears", 10 + i, Zone.HAND));
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("windfall-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();

        Map<String, Integer> handBefore = new LinkedHashMap<>();
        Map<String, Integer> graveBefore = new LinkedHashMap<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            int hand = s.seats.get(pid).getHand().size();
            // P1 casts Windfall from its hand, so it discards one card fewer.
            handBefore.put(pid, "P1".equals(pid) ? hand - 1 : hand);
            graveBefore.put(pid, s.seats.get(pid).getGraveyard().size());
        }
        int greatest = handBefore.values().stream().mapToInt(Integer::intValue).max().orElseThrow();
        assertEquals(handBefore.get("P3"), greatest, "control: P3 holds the largest hand " + handBefore);

        s.submit(s.action("activate_ability", "Cast Windfall"));
        boolean cast = false;
        for (int i = 0; i < 80; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            if ("priority".equals(cls) && game.getStack().isEmpty() && cast) {
                break;
            }
            switch (cls) {
                case "mana_payment" -> {
                    cast = true;
                    s.payWith("Island");
                }
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                default -> fail("unexpected " + cls + " for " + s.actor() + " " + s.labels() + " " + s.prompt());
            }
        }
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            assertEquals(greatest, s.seats.get(pid).getHand().size(),
                    pid + " draws the greatest number any player discarded (" + greatest + ")");
            int windfall = "P1".equals(pid) ? 1 : 0;
            assertEquals(graveBefore.get(pid) + handBefore.get(pid) + windfall,
                    s.seats.get(pid).getGraveyard().size(), pid + " discarded exactly its whole hand");
        }
    }
}

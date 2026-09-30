package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.stack.StackObject;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Hive Mind at 4P and 5P on the full-game lane: one spell, one copy for every
 * other player, each copy decided by its own controller.
 *
 * <p>Oracle: "Whenever a player casts an instant or sorcery spell, each other
 * player copies that spell. Each of those players may choose new targets for
 * their copy." A copy is controlled by the player who put it on the stack
 * (707.10), so each other player controls exactly one copy and only that player
 * is asked whether to change its target (707.10c).</p>
 *
 * <p>P1 casts Lightning Bolt at P2. The last seat keeps its copy's target; every
 * other copier redirects its copy to P1. Expected life totals follow from the
 * Oracle text alone.</p>
 */
class XmageMultiplayerHiveMindTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void everyOtherPlayerControlsAndRetargetsItsOwnCopy(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Lightning Bolt", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P3", "Hive Mind", 2, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("hivemind-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        String last = "P" + playerCount;

        s.submit(s.action("activate_ability", "Cast Lightning Bolt"));
        List<String> retargetAsked = new ArrayList<>();
        List<String> targetAsked = new ArrayList<>();
        Map<UUID, String> copyControllers = new LinkedHashMap<>();
        for (int i = 0; i < 120; i++) {
            String cls = s.decisionClass();
            String actor = s.actor();
            for (StackObject o : game.getStack()) {
                if (o.isCopy() && "Lightning Bolt".equals(o.getName())) {
                    copyControllers.putIfAbsent(o.getId(), seatOf(s, o.getControllerId()));
                }
            }
            if ("priority".equals(cls) && game.getStack().isEmpty() && !targetAsked.isEmpty()) {
                break;
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Mountain");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_use" -> {
                    retargetAsked.add(actor);
                    s.submit(pick(s, last.equals(actor) ? "No" : "Yes"));
                }
                case "target" -> {
                    targetAsked.add(actor);
                    s.submit(pick(s, "P1".equals(actor) && targetAsked.size() == 1 ? "Seat 2" : "Seat 1"));
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        List<String> others = new ArrayList<>();
        for (int seat = 2; seat <= playerCount; seat++) {
            others.add("P" + seat);
        }
        assertEquals(others, copyControllers.values().stream().sorted().toList(),
                "707.10: each other player controls exactly one copy");
        assertEquals(others, retargetAsked.stream().sorted().toList(),
                "707.10c: each copy's controller, and only it, is asked about new targets");
        assertEquals("P1", targetAsked.get(0), "P1 targets its own Bolt");
        List<String> retargeters = new ArrayList<>(others);
        retargeters.remove(last);
        assertEquals(retargeters, targetAsked.subList(1, targetAsked.size()).stream().sorted().toList(),
                "a copier that keeps the target is not asked for one");
        int redirected = playerCount - 2;
        assertEquals(40 - 3 * redirected, s.seats.get("P1").getLife(), "every copier but the last hit P1");
        assertEquals(40 - 3 - 3, s.seats.get("P2").getLife(), "the Bolt and the last seat's kept copy hit P2");
        for (int seat = 3; seat <= playerCount; seat++) {
            assertEquals(40, s.seats.get("P" + seat).getLife(), "P" + seat + " untouched");
        }
        assertNotNull(game.getStack());
    }

    /**
     * The last seat concedes while its own "choose new targets for your copy?"
     * frame is open. CR 800.4a: objects it controls on the stack that are not
     * represented by cards cease to exist, so its copy never resolves; it is
     * never asked anything again (F-42); the other copies resolve as chosen.
     */
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void aCopierWhoLeavesTakesItsCopyWithIt(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Lightning Bolt", 0, Zone.HAND));
        objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P3", "Hive Mind", 2, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("hivemind-leave-" + playerCount + "p",
                playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        String last = "P" + playerCount;
        UUID lastId = s.seats.get(last).getId();

        s.submit(s.action("activate_ability", "Cast Lightning Bolt"));
        boolean left = false;
        int targets = 0;
        for (int i = 0; i < 120; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "the lane goes on: " + payload.get("failure"));
            String cls = s.decisionClass();
            String actor = s.actor();
            if (left) {
                assertTrue(!last.equals(actor), "no " + cls + " frame is exposed to " + last + " after it left");
                for (StackObject o : game.getStack()) {
                    assertTrue(!lastId.equals(o.getControllerId()), "800.4a: the leaver's copy ceased to exist");
                }
            }
            if ("priority".equals(cls) && game.getStack().isEmpty() && targets > 0) {
                break;
            }
            switch (cls) {
                case "mana_payment" -> s.payWith("Mountain");
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_use" -> {
                    if (last.equals(actor)) {
                        String id = s.seats.get(last).getId().toString();
                        JsonObject concede = new JsonObject();
                        concede.addProperty("proposal_id", last + "-concede");
                        concede.addProperty("actor_id", id);
                        concede.addProperty("player_id", id);
                        assertTrue(s.session.submitConcede(concede).get("failure").isJsonNull());
                        left = true;
                    } else {
                        s.submit(pick(s, "Yes"));
                    }
                }
                case "target" -> {
                    targets++;
                    s.submit(pick(s, "P1".equals(actor) && targets == 1 ? "Seat 2" : "Seat 1"));
                }
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels());
            }
        }
        assertTrue(left, "control: the last seat was asked about its copy");
        assertTrue(!s.seats.get(last).isInGame(), last + " left the game");
        assertEquals(40 - 3 * (playerCount - 2), s.seats.get("P1").getLife(), "every remaining copier hit P1");
        assertEquals(40 - 3, s.seats.get("P2").getLife(), "only the original Bolt hit P2; the leaver's copy is gone");
    }

    private static String seatOf(XmageMultiplayerScenario s, UUID playerId) {
        for (Map.Entry<String, mage.players.Player> e : s.seats.entrySet()) {
            if (e.getValue().getId().equals(playerId)) {
                return e.getKey();
            }
        }
        return "?";
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

package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Directional control exchange at 3–6 players, with an actual card on the
 * full-game lane.
 *
 * <p>P1 casts Order of Succession (Oracle: "Choose left or right. Starting with
 * you and proceeding in the chosen direction, each player chooses a creature
 * controlled by the next player in that direction. Each player gains control
 * of the creature they chose."). Every player controls exactly one creature,
 * each with a different name.</p>
 *
 * <p>Seat topology follows CR 103.1: turns go clockwise, P1 → PN → … → P2, so
 * the player to a player's left is the next player in turn order.</p>
 *
 * <ul>
 *   <li>The choosers are every player once, starting with P1 and proceeding in
 *       the chosen direction.</li>
 *   <li>Each chooser picks from exactly the creature of its neighbour in that
 *       direction, and ends up controlling it.</li>
 * </ul>
 */
class XmageMultiplayerDirectionalExchangeTest {

    private static final String ORDER = "Order of Succession";
    private static final List<String> CREATURES = List.of(
            "Grizzly Bears", "Hill Giant", "Craw Wurm", "Walking Corpse", "Raging Goblin", "Air Elemental");

    @ParameterizedTest(name = "{0} players, {1}")
    @CsvSource({"3,Left", "3,Right", "4,Left", "4,Right", "5,Left", "5,Right", "6,Left", "6,Right"})
    void eachPlayerTakesTheCreatureOfItsNeighbourInTheChosenDirection(int playerCount, String direction) {
        String tag = "succession-" + playerCount + "p-" + direction;
        List<String> turnOrder = new ArrayList<>(List.of("P1"));
        for (int seat = playerCount; seat >= 2; seat--) {
            turnOrder.add("P" + seat);
        }
        boolean left = "Left".equals(direction);
        // Chooser sequence and each chooser's neighbour in the chosen direction.
        List<String> choosers = new ArrayList<>();
        Map<String, String> neighbour = new LinkedHashMap<>();
        for (int index = 0; index < playerCount; index++) {
            int at = left ? index : (playerCount - index) % playerCount;
            int next = left ? (at + 1) % playerCount : (at - 1 + playerCount) % playerCount;
            choosers.add(turnOrder.get(at));
            neighbour.put(turnOrder.get(at), turnOrder.get(next));
        }

        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", ORDER, 0));
        for (int index = 0; index < 4; index++) {
            objects.add(obj("bf", "P1", "Island", index));
        }
        for (int seat = 1; seat <= playerCount; seat++) {
            objects.add(obj("bf", "P" + seat, creatureOf("P" + seat), 0));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();

        XmageActualCardCorpusTest.cast(started, tag + "-cast", ORDER);
        List<String> seen = new ArrayList<>();
        XmageActualCardCorpusTest.resolveAll(started, tag, "Island — {T}: Add {U}.", (cls, step) -> {
            String actor = XmageActualCardCorpusTest.actorPid(started);
            switch (cls) {
                case "choice" -> {
                    assertEquals("P1", actor);
                    XmageActualCardCorpusTest.submit(started, tag + "-direction",
                            XmageActualCardCorpusTest.labelled(started, direction));
                }
                case "target", "choose_object" -> {
                    List<String> labels = new ArrayList<>();
                    for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
                        labels.add(element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
                    }
                    String wanted = creatureOf(neighbour.get(actor));
                    assertNotNull(wanted, actor);
                    assertEquals(List.of(wanted), labels,
                            actor + " chooses only among the creatures of its " + direction + " neighbour "
                                    + neighbour.get(actor));
                    seen.add(actor);
                    XmageActualCardCorpusTest.chooseByExactName(started, tag + "-take-" + actor, wanted, 1);
                }
                default -> {
                    return false;
                }
            }
            return true;
        });

        assertEquals(choosers, seen, "starting with P1 and proceeding " + direction + ", every player chooses once");
        for (String chooser : choosers) {
            String creature = creatureOf(neighbour.get(chooser));
            Permanent permanent = null;
            for (Permanent candidate : game.getBattlefield().getAllActivePermanents()) {
                if (creature.equals(candidate.getName())) {
                    permanent = candidate;
                }
            }
            assertNotNull(permanent, creature);
            assertEquals(started.seats().get(chooser).getId(), permanent.getControllerId(),
                    chooser + " gains control of " + creature);
            assertTrue(!permanent.getControllerId().equals(permanent.getOwnerId()), "every creature changed hands");
        }
    }

    private static String creatureOf(String pid) {
        return CREATURES.get(Integer.parseInt(pid.substring(1)) - 1);
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}

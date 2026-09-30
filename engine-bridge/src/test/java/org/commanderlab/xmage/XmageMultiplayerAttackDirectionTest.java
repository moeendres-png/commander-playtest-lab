package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Seat direction at 3–6 players, with an actual card on the full-game lane.
 *
 * <p>P1 casts Mystic Barrier (Oracle: "When Mystic Barrier enters and at the
 * beginning of your upkeep, choose left or right. Each player may attack only
 * the nearest opponent in the last chosen direction and planeswalkers
 * controlled by that player.") and chooses a direction. P1 and P2 each control
 * a Grizzly Bears.</p>
 *
 * <p>CR 103.1: the default turn order proceeds clockwise. Seen from above, the
 * next player in turn order therefore sits to the current player's left.
 * Turns run in seat order, P1 → P2 → … → PN (F-41). So P1's left neighbour is
 * P2 and its right neighbour is PN. P2's left neighbour is P3 and its right
 * is P1.</p>
 *
 * <p>The engine's attack offers must name exactly that one opponent: P1's
 * attack on turn 1, and P2's attack on turn 2, which is P2's turn.</p>
 */
class XmageMultiplayerAttackDirectionTest {

    private static final String BARRIER = "Mystic Barrier";
    private static final String BEARS = "Grizzly Bears";

    @ParameterizedTest(name = "{0} players, {1}")
    @CsvSource({"3,left", "3,right", "4,left", "4,right", "5,left", "5,right", "6,left", "6,right"})
    void eachPlayerMayAttackOnlyTheNearestOpponentInTheChosenDirection(int playerCount, String direction) {
        String tag = "barrier-" + playerCount + "p-" + direction;
        String pn = "P" + playerCount;
        boolean left = "left".equals(direction);
        Map<String, String> expected = new LinkedHashMap<>();
        expected.put("P1", left ? "P2" : pn);
        expected.put("P2", left ? "P3" : "P1");

        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", BARRIER, 0));
        for (int index = 0; index < 5; index++) {
            objects.add(obj("bf", "P1", "Plains", index));
        }
        objects.add(obj("bf", "P1", BEARS, 0));
        objects.add(obj("bf", "P2", BEARS, 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();

        XmageActualCardCorpusTest.cast(started, tag + "-cast", BARRIER);
        boolean chosen = false;
        Map<String, List<String>> offered = new LinkedHashMap<>();
        for (int step = 0; step < 400 && offered.size() < 2; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "mana_payment" -> XmageActualCardCorpusTest.payOneFromRestoredMana(started, tag + "-pay-" + step,
                        List.of("Plains"), java.util.Set.of("Plains — {T}: Add {W}."));
                case "choice" -> {
                    assertEquals("P1", actor);
                    assertTrue(!chosen, "the direction is chosen once (on entering; P1's upkeep is not reached)");
                    chosen = true;
                    List<String> labels = new ArrayList<>();
                    for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
                        labels.add(element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
                    }
                    assertEquals(List.of("left", "right"), labels);
                    XmageActualCardCorpusTest.submit(started, tag + "-direction",
                            XmageActualCardCorpusTest.labelled(started, direction));
                }
                case "declare_attacker" -> {
                    assertEquals(PhaseStep.DECLARE_ATTACKERS, game.getStep().getType());
                    assertEquals(actor, XmageNativeStateRestorationTest.pidOf(started.seats(),
                            game.getActivePlayerId().toString()), "only the active player declares attackers");
                    List<String> defenders = new ArrayList<>();
                    JsonObject decline = null;
                    for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
                        JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
                        JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
                        if (engine != null && engine.has("defender_id")) {
                            defenders.add(XmageNativeStateRestorationTest.pidOf(started.seats(),
                                    engine.get("defender_id").getAsString()));
                        } else if (meta.get("label").getAsString().startsWith("Do not attack")) {
                            decline = element.getAsJsonObject();
                        }
                    }
                    offered.put(actor, defenders);
                    assertTrue(decline != null, "attacking stays optional");
                    // Decline: the offers are the evidence; no blocks or damage are needed.
                    XmageActualCardCorpusTest.submit(started, tag + "-decline-" + actor, decline);
                }
                case "choose_object" -> {
                    assertEquals(PhaseStep.CLEANUP, game.getStep().getType());
                    XmageActualCardCorpusTest.chooseByExactName(started, tag + "-discard-" + step, "Mountain", 1);
                }
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor + " at " + game.getStep().getType());
            }
        }
        assertTrue(chosen, "direction chosen");
        assertEquals(List.of("P1", "P2"), new ArrayList<>(offered.keySet()),
                "P1 attacks on turn 1, P2 (next in turn order) on turn 2");
        for (Map.Entry<String, String> entry : expected.entrySet()) {
            assertEquals(List.of(entry.getValue()), offered.get(entry.getKey()),
                    entry.getKey() + " may attack only the nearest opponent to its " + direction);
        }
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}

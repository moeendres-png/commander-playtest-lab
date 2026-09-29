package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import org.junit.jupiter.api.Disabled;
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
 * Block-declaration order with several defending players, at 3–6 players, on
 * the full-game lane (CR 802.4: "each defending player in APNAP order declares
 * blockers ... The first defending player declares all their blocks, then the
 * second defending player, and so on.").
 *
 * <p>P1 attacks every opponent with a different creature, and every opponent
 * has a Wall of Stone that could block. The order of the declare_blocker
 * decisions must be APNAP: PN, …, P2. It must also be identical across three
 * games with the same seed and choices (semantic replay).</p>
 *
 * <p>F-29: the pinned engine iterates a hash set of defending players. So the
 * order was arbitrary and changed from game to game: six identical 4P games
 * gave four different orders. The fix is in the XMage fork. This test is
 * enabled by the repin to a candidate that contains it.</p>
 */
class XmageMultiplayerBlockOrderTest {

    private static final List<String> ATTACKERS = List.of(
            "Grizzly Bears", "Hill Giant", "Craw Wurm", "Walking Corpse", "Raging Goblin");

    @Disabled("F-29: engine fix moeendres-png/mage#28; enabled by the repin to a candidate containing it")
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void defendingPlayersDeclareBlockersInApnapOrderEveryGame(int playerCount) {
        List<String> apnap = new ArrayList<>();
        for (int seat = playerCount; seat >= 2; seat--) {
            apnap.add("P" + seat);
        }
        for (int run = 0; run < 3; run++) {
            assertEquals(apnap, run(playerCount, run), "run " + run + ": defenders declare blockers in APNAP order");
        }
    }

    private static List<String> run(int playerCount, int run) {
        String tag = "block-order-" + playerCount + "p-" + run;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        Map<String, String> attackAt = new LinkedHashMap<>();
        for (int seat = 2; seat <= playerCount; seat++) {
            String attacker = ATTACKERS.get(seat - 2);
            objects.add(obj("P1", attacker));
            attackAt.put(attacker, "P" + seat);
            objects.add(obj("P" + seat, "Wall of Stone"));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        Map<String, UUID> ids = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> ids.put(pid, player.getId()));
        List<String> blockers = new ArrayList<>();
        for (int step = 0; step < 200 && game.getStep().getType() != PhaseStep.COMBAT_DAMAGE; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = started.session().legalActionsPayload();
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "declare_attacker" -> {
                    String attacker = attackerName(legal);
                    XmageActualCardCorpusTest.submit(started, tag + "-attack-" + attacker,
                            attackOption(legal, ids.get(attackAt.get(attacker))));
                }
                case "declare_blocker" -> {
                    blockers.add(actor);
                    XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + actor);
                }
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor);
            }
        }
        assertEquals(PhaseStep.COMBAT_DAMAGE, game.getStep().getType(), "combat reached damage");
        return blockers;
    }

    private static String attackerName(JsonObject legal) {
        String name = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            String candidate = meta.get("name").getAsString();
            assertTrue(name == null || name.equals(candidate), "one attacker per decision");
            name = candidate;
        }
        assertNotNull(name);
        return name;
    }

    private static JsonObject attackOption(JsonObject legal, UUID defender) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta.has("defender_id") && defender.toString().equals(meta.get("defender_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        fail("attack at " + defender + " not offered: " + legal);
        return null;
    }

    private static XmageNativeStateRestoration.RequestedObject obj(String pid, String name) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, mage.constants.Zone.BATTLEFIELD, false);
    }
}

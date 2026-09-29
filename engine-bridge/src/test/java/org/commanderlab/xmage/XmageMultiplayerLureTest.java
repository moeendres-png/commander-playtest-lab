package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.game.combat.CombatGroup;
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
 * "Must be blocked by all" in a split attack at 3–6 players, with actual cards
 * on the full-game lane (CR 509.1c, 802.4a).
 *
 * <p>P1 attacks P2 with Prized Unicorn (Oracle: "All creatures able to block
 * Prized Unicorn do so.") and P3 with Grizzly Bears. P2 controls Wall of Stone
 * and Hill Giant. P3 controls Craw Wurm. From 4P on, the unattacked P4 controls
 * an Air Elemental.</p>
 *
 * <ul>
 *   <li>Both of P2's creatures block the Unicorn. P2 has no alternative, so the
 *       engine declares the required blocks and P2 is owed no decision.</li>
 *   <li>The requirement does not reach other players' creatures (802.4a). P3 is
 *       asked only about the Bears attacking it, may decline, and takes 2.</li>
 *   <li>The unattacked P4 is never asked.</li>
 * </ul>
 */
class XmageMultiplayerLureTest {

    private static final String UNICORN = "Prized Unicorn";
    private static final String BEARS = "Grizzly Bears";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void theLureBindsOnlyTheAttackedPlayersCreatures(int playerCount) {
        String tag = "lure-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", UNICORN));
        objects.add(obj("P1", BEARS));
        objects.add(obj("P2", "Wall of Stone"));
        objects.add(obj("P2", "Hill Giant"));
        objects.add(obj("P3", "Craw Wurm"));
        if (playerCount >= 4) {
            objects.add(obj("P4", "Air Elemental"));
        }
        Map<String, String> attackAt = Map.of(UNICORN, "P2", BEARS, "P3");
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        Map<String, UUID> ids = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> ids.put(pid, player.getId()));

        List<String> blockAsks = new ArrayList<>();
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
                    List<String> labels = new ArrayList<>();
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        labels.add(element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
                    }
                    blockAsks.add(actor + ":" + labels);
                    XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + actor);
                }
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor);
            }
        }
        assertEquals(List.of("P3:[Craw Wurm blocks Grizzly Bears]"), blockAsks,
                "only P3 has a discretionary block, and only against the creature attacking it");
        Map<String, List<String>> blockedBy = new LinkedHashMap<>();
        for (CombatGroup group : game.getCombat().getGroups()) {
            List<String> blockers = new ArrayList<>();
            group.getBlockers().forEach(id -> blockers.add(game.getPermanent(id).getName()));
            blockers.sort(String::compareTo);
            blockedBy.put(game.getPermanent(group.getAttackers().get(0)).getName(), blockers);
        }
        assertEquals(List.of("Hill Giant", "Wall of Stone"), blockedBy.get(UNICORN),
                "every creature of P2 able to block the Unicorn blocks it");
        assertEquals(List.of(), blockedBy.get(BEARS), "P3 declined; the lure does not bind P3's creature");
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

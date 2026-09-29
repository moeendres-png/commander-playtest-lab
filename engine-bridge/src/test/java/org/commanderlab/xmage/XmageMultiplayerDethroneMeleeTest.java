package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.counters.CounterType;
import mage.game.Game;
import mage.game.permanent.Permanent;
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
 * Attack-target keywords that count or compare players, at 3–6 players, with
 * actual cards on the full-game lane.
 *
 * <p>Dethrone (CR 702.105a): "Whenever this creature attacks the player with
 * the most life or tied for most life, put a +1/+1 counter on it." Melee (CR
 * 702.121a): "Whenever this creature attacks, it gets +1/+1 until end of turn
 * for each opponent you attacked with a creature this combat."</p>
 *
 * <p>P1 controls Marchesa's Emissary and Grenzo's Cutthroat (dethrone) and Wings
 * of the Guard (melee).</p>
 *
 * <ul>
 *   <li>Lava Spike first hits P2 (37). The Emissary attacks P2 and gets no counter.
 *       The Cutthroat attacks P3, who is tied for most life at 40 with P1 and the
 *       rest, and gets one counter. Wings attacks PN at 4P+, and P3 at 3P. It gets
 *       +1/+1 per distinct opponent attacked: 3, or 2 at 3P.</li>
 *   <li>P1 casts Chaplain's Blessing first (45). No opponent has the most life, so
 *       the Cutthroat attacking P2 and the Emissary attacking P3 get no counters.
 *       The controller's own life counts.</li>
 * </ul>
 */
class XmageMultiplayerDethroneMeleeTest {

    private static final String EMISSARY = "Marchesa's Emissary";
    private static final String CUTTHROAT = "Grenzo's Cutthroat";
    private static final String WINGS = "Wings of the Guard";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void dethroneComparesAgainstTheMostLifeAtTheTableAndMeleeCountsDistinctOpponents(int playerCount) {
        String pn = "P" + playerCount;
        String wingsAt = playerCount == 3 ? "P3" : pn;
        int distinct = playerCount == 3 ? 2 : 3;
        Map<String, String> attackAt = new LinkedHashMap<>();
        attackAt.put(EMISSARY, "P2");
        attackAt.put(CUTTHROAT, "P3");
        attackAt.put(WINGS, wingsAt);
        Snapshot snap = run("dethrone-spike-" + playerCount + "p", playerCount, "Lava Spike", "Mountain", attackAt);

        assertEquals(0, snap.counters.get(EMISSARY), "P2 (37) is not the player with the most life");
        assertEquals(1, snap.counters.get(CUTTHROAT), "P3 (40) is tied for the most life");
        assertEquals(0, snap.counters.get(WINGS));
        assertEquals(1 + distinct, snap.powerInCombat.get(WINGS),
                "melee: +1/+1 for each distinct opponent attacked this combat");
        Map<String, Integer> expected = new LinkedHashMap<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            expected.put("P" + seat, 40);
        }
        expected.put("P2", 40 - 3 - 2);
        expected.merge("P3", -2, Integer::sum);
        expected.merge(wingsAt, -(1 + distinct), Integer::sum);
        assertEquals(expected, snap.life, "combat damage matches the dethrone counter and the melee bonus");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void dethroneDoesNotTriggerWhenTheAttackingPlayerAloneHasTheMostLife(int playerCount) {
        Map<String, String> attackAt = new LinkedHashMap<>();
        attackAt.put(CUTTHROAT, "P2");
        attackAt.put(EMISSARY, "P3");
        attackAt.put(WINGS, "P2");
        Snapshot snap = run("dethrone-blessing-" + playerCount + "p", playerCount, "Chaplain's Blessing", "Plains",
                attackAt);

        assertEquals(45, snap.life.get("P1"));
        assertEquals(0, snap.counters.get(CUTTHROAT), "P1 at 45 has the most life, not P2 at 40");
        assertEquals(0, snap.counters.get(EMISSARY), "P1 at 45 has the most life, not P3 at 40");
        assertEquals(3, snap.powerInCombat.get(WINGS), "melee: two distinct opponents attacked");
        assertEquals(40 - 1 - 3, snap.life.get("P2"));
        assertEquals(40 - 2, snap.life.get("P3"));
    }

    private record Snapshot(Map<String, Integer> counters, Map<String, Integer> powerInCombat,
            Map<String, Integer> life) {
    }

    private static Snapshot run(String tag, int playerCount, String spell, String land,
            Map<String, String> attackAt) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", spell));
        objects.add(obj("bf", "P1", land));
        for (String creature : attackAt.keySet()) {
            objects.add(obj("bf", "P1", creature));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        Map<String, UUID> ids = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> ids.put(pid, player.getId()));

        XmageActualCardCorpusTest.cast(started, tag + "-cast", spell);
        String manaLabel = land + " — {T}: Add {" + ("Mountain".equals(land) ? "R" : "W") + "}.";
        XmageActualCardCorpusTest.resolveAll(started, tag + "-spell", manaLabel, (cls, step) -> {
            if ("target".equals(cls)) {
                XmageActualCardCorpusTest.submit(started, tag + "-target",
                        XmageActualCardCorpusTest.playerTarget(started, "P2"));
                return true;
            }
            return false;
        });

        Map<String, Integer> counters = new LinkedHashMap<>();
        Map<String, Integer> power = new LinkedHashMap<>();
        List<String> declared = new ArrayList<>();
        for (int step = 0; step < 200; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = started.session().legalActionsPayload();
            PhaseStep phaseStep = game.getStep().getType();
            if (phaseStep == PhaseStep.DECLARE_BLOCKERS && power.isEmpty()) {
                for (String creature : attackAt.keySet()) {
                    Permanent permanent = permanent(game, started, creature);
                    assertTrue(permanent.isAttacking(), creature + " attacks");
                    assertEquals(ids.get(attackAt.get(creature)), game.getCombat().getDefenderId(permanent.getId()),
                            creature + " attacks " + attackAt.get(creature));
                    counters.put(creature, permanent.getCounters(game).getCount(CounterType.P1P1));
                    power.put(creature, permanent.getPower().getValue());
                }
            }
            if (phaseStep == PhaseStep.END_COMBAT) {
                break;
            }
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "declare_attacker" -> {
                    assertEquals("P1", actor);
                    String attacker = attackerName(legal);
                    declared.add(attacker);
                    UUID defender = ids.get(attackAt.get(attacker));
                    assertNotNull(defender, "unplanned attacker " + attacker);
                    XmageActualCardCorpusTest.submit(started, tag + "-attack-" + step, attackOption(legal, defender));
                }
                case "trigger_order" -> {
                    // P1's simultaneous attack triggers: an explicit, label-scripted order
                    // (the dethrone and melee triggers do not interact).
                    JsonObject first = null;
                    String firstLabel = null;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        String label = element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString();
                        if (firstLabel == null || label.compareTo(firstLabel) < 0) {
                            firstLabel = label;
                            first = element.getAsJsonObject();
                        }
                    }
                    XmageActualCardCorpusTest.submit(started, tag + "-order-" + step, first);
                }
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor + " at " + phaseStep);
            }
        }
        assertEquals(attackAt.keySet().stream().sorted().toList(), declared.stream().sorted().toList(),
                "each creature was asked exactly once");
        assertEquals(attackAt.size(), counters.size(), "combat snapshot taken");
        Map<String, Integer> life = new LinkedHashMap<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            life.put("P" + seat, started.seats().get("P" + seat).getLife());
        }
        return new Snapshot(counters, power, life);
    }

    private static Permanent permanent(Game game, XmageActualCardCorpusTest.Started started, String name) {
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(started.seats().get("P1").getId())) {
            if (name.equals(permanent.getName())) {
                return permanent;
            }
        }
        fail(name + " not on P1's battlefield");
        return null;
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

    private static XmageNativeStateRestoration.RequestedObject obj(String zoneTag, String pid, String name) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}

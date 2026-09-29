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
 * A "blocks this turn if able" requirement in a split attack at 3–6 players,
 * with actual cards on the full-game lane (CR 509.1c, 802.4a).
 *
 * <p>P1 casts Culling Mark (Oracle: "Target creature blocks this turn if
 * able.") on P3's Hill Giant. P1 then attacks P2 with Grizzly Bears and P3 with
 * Air Elemental (flying).</p>
 *
 * <p>The Hill Giant can block neither attacker. It can't block the Bears, which
 * attacks another player (802.4a), and it can't block the flying Elemental.
 * So the requirement imposes nothing (509.1c: requirements are obeyed only as
 * far as possible without violating restrictions). The Giant does not block,
 * and combat damage is dealt: P2 takes 2 and P3 takes 4.</p>
 *
 * <p>F-28: on the pinned engine, {@code Combat.checkBlockRequirementsAfter} asks
 * {@code Permanent.canBlock}, which checks only that the attacker is an
 * opponent's, whether the Giant could block. So it keeps demanding a block
 * of the Bears that the engine itself rejects, and block declaration loops
 * forever on the engine thread without reaching the lane. The fix is in the
 * XMage fork. This test is enabled by the repin to a candidate that contains it.</p>
 */
class XmageMultiplayerForcedBlockTest {

    private static final String MARK = "Culling Mark";
    private static final String GIANT = "Hill Giant";
    private static final String BEARS = "Grizzly Bears";
    private static final String ELEMENTAL = "Air Elemental";

    @Disabled("F-28: engine fix moeendres-png/mage#27; enabled by the repin to a candidate containing it")
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void aForcedBlockerThatCanOnlyReachAnotherPlayersAttackerDoesNotDeadlockCombat(int playerCount) {
        // A block-requirement livelock spins on the engine thread without ever reaching the
        // external decision surface; the session's bounded decision wait then reports no
        // pending decision, and the test fails with the engine thread's stack.
        String tag = "forced-block-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", MARK, 0));
        for (int index = 0; index < 3; index++) {
            objects.add(obj("bf", "P1", "Forest", index));
        }
        objects.add(obj("bf", "P1", BEARS, 0));
        objects.add(obj("bf", "P1", ELEMENTAL, 0));
        objects.add(obj("bf", "P3", GIANT, 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();
        Map<String, UUID> ids = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> ids.put(pid, player.getId()));
        Map<String, String> attackAt = Map.of(BEARS, "P2", ELEMENTAL, "P3");

        XmageActualCardCorpusTest.cast(started, tag + "-mark", MARK);
        XmageActualCardCorpusTest.resolveAll(started, tag + "-mark", "Forest — {T}: Add {G}.", (cls, step) -> {
            if ("target".equals(cls)) {
                XmageActualCardCorpusTest.chooseByExactName(started, tag + "-mark-giant", GIANT, 1);
                return true;
            }
            return false;
        });

        List<String> blockDecisions = new ArrayList<>();
        for (int step = 0; step < 200 && game.getStep().getType() != PhaseStep.END_COMBAT; step++) {
            if (started.session().pendingDecisionPayload().get("decision").isJsonNull()) {
                fail("no decision reached the lane at " + game.getStep().getType() + " (F-28 livelock?)"
                        + engineStacks());
            }
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
                    blockDecisions.add(actor + ":" + labels);
                    fail("the Hill Giant has no legal block, so no block may be offered: " + blockDecisions);
                }
                default -> fail("[" + tag + "] unexpected " + cls + " for " + actor + " at " + game.getStep().getType());
            }
        }
        assertEquals(PhaseStep.END_COMBAT, game.getStep().getType(), "combat completed");
        assertTrue(blockDecisions.isEmpty());
        Map<String, Integer> expected = new LinkedHashMap<>();
        ids.keySet().forEach(pid -> expected.put(pid, 40));
        expected.put("P2", 38);
        expected.put("P3", 36);
        Map<String, Integer> life = new LinkedHashMap<>();
        started.seats().forEach((pid, player) -> life.put(pid, player.getLife()));
        assertEquals(expected, life, "nothing was blocked");
    }

    /** Stacks of engine threads currently inside combat code (evidence for a livelock). */
    private static String engineStacks() {
        StringBuilder dump = new StringBuilder();
        for (Map.Entry<Thread, StackTraceElement[]> entry : Thread.getAllStackTraces().entrySet()) {
            if (java.util.Arrays.toString(entry.getValue()).contains("mage.game.combat")) {
                dump.append("\nTHREAD ").append(entry.getKey().getName()).append(' ').append(entry.getKey().getState());
                for (int index = 0; index < Math.min(8, entry.getValue().length); index++) {
                    dump.append("\n  at ").append(entry.getValue()[index]);
                }
            }
        }
        return dump.toString();
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

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}

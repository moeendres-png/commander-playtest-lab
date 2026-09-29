package org.commanderlab.xmage;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Rules RNG for random player selection at 4P and 5P, with an actual card on
 * the full-game lane.
 *
 * <p>P1 controls Vial Smasher the Fierce (Oracle: "Whenever you cast your first
 * spell each turn, choose an opponent at random. Vial Smasher deals damage
 * equal to that spell's mana value to that player or a planeswalker that
 * player controls."). P1 casts Raging Goblin (mana value 1), so exactly one
 * opponent, chosen at random, loses 1 life.</p>
 *
 * <ul>
 *   <li>The choice is Rules randomness. Two runs with the same explicit seed
 *       choose the same opponent (AGENTS.md §5).</li>
 *   <li>Only opponents are chosen, never P1, and no pilot decision is invented
 *       for the random choice.</li>
 *   <li>Across seeds, more than one opponent is chosen, so the seed really
 *       drives the choice (non-vacuity).</li>
 * </ul>
 */
class XmageMultiplayerRandomOpponentTest {

    private static final String SMASHER = "Vial Smasher the Fierce";
    private static final String GOBLIN = "Raging Goblin";
    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";
    private static final long[] SEEDS = {11L, 22L, 33L, 44L, 55L, 66L, 77L, 88L};

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void randomOpponentIsReproducibleFromTheRulesSeed(int playerCount) {
        Map<Long, String> chosenBySeed = new LinkedHashMap<>();
        for (long seed : SEEDS) {
            String first = chosenOpponent(playerCount, seed, "a");
            String second = chosenOpponent(playerCount, seed, "b");
            assertEquals(first, second, "seed " + seed + ": twin runs choose the same opponent");
            assertNotEquals("P1", first, "only an opponent may be chosen");
            chosenBySeed.put(seed, first);
        }
        Set<String> distinct = new LinkedHashSet<>(chosenBySeed.values());
        assertTrue(distinct.size() >= 2,
                "the seed drives the random choice (non-vacuous): " + chosenBySeed);
    }

    private static String chosenOpponent(int playerCount, long seed, String run) {
        String tag = "vial-" + playerCount + "p-" + seed;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("bf", "P1", SMASHER, mage.constants.Zone.BATTLEFIELD));
        objects.add(obj("bf", "P1", "Mountain", mage.constants.Zone.BATTLEFIELD));
        objects.add(obj("hand", "P1", GOBLIN, mage.constants.Zone.HAND));
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(
                tag, playerCount, objects, Map.of(), 0, seed);
        XmageActualCardCorpusTest.cast(started, tag + "-" + run + "-cast", GOBLIN);
        XmageActualCardCorpusTest.resolveAll(started, tag + "-" + run, MOUNTAIN_LABEL,
                XmageActualCardCorpusTest.NONE);
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", GOBLIN));

        String chosen = null;
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            int life = started.seats().get(pid).getLife();
            if (life != 40) {
                assertEquals(39, life, pid + " takes damage equal to the mana value");
                assertTrue(chosen == null, "exactly one player is damaged");
                chosen = pid;
            }
        }
        assertTrue(chosen != null, "Vial Smasher dealt its damage");
        return chosen;
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, mage.constants.Zone zone) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, zone, false);
    }
}

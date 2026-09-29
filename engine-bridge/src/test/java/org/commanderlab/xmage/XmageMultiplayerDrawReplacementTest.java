package org.commanderlab.xmage;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * A draw replacement controlled by a non-active player, with actual cards at
 * 3–5 players on the full-game lane.
 *
 * <p>P3 controls Notion Thief (Oracle: "If an opponent would draw a card except
 * the first one they draw in each of their draw steps, instead that player
 * skips that draw and you draw a card."). P1 casts Wheel of Fortune (Oracle:
 * "Each player discards their hand, then draws seven cards.").</p>
 *
 * <ul>
 *   <li>Every opponent of P3, the caster included, skips all seven draws, and
 *       P3 draws one card for each skipped draw.</li>
 *   <li>P3's own seven draws are normal.</li>
 *   <li>So P3 ends with 7 × N cards in hand and everyone else with 0.</li>
 * </ul>
 */
class XmageMultiplayerDrawReplacementTest {

    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5})
    void opponentsDrawsAreRedirectedToTheThiefController(int playerCount) {
        String tag = "notion-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", "Wheel of Fortune", 0));
        for (int index = 0; index < 3; index++) {
            objects.add(obj("bf", "P1", "Mountain", index));
        }
        objects.add(obj("bf", "P3", "Notion Thief", 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);

        XmageActualCardCorpusTest.cast(started, tag + "-wheel", "Wheel of Fortune");
        XmageActualCardCorpusTest.resolveAll(started, tag, MOUNTAIN_LABEL, XmageActualCardCorpusTest.NONE);

        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            int expected = "P3".equals(pid) ? 7 * playerCount : 0;
            assertEquals(expected, started.seats().get(pid).getHand().size(),
                    pid + ": opponents' draws are replaced by draws for P3");
        }
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P3", "Notion Thief"));
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}

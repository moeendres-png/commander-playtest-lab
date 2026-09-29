package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

/**
 * Undaunted (CR 702.125a) at 3–6 players, with an actual card on the full-game
 * lane.
 *
 * <p>Sublime Exhalation (Oracle: "{6}{W} Sorcery. Undaunted (This spell costs
 * {1} less to cast for each opponent.) Destroy all creatures.") costs
 * {7−N}{W} at N players. P1 has exactly 8−N Plains. Every player controls a
 * Grizzly Bears.</p>
 *
 * <ul>
 *   <li>The engine asks for the reduced cost, and the spell resolves and
 *       destroys every creature.</li>
 *   <li>With one Plains fewer, the engine does not offer the cast at all.</li>
 * </ul>
 */
class XmageMultiplayerUndauntedTest {

    private static final String EXHALATION = "Sublime Exhalation";
    private static final String PLAINS_LABEL = "Plains — {T}: Add {W}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void theCostIsReducedByOneForEachOpponent(int playerCount) {
        String tag = "undaunted-" + playerCount + "p";
        int plains = 8 - playerCount;
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, board(playerCount, plains));
        XmageActualCardCorpusTest.cast(started, tag + "-cast", EXHALATION);
        assertEquals("mana_payment", XmageActualCardCorpusTest.decisionClass(started));
        String unpaid = started.session().pendingDecisionPayload().getAsJsonObject("decision")
                .getAsJsonObject("context").get("unpaid_mana").getAsString();
        assertEquals("{" + (plains - 1) + "}{W}", unpaid,
                "{6}{W} minus {1} for each of the " + (playerCount - 1) + " opponents");
        XmageActualCardCorpusTest.resolveAll(started, tag, PLAINS_LABEL, (cls, step) -> false);
        for (int seat = 1; seat <= playerCount; seat++) {
            assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, "P" + seat, "Grizzly Bears"));
            assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P" + seat, "Grizzly Bears"));
        }
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P1", EXHALATION));
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void oneManaShortOfTheReducedCostIsNotOffered(int playerCount) {
        String tag = "undaunted-short-" + playerCount + "p";
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, board(playerCount, 7 - playerCount));
        for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
            String label = element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString();
            assertFalse(label.startsWith(EXHALATION), "unaffordable even with undaunted: " + label);
        }
    }

    private static List<XmageNativeStateRestoration.RequestedObject> board(int playerCount, int plains) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", EXHALATION, 0));
        for (int index = 0; index < plains; index++) {
            objects.add(obj("bf", "P1", "Plains", index));
        }
        for (int seat = 1; seat <= playerCount; seat++) {
            objects.add(obj("bf", "P" + seat, "Grizzly Bears", 0));
        }
        return objects;
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}

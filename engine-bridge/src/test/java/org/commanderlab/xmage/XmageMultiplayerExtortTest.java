package org.commanderlab.xmage;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Extort in multiplayer (CR 702.101a), with an actual card on the full-game
 * lane.
 *
 * <p>P1 controls Syndic of Tithes (Oracle: "Extort (Whenever you cast a spell,
 * you may pay {W/B}. If you do, each opponent loses 1 life and you gain that
 * much life.)") and casts Raging Goblin.</p>
 *
 * <ul>
 *   <li>Only P1 is asked, through the external surface, whether to pay.</li>
 *   <li>If P1 pays the hybrid {W/B} (with a Plains): each of the N−1
 *       opponents loses 1, and P1 gains the total lost, N−1.</li>
 *   <li>If P1 declines: no life changes.</li>
 * </ul>
 */
class XmageMultiplayerExtortTest {

    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";
    private static final String PLAINS_LABEL = "Plains — {T}: Add {W}.";

    @ParameterizedTest(name = "{0} players, pays: {1}")
    @CsvSource({"3, true", "3, false", "4, true", "4, false", "5, true", "5, false", "6, true", "6, false"})
    void extortDrainsEachOpponentAndGainsTheTotal(int playerCount, boolean pays) {
        String tag = "extort-" + playerCount + "p-" + pays;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("bf", "P1", "Syndic of Tithes", 0));
        objects.add(obj("bf", "P1", "Mountain", 0));
        objects.add(obj("bf", "P1", "Plains", 0));
        objects.add(obj("bf", "P1", "Plains", 1));
        objects.add(obj("hand", "P1", "Raging Goblin", 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);

        List<String> asked = new ArrayList<>();
        XmageActualCardCorpusTest.cast(started, tag + "-goblin", "Raging Goblin");
        XmageActualCardCorpusTest.resolveAll(started, tag, null, (cls, step) -> {
            String actor = XmageActualCardCorpusTest.actorPid(started);
            switch (cls) {
                case "mana_payment" -> {
                    String prompt = started.session().pendingDecisionPayload().getAsJsonObject("decision")
                            .get("prompt").getAsString();
                    boolean extortCost = prompt.contains("W/B") || prompt.contains("Syndic");
                    XmageActualCardCorpusTest.payOneFromRestoredMana(started, tag + "-pay-" + step,
                            List.of(extortCost ? "Plains" : "Mountain"),
                            Set.of(extortCost ? PLAINS_LABEL : MOUNTAIN_LABEL));
                }
                case "choose_use" -> {
                    String prompt = started.session().pendingDecisionPayload().getAsJsonObject("decision")
                            .get("prompt").getAsString().toLowerCase(Locale.ROOT);
                    asked.add(actor + ":" + prompt);
                    XmageActualCardCorpusTest.submit(started, tag + "-use-" + step,
                            XmageActualCardCorpusTest.labelled(started, pays ? "Yes" : "No"));
                }
                default -> {
                    return false;
                }
            }
            return true;
        });

        assertEquals(1, asked.size(), "one extort decision: " + asked);
        assertTrue(asked.get(0).startsWith("P1:"), "only the extort controller decides: " + asked);
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", "Raging Goblin"));
        int drained = pays ? playerCount - 1 : 0;
        assertEquals(40 + drained, started.seats().get("P1").getLife(),
                "P1 gains the total life lost (" + drained + ")");
        for (int seat = 2; seat <= playerCount; seat++) {
            assertEquals(pays ? 39 : 40, started.seats().get("P" + seat).getLife(), "P" + seat);
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

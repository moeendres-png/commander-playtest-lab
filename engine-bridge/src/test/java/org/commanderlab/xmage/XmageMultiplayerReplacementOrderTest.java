package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * CR 616.1 with actual cards at 3–6 players on the full-game lane: when
 * replacement effects controlled by different players compete for one event,
 * the affected player chooses the order, even when that player is neither
 * active nor the controller of either effect's source.
 *
 * <p>P1 casts Healing Salve ("Target player gains 3 life."), targeting P2.
 * P2 controls Boon Reflection ("If you would gain life, you gain twice that
 * much life instead."). P3 controls Tainted Remedy ("If an opponent would gain
 * life, that player loses that much life instead."). The official Tainted
 * Remedy ruling says the player who would gain life chooses the order:</p>
 *
 * <ul>
 *   <li>Tainted Remedy first: "gain 3" becomes "lose 3", and Boon Reflection
 *       no longer applies. P2 ends at 37.</li>
 *   <li>Boon Reflection first: "gain 6", which Tainted Remedy turns into
 *       "lose 6". P2 ends at 34.</li>
 * </ul>
 *
 * <p>Only P2 is asked, through the external surface, offered exactly those two
 * effects, and nobody else's life changes.</p>
 */
class XmageMultiplayerReplacementOrderTest {

    private static final String PLAINS_LABEL = "Plains — {T}: Add {W}.";

    @ParameterizedTest(name = "{0} players, {1} first")
    @CsvSource({
            "3, Tainted Remedy, 37", "3, Boon Reflection, 34",
            "4, Tainted Remedy, 37", "4, Boon Reflection, 34",
            "5, Tainted Remedy, 37", "5, Boon Reflection, 34",
            "6, Tainted Remedy, 37", "6, Boon Reflection, 34"})
    void theAffectedPlayerOrdersCompetingReplacementEffects(
            int playerCount, String first, int expectedLife) {
        String tag = "repl-" + playerCount + "p-" + first.charAt(0);
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", "Healing Salve", mage.constants.Zone.HAND));
        objects.add(obj("bf", "P1", "Plains", mage.constants.Zone.BATTLEFIELD));
        objects.add(obj("bf", "P2", "Boon Reflection", mage.constants.Zone.BATTLEFIELD));
        objects.add(obj("bf", "P3", "Tainted Remedy", mage.constants.Zone.BATTLEFIELD));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);

        List<String> orderingAsks = new ArrayList<>();
        XmageActualCardCorpusTest.cast(started, tag + "-cast", "Healing Salve");
        XmageActualCardCorpusTest.resolveAll(started, tag, PLAINS_LABEL, (cls, step) -> {
            switch (cls) {
                case "mode" -> XmageActualCardCorpusTest.submit(started, tag + "-mode",
                        XmageActualCardCorpusTest.labelled(started, "gains 3 life"));
                case "target" -> XmageActualCardCorpusTest.submit(started, tag + "-target",
                        XmageActualCardCorpusTest.playerTarget(started, "P2"));
                case "replacement_effect" -> {
                    String actor = XmageActualCardCorpusTest.actorPid(started);
                    List<String> offered = new ArrayList<>();
                    for (JsonElement element : started.session().legalActionsPayload()
                            .getAsJsonArray("actions")) {
                        String label = element.getAsJsonObject().getAsJsonObject("metadata")
                                .get("label").getAsString();
                        offered.add(label.substring(0, label.indexOf(" [")));
                    }
                    offered.sort(String::compareTo);
                    assertEquals(List.of("Boon Reflection", "Tainted Remedy"), offered,
                            "both competing effects are offered");
                    orderingAsks.add(actor);
                    XmageActualCardCorpusTest.submit(started, tag + "-order",
                            XmageActualCardCorpusTest.labelled(started, first));
                }
                default -> {
                    return false;
                }
            }
            return true;
        });

        assertEquals(List.of("P2"), orderingAsks,
                "CR 616.1: only the player who would gain life orders the effects");
        assertEquals(expectedLife, started.seats().get("P2").getLife(),
                first + " applied first");
        for (int seat = 1; seat <= playerCount; seat++) {
            if (seat != 2) {
                assertEquals(40, started.seats().get("P" + seat).getLife(), "P" + seat);
            }
        }
        assertTrue(XmageActualCardCorpusTest.inGraveyard(started, "P1", "Healing Salve") == 1);
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, mage.constants.Zone zone) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, zone, false);
    }
}

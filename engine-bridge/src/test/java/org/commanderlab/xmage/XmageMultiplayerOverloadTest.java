package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Overload in multiplayer (CR 702.96a/b), with an actual card on the full-game
 * lane.
 *
 * <p>P1 casts Cyclonic Rift (Oracle: "Return target nonland permanent you don't
 * control to its owner's hand. Overload {6}{U}") with overload. Every opponent
 * controls a Grizzly Bears, a hexproof Slippery Bogle and a Forest; P1 controls
 * a Grizzly Bears of its own.</p>
 *
 * <ul>
 *   <li>Both casting modes are engine-offered.</li>
 *   <li>Overloaded, the spell targets nothing (702.96b). Every opponent's
 *       nonland permanent, the hexproof Bogles included, returns to its owner's
 *       hand.</li>
 *   <li>Lands stay, and P1's own Bears stays ("you don't control").</li>
 * </ul>
 */
class XmageMultiplayerOverloadTest {

    private static final String RIFT = "Cyclonic Rift";
    private static final String ISLAND_LABEL = "Island — {T}: Add {U}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void overloadedRiftReturnsEveryOpponentsNonlandPermanent(int playerCount) {
        String tag = "rift-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", RIFT, 0));
        for (int index = 0; index < 7; index++) {
            objects.add(obj("bf", "P1", "Island", index));
        }
        objects.add(obj("bf", "P1", "Grizzly Bears", 0));
        for (int seat = 2; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            objects.add(obj("bf", pid, "Grizzly Bears", 0));
            objects.add(obj("bf", pid, "Slippery Bogle", 0));
            objects.add(obj("bf", pid, "Forest", 0));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);

        JsonObject overload = null;
        int riftOffers = 0;
        for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
            String label = element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString();
            if (label.startsWith(RIFT + " — Cast")) {
                riftOffers++;
                if (label.contains("with overload")) {
                    overload = element.getAsJsonObject();
                }
            }
        }
        assertEquals(2, riftOffers, "normal and overloaded casts are both engine-offered");
        assertNotNull(overload, "overloaded cast offered");
        XmageFullGameTaxExecutionTest.submit(started.session(), tag + "-overload", overload);
        XmageActualCardCorpusTest.resolveAll(started, tag, ISLAND_LABEL, (cls, step) -> {
            assertTrue(!"target".equals(cls), "an overloaded spell chooses no targets");
            return false;
        });

        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", "Grizzly Bears"),
                "P1's own Bears stays");
        for (int seat = 2; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, pid, "Grizzly Bears"), pid);
            assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, pid, "Slippery Bogle"),
                    pid + "'s hexproof Bogle is returned too (no targeting)");
            assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, pid, "Forest"),
                    pid + "'s land stays");
            long returned = started.seats().get(pid).getHand().getCards(started.session().restorationGame())
                    .stream().filter(card -> card.getName().equals("Grizzly Bears")
                            || card.getName().equals("Slippery Bogle")).count();
            assertEquals(2, returned, pid + "'s permanents returned to its owner's hand");
        }
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P1", RIFT));
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}

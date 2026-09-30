package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * F-36: the objects a decision offers come in a twin-stable order, never in native-id
 * order (ids are random per game).
 *
 * <p>P1 (Rograkh and Tana, the Bloodsower, with a library of Mountains and Forests)
 * activates Terramorphic Expanse ("{T}, Sacrifice: Search your library for a basic land
 * card, put it onto the battlefield tapped, then shuffle."). The search offers
 * the library's basic lands in library order, top first. The searching player sees
 * that order, and a card's position is what distinguishes identical cards.
 * The pilot takes the first Mountain offered. Two games with the same Rules seed then
 * end with the same library order.</p>
 *
 * <p>Before the fix the options came in UUID order. "The first Mountain" was a
 * different card in each game, so the seeded shuffle started from a different
 * sequence and the libraries, and with them the games, diverged.</p>
 */
class XmageFullGameStableOptionOrderTest {

    private static final String EXPANSE = "Terramorphic Expanse";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 4})
    void aLibrarySearchOffersLibraryOrderAndReplaysTheSameShuffle(int playerCount) {
        List<String> first = searchAndShuffle(playerCount, "a");
        List<String> second = searchAndShuffle(playerCount, "b");
        assertEquals(first, second, "same seed and same semantic choice: same library afterwards");
    }

    private static List<String> searchAndShuffle(int playerCount, String run) {
        String tag = "stable-order-" + playerCount + "p-" + run;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject("obj:bf-P1-0-Expanse", EXPANSE, "P1", "P1",
                mage.constants.Zone.BATTLEFIELD, false));
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(
                tag, playerCount, objects, Map.of("P1", "Tana, the Bloodsower"), 40, 97L);
        mage.players.Player p1 = started.seats().get("P1");
        mage.game.Game game = started.session().restorationGame();
        XmageActualCardCorpusTest.submit(started, tag + "-crack",
                XmageActualCardCorpusTest.labelled(started, EXPANSE + " — {T}, Sacrifice"));
        boolean searched = false;
        for (int step = 0; step < 40 && !searched; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            if ("priority".equals(cls)) {
                XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                continue;
            }
            List<String> offeredIds = new ArrayList<>();
            JsonObject firstMountain = null;
            for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
                JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
                offeredIds.add(meta.getAsJsonObject("xmage_option_metadata").get("object_id").getAsString());
                if (firstMountain == null && meta.get("label").getAsString().equals("Mountain")) {
                    firstMountain = element.getAsJsonObject();
                }
            }
            List<String> libraryOrder = new ArrayList<>();
            for (UUID id : p1.getLibrary().getCardList()) {
                if (offeredIds.contains(id.toString())) {
                    libraryOrder.add(id.toString());
                }
            }
            assertEquals(libraryOrder, offeredIds, "the search offers the library's basics in library order");
            assertTrue(firstMountain != null, "a Mountain is offered");
            XmageActualCardCorpusTest.submit(started, tag + "-take", firstMountain);
            searched = true;
        }
        assertTrue(searched, "the search decision was reached");
        XmageActualCardCorpusTest.resolveAll(started, tag + "-resolve", null, (cls, step) -> false);
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", "Mountain"));
        List<String> names = new ArrayList<>();
        p1.getLibrary().getCards(game).forEach(card -> names.add(card.getName()));
        return names;
    }
}

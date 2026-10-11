package org.commanderlab.xmage;

import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

/**
 * #735: two permanents with the same name, controller, zone-change counter, P/T, tapped
 * state and damage (typically tokens) must still get a twin-stable order. Before the fix
 * their keys were equal and the order fell back to the native UUID, which is random per
 * game: in real-deck 5P seed 4 "Orc Army Token blocks Spirit Token" was a different Spirit
 * Token in each replay, and the games diverged.
 */
class XmageStableOrderSameNameTest {

    private static final String BEARS = "Grizzly Bears";

    @Test
    void sameNamedPermanentsAreOrderedByTimestampNotByNativeId() {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        for (int index = 0; index < 2; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P1-" + index + "-Bears", BEARS, "P1", "P1",
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start("stable-order-same-name", 4, objects);
        Game game = started.session().restorationGame();
        List<Permanent> bears = new ArrayList<>();
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents()) {
            if (BEARS.equals(permanent.getName())) {
                bears.add(permanent);
            }
        }
        assertEquals(2, bears.size(), "both Bears are on the battlefield");
        Permanent first = bears.get(0);
        Permanent second = bears.get(1);
        assertNotEquals(first.getCreateOrder(), second.getCreateOrder(),
                "the two Bears entered at different timestamps");

        assertNotEquals(XmageStableOrder.contentKey(first.getId(), game),
                XmageStableOrder.contentKey(second.getId(), game),
                "the content key tells the Bears apart without the native id");
        Permanent earlier = first.getCreateOrder() < second.getCreateOrder() ? first : second;
        assertEquals(earlier.getId(), sortedIds(game, first, second, false).get(0),
                "the earlier timestamp comes first");
        assertEquals(sortedIds(game, first, second, false), sortedIds(game, first, second, true),
                "the native id never decides the order");

        // Tokens made by one effect share one timestamp: battlefield order still decides.
        second.setCreateOrder(first.getCreateOrder());
        assertNotEquals(XmageStableOrder.contentKey(first.getId(), game),
                XmageStableOrder.contentKey(second.getId(), game),
                "same timestamp: battlefield order tells the Bears apart");
        assertEquals(sortedIds(game, first, second, false), sortedIds(game, first, second, true),
                "same timestamp: the native id still never decides the order");
    }

    /** The F-36 order, with the final native-id tie-break forward or reversed. */
    private static List<UUID> sortedIds(Game game, Permanent first, Permanent second, boolean reversedIds) {
        Comparator<UUID> ids = Comparator.comparing(UUID::toString);
        List<UUID> out = new ArrayList<>(List.of(second.getId(), first.getId()));
        out.sort(Comparator.comparing((UUID id) -> XmageStableOrder.objectKey(id, game))
                .thenComparing(id -> XmageStableOrder.contentKey(id, game))
                .thenComparing(reversedIds ? ids.reversed() : ids));
        return out;
    }
}

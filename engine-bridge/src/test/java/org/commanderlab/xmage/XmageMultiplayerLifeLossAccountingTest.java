package org.commanderlab.xmage;

import mage.constants.PhaseStep;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * "Life lost this way" accounting in multiplayer when one opponent's life
 * can't change, with actual cards at 3–6 players on the full-game lane.
 *
 * <p>On P1's turn, P2 casts Teferi's Protection ("your life total can't
 * change …"). P1 then destroys its own Kokusho, the Evening Star with Murder.
 * Kokusho's Oracle text: "When Kokusho dies, each opponent loses 5 life. You
 * gain life equal to the life lost this way."</p>
 *
 * <ul>
 *   <li>P2's life total can't change, so P2 loses nothing (official Teferi's
 *       Protection ruling: the life-loss part simply has no effect).</li>
 *   <li>Every other opponent loses 5.</li>
 *   <li>P1 gains exactly the life actually lost: 5 × (N − 2), not 5 × (N − 1).</li>
 * </ul>
 */
class XmageMultiplayerLifeLossAccountingTest {

    private static final String PLAINS_LABEL = "Plains — {T}: Add {W}.";
    private static final String SWAMP_LABEL = "Swamp — {T}: Add {B}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void kokushoGainsOnlyTheLifeActuallyLost(int playerCount) {
        String tag = "kokusho-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P2", "Teferi's Protection", 0));
        objects.add(obj("bf", "P1", "Kokusho, the Evening Star", 0));
        objects.add(obj("hand", "P1", "Murder", 0));
        for (int index = 0; index < 3; index++) {
            objects.add(obj("bf", "P2", "Plains", index));
            objects.add(obj("bf", "P1", "Swamp", index));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();

        boolean cast = false;
        for (int step = 0; step < 40 && !cast; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            if (!"priority".equals(cls)) {
                fail("unexpected decision " + cls + " for " + actor);
            }
            if ("P2".equals(actor)) {
                XmageActualCardCorpusTest.cast(started, tag + "-teferi", "Teferi's Protection");
                cast = true;
            } else {
                XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
            }
        }
        assertTrue(cast, "P2 got priority on P1's turn");
        XmageActualCardCorpusTest.resolveAll(started, tag + "-teferi", PLAINS_LABEL,
                XmageActualCardCorpusTest.NONE);
        assertEquals(PhaseStep.PRECOMBAT_MAIN, game.getStep().getType());

        XmageActualCardCorpusTest.cast(started, tag + "-murder", "Murder");
        XmageActualCardCorpusTest.resolveAll(started, tag + "-murder", SWAMP_LABEL, (cls, step) -> {
            if (!"target".equals(cls)) {
                return false;
            }
            XmageActualCardCorpusTest.chooseByExactName(started, tag + "-murder-target",
                    "Kokusho, the Evening Star", 1);
            return true;
        });
        assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, "P1", "Kokusho, the Evening Star"),
                "Kokusho died");

        assertEquals(40, started.seats().get("P2").getLife(), "P2's life total can't change");
        for (int seat = 3; seat <= playerCount; seat++) {
            assertEquals(35, started.seats().get("P" + seat).getLife(), "P" + seat + " loses 5");
        }
        assertEquals(40 + 5 * (playerCount - 2), started.seats().get("P1").getLife(),
                "P1 gains only the life actually lost");
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}

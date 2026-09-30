package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * F-35: two options the lane offered although choosing them could only fail, and the
 * failed execution aborted the whole game (XMAGE_ACTION_EXECUTION_FAILED). Found by
 * the full-game replay harness with real decks.
 *
 * <ul>
 *   <li>CR 700.2a: a mode that would be illegal (no legal targets) can't be chosen.
 *       Abrade ("Choose one — deal 3 damage to target creature; or destroy target
 *       artifact") with a creature but no artifact on the battlefield may only offer
 *       the creature mode.</li>
 *   <li>A mana ability with a mana cost of its own (Rakdos Signet: "{1}, {T}: Add
 *       {B}{R}") is offered only while that cost can be paid, and a {T} ability can't be
 *       funded by another {T} ability of the same permanent (Study Hall).</li>
 * </ul>
 */
class XmageFullGameIllegalOptionTest {

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 4})
    void aModeWithoutLegalTargetsIsNotOffered(int playerCount) {
        String tag = "f35-abrade-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", "Abrade", 0));
        objects.add(obj("bf", "P1", "Mountain", 0));
        objects.add(obj("bf", "P1", "Mountain", 1));
        objects.add(obj("bf", "P2", "Grizzly Bears", 0));
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageActualCardCorpusTest.cast(started, tag + "-cast", "Abrade");
        assertEquals("mode", XmageActualCardCorpusTest.decisionClass(started));
        assertEquals(List.of("{this} deals 3 damage to target creature."), labels(started),
                "CR 700.2a: the artifact mode has no legal target and can't be chosen");
        XmageActualCardCorpusTest.submit(started, tag + "-mode",
                XmageActualCardCorpusTest.labelled(started, "damage to target creature"));
        XmageActualCardCorpusTest.resolveAll(started, tag, "Mountain — {T}: Add {R}.", (cls, step) -> {
            if ("target".equals(cls)) {
                XmageActualCardCorpusTest.chooseByExactName(started, tag + "-bears", "Grizzly Bears", 1);
                return true;
            }
            return false;
        });
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P2", "Grizzly Bears"));
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P1", "Abrade"));
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 4})
    void aManaAbilityIsNotOfferedWhenItsOwnCostCannotBePaid(int playerCount) {
        String tag = "f35-signet-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", "Mind Stone", 0)); // {2}
        objects.add(obj("bf", "P1", "Swamp", 0));
        objects.add(obj("bf", "P1", "Rakdos Signet", 0));
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageActualCardCorpusTest.cast(started, tag + "-cast", "Mind Stone");
        assertEquals("mana_payment", XmageActualCardCorpusTest.decisionClass(started));
        assertTrue(labels(started).stream().anyMatch(label -> label.startsWith("Rakdos Signet")),
                "with the Swamp untapped the Signet's {1} can be paid: " + labels(started));
        XmageActualCardCorpusTest.submit(started, tag + "-swamp",
                XmageActualCardCorpusTest.labelled(started, "Swamp — {T}: Add {B}."));
        XmageActualCardCorpusTest.submit(started, tag + "-spend",
                XmageActualCardCorpusTest.labelled(started, "Spend black mana from pool"));
        assertEquals("mana_payment", XmageActualCardCorpusTest.decisionClass(started));
        assertEquals(List.of("Cancel mana payment"), labels(started),
                "pool empty and Swamp tapped: the Signet's own {1} can't be paid, so it is not offered");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 4})
    void aTapManaAbilityCannotPayItsOwnCostWithTheSamePermanent(int playerCount) {
        String tag = "f35-study-hall-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("hand", "P1", "Mind Stone", 0)); // {2}
        objects.add(obj("bf", "P1", "Plains", 0));
        objects.add(obj("bf", "P1", "Study Hall", 0));
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageActualCardCorpusTest.cast(started, tag + "-cast", "Mind Stone");
        XmageActualCardCorpusTest.submit(started, tag + "-plains",
                XmageActualCardCorpusTest.labelled(started, "Plains — {T}: Add {W}."));
        XmageActualCardCorpusTest.submit(started, tag + "-spend",
                XmageActualCardCorpusTest.labelled(started, "Spend white mana from pool"));
        assertEquals("mana_payment", XmageActualCardCorpusTest.decisionClass(started));
        assertEquals(List.of("Cancel mana payment", "Study Hall — {T}: Add {C}."), labels(started),
                "Study Hall's {1}, {T} ability can't be funded by its own {T} ability");
        XmageActualCardCorpusTest.submit(started, tag + "-hall",
                XmageActualCardCorpusTest.labelled(started, "Study Hall — {T}: Add {C}."));
        XmageActualCardCorpusTest.resolveAll(started, tag, null, (cls, step) -> {
            if ("mana_payment".equals(cls)) {
                XmageActualCardCorpusTest.submit(started, tag + "-spend-c-" + step,
                        XmageActualCardCorpusTest.labelled(started, "Spend colorless mana from pool"));
                return true;
            }
            return false;
        });
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", "Mind Stone"));
    }

    private static List<String> labels(XmageActualCardCorpusTest.Started started) {
        List<String> labels = new ArrayList<>();
        for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            labels.add(meta.get("label").getAsString());
        }
        return labels;
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }
}

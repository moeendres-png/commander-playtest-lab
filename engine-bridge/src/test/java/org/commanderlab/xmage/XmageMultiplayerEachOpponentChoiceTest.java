package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * "Each opponent" choices with an actual card at 3–6 players on the
 * full-game lane.
 *
 * <p>Liliana's Triumph (Oracle: "Each opponent sacrifices a creature of their
 * choice. If you control a Liliana planeswalker, each opponent also discards
 * a card."). P1, the active player, casts it without a Liliana. Every seat
 * controls a Walking Corpse and a Gravedigger.</p>
 *
 * <ul>
 *   <li>Enabled: every opponent, and only the opponents, makes its own
 *       sacrifice choice through the external decision surface, once, from
 *       its own creatures; P1 keeps both creatures.</li>
 *   <li>CR 101.4: the choices are made in APNAP order: the active player
 *       first (here the caster, who does not choose), then the others in turn
 *       order (P1, PN, …, P2). The pin asks in the order of the engine's
 *       priority pointer instead. This is F-21
 *       (commander-playtest-lab#328), so the order expectation stays
 *       disabled until a repin admits the fix.</li>
 * </ul>
 */
class XmageMultiplayerEachOpponentChoiceTest {

    private static final String TRIUMPH = "Liliana's Triumph";
    private static final String CORPSE = "Walking Corpse";
    private static final String DIGGER = "Gravedigger";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void everyOpponentChoosesTheirOwnSacrifice(int playerCount) {
        List<String> choosers = run("triumph-" + playerCount + "p", playerCount);
        List<String> sorted = new ArrayList<>(choosers);
        sorted.sort(String::compareTo);
        List<String> opponents = new ArrayList<>();
        for (int seat = 2; seat <= playerCount; seat++) {
            opponents.add("P" + seat);
        }
        opponents.sort(String::compareTo);
        assertEquals(opponents, sorted, "each opponent chooses exactly once; the caster does not");
    }

    @Disabled("F-21: at the pin the choices follow the priority pointer, not APNAP "
            + "(commander-playtest-lab#328)")
    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void opponentsChooseInApnapOrder(int playerCount) {
        List<String> choosers = run("triumph-order-" + playerCount + "p", playerCount);
        List<String> expectedOrder = new ArrayList<>();
        for (int seat = playerCount; seat >= 2; seat--) {
            expectedOrder.add("P" + seat);
        }
        assertEquals(expectedOrder, choosers,
                "CR 101.4: active player P1 first (does not choose), then turn order PN, ..., P2");
    }

    private static List<String> run(String tag, int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-P1-0-LilianasTriumph", TRIUMPH, "P1", "P1",
                mage.constants.Zone.HAND, false));
        for (int index = 0; index < 2; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P1-" + index + "-Swamp", "Swamp", "P1", "P1",
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            for (String creature : List.of(CORPSE, DIGGER)) {
                objects.add(new XmageNativeStateRestoration.RequestedObject(
                        "obj:bf-" + pid + "-0-" + creature.replace(" ", ""), creature,
                        pid, pid, mage.constants.Zone.BATTLEFIELD, false));
            }
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        Game game = started.session().restorationGame();

        XmageActualCardCorpusTest.cast(started, tag + "-cast", TRIUMPH);
        List<String> choosers = new ArrayList<>();
        XmageActualCardCorpusTest.resolveAll(started, tag,
                XmageActualCardCorpusTest.SWAMP_LABEL, (cls, step) -> {
                    if (!"choose_object".equals(cls)) {
                        return false;
                    }
                    String actor = XmageActualCardCorpusTest.actorPid(started);
                    UUID actorId = started.seats().get(actor).getId();
                    JsonObject legal = started.session().legalActionsPayload();
                    Set<String> offered = new java.util.TreeSet<>();
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        JsonObject engine = element.getAsJsonObject()
                                .getAsJsonObject("metadata")
                                .getAsJsonObject("xmage_option_metadata");
                        assertNotNull(engine, "sacrifice options carry engine metadata");
                        Permanent option = game.getPermanent(
                                UUID.fromString(engine.get("object_id").getAsString()));
                        assertNotNull(option, "each option is a permanent");
                        assertEquals(actorId, option.getControllerId(),
                                actor + " may sacrifice only a creature they control");
                        offered.add(option.getName());
                    }
                    assertEquals(Set.of(CORPSE, DIGGER), offered,
                            actor + " chooses between their own two creatures");
                    choosers.add(actor);
                    XmageActualCardCorpusTest.chooseByExactName(started,
                            tag + "-sac-" + actor, chosenBy(actor), 1);
                    return true;
                });

        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            if (seat == 1) {
                assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, pid, CORPSE));
                assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, pid, DIGGER));
                continue;
            }
            String chosen = chosenBy(pid);
            String kept = chosen.equals(CORPSE) ? DIGGER : CORPSE;
            assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, pid, chosen),
                    pid + " sacrificed " + chosen);
            assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, pid, chosen),
                    pid + "'s " + chosen + " is in their graveyard");
            assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, pid, kept),
                    pid + " kept " + kept);
        }
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P1", TRIUMPH));
        assertTrue(game.getStack().isEmpty());
        assertFalse(game.hasEnded());
        return choosers;
    }

    /** Odd seats sacrifice the Corpse, even seats the Gravedigger. */
    private static String chosenBy(String pid) {
        return Integer.parseInt(pid.substring(1)) % 2 == 1 ? CORPSE : DIGGER;
    }
}

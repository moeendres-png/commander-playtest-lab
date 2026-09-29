package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.permanent.Permanent;
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
 * CR 101.4 with an actual card at 3–6 players on the full-game lane: every
 * player, not only the active one, makes their own choice through the
 * external decision surface, in APNAP order.
 *
 * <p>Innocent Blood (Oracle: "Each player sacrifices a creature of their
 * choice."). Every seat controls a Walking Corpse and a Gravedigger. P1
 * casts it. CR 101.4: the active player chooses first, then each other player
 * in turn order; the engine's live turn order is counterclockwise
 * (P1, PN, …, P2; see XmagePb03Tier2StackTest). Each player is offered only
 * their own creatures, and odd and even seats choose different ones, so each
 * sacrifice is observably that player's own decision.</p>
 */
class XmageMultiplayerEachPlayerChoiceTest {

    private static final String BLOOD = "Innocent Blood";
    private static final String CORPSE = "Walking Corpse";
    private static final String DIGGER = "Gravedigger";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void eachPlayerChoosesTheirOwnSacrificeInApnapOrder(int playerCount) {
        String tag = "blood-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-P1-0-InnocentBlood", BLOOD, "P1", "P1",
                mage.constants.Zone.HAND, false));
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-P1-0-Swamp", "Swamp", "P1", "P1",
                mage.constants.Zone.BATTLEFIELD, false));
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

        XmageActualCardCorpusTest.cast(started, tag + "-cast", BLOOD);
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

        List<String> expectedOrder = new ArrayList<>();
        expectedOrder.add("P1");
        for (int seat = playerCount; seat >= 2; seat--) {
            expectedOrder.add("P" + seat);
        }
        assertEquals(expectedOrder, choosers,
                "CR 101.4: every player chooses, active player first, then turn order");
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            String chosen = chosenBy(pid);
            String kept = chosen.equals(CORPSE) ? DIGGER : CORPSE;
            assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, pid, chosen),
                    pid + " sacrificed " + chosen);
            assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, pid, chosen),
                    pid + "'s " + chosen + " is in their graveyard");
            assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, pid, kept),
                    pid + " kept " + kept);
        }
        assertEquals(1, XmageActualCardCorpusTest.inGraveyard(started, "P1", BLOOD));
        assertTrue(game.getStack().isEmpty());
        assertFalse(game.hasEnded());
    }

    /** Odd seats sacrifice the Corpse, even seats the Gravedigger. */
    private static String chosenBy(String pid) {
        return Integer.parseInt(pid.substring(1)) % 2 == 1 ? CORPSE : DIGGER;
    }
}

package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.combat.CombatGroup;
import mage.game.permanent.Permanent;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * CR 701.15b with an actual card at 3–6 players on the full-game lane.
 *
 * <p>P1 casts Disrupt Decorum (Oracle: "Goad all creatures you don't
 * control."). Every opponent controls a Grizzly Bears. On the next turn,
 * which is PN's (the engine's turn order is counterclockwise), PN's goaded
 * Bears must attack, and must attack a player other than P1 if able.</p>
 *
 * <ul>
 *   <li>The engine declares the forced attack itself: PN is never offered
 *       "do not attack", and never offered P1.</li>
 *   <li>With several non-goading opponents, PN chooses among exactly those.</li>
 *   <li>At 3 players the only non-goading opponent is P2, and the engine
 *       declares that attack without a decision.</li>
 * </ul>
 */
class XmageMultiplayerGoadTest {

    private static final String DECORUM = "Disrupt Decorum";
    private static final String BEARS = "Grizzly Bears";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void goadedCreatureAttacksAPlayerOtherThanTheGoader(int playerCount) {
        String tag = "goad-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-P1-0-DisruptDecorum", DECORUM, "P1", "P1",
                mage.constants.Zone.HAND, false));
        for (int index = 0; index < 4; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P1-" + index + "-Mountain", "Mountain", "P1", "P1",
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        for (int seat = 2; seat <= playerCount; seat++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P" + seat + "-0-Bears", BEARS, "P" + seat, "P" + seat,
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();

        XmageActualCardCorpusTest.cast(started, tag + "-cast", DECORUM);
        XmageActualCardCorpusTest.resolveAll(started, tag, XmageActualCardCorpusTest.MOUNTAIN_LABEL,
                XmageActualCardCorpusTest.NONE);
        String next = "P" + playerCount;
        UUID nextId = started.seats().get(next).getId();

        UUID p2 = started.seats().get("P2").getId();
        List<String> offeredDefenders = null;
        boolean done = false;
        for (int step = 0; step < 300 && !done; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = session.legalActionsPayload();
            switch (cls) {
                case "priority" -> {
                    if (nextId.equals(game.getActivePlayerId())
                            && game.getStep().getType() == mage.constants.PhaseStep.DECLARE_ATTACKERS) {
                        done = true;
                        break;
                    }
                    XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                }
                case "target" -> {
                    assertEquals(next, actor, "the goaded creature's controller chooses");
                    assertTrue(offeredDefenders == null, "one forced-attack choice");
                    offeredDefenders = new ArrayList<>();
                    JsonObject atP2 = null;
                    for (JsonElement element : legal.getAsJsonArray("actions")) {
                        String defender = defenderOf(element.getAsJsonObject(), started);
                        offeredDefenders.add(defender);
                        if ("P2".equals(defender)) {
                            atP2 = element.getAsJsonObject();
                        }
                    }
                    assertNotNull(atP2, "P2 must be a legal forced defender: " + legal);
                    XmageFullGameTaxExecutionTest.submit(session, tag + "-defender-" + step, atP2);
                }
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(started,
                        tag + "-discard-" + step, "Mountain", Math.max(1, session
                                .pendingDecisionPayload().getAsJsonObject("decision")
                                .get("minimum_selections").getAsInt()));
                default -> fail("unexpected decision " + cls + " for " + actor
                        + " (a goaded creature must not be offered to hold): " + legal);
            }
        }
        assertTrue(done, "reached " + next + "'s declare attackers");

        List<String> expected = new ArrayList<>();
        for (int seat = 2; seat < playerCount; seat++) {
            expected.add("P" + seat);
        }
        if (expected.size() == 1) {
            assertEquals(null, offeredDefenders,
                    "one non-goading opponent: the engine declares the attack itself");
        } else {
            java.util.Collections.sort(offeredDefenders);
            assertEquals(expected, offeredDefenders,
                    "CR 701.15b: every opponent except the goader P1");
        }
        Permanent bears = null;
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(nextId)) {
            if (BEARS.equals(permanent.getName())) {
                bears = permanent;
            }
        }
        assertNotNull(bears);
        CombatGroup group = game.getCombat().findGroup(bears.getId());
        assertNotNull(group, next + "'s goaded Bears attacks");
        assertEquals(p2, group.getDefenderId(), "it attacks the chosen non-goader P2, not P1");
        assertEquals(1, game.getCombat().getGroups().size());
    }

    private static String defenderOf(JsonObject action, XmageActualCardCorpusTest.Started started) {
        String metadata = action.getAsJsonObject("metadata").toString();
        String found = null;
        for (java.util.Map.Entry<String, mage.players.Player> seat : started.seats().entrySet()) {
            if (metadata.contains(seat.getValue().getId().toString())) {
                assertTrue(found == null, "one player per option: " + metadata);
                found = seat.getKey();
            }
        }
        assertNotNull(found, "option names a player: " + metadata);
        return found;
    }
}

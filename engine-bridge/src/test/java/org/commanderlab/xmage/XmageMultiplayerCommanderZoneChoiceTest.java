package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.PhaseStep;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * CR 903.9a / 704.6d with actual cards at 3–6 players on the full-game lane:
 * several commanders die at once, and each owner, including every
 * non-active player, chooses for themselves whether their commander goes to
 * the command zone.
 *
 * <p>Every player casts their commander Rograkh, Son of Rohgahh ({0}, 0/1) on
 * their own turn. Then P1 casts Pyroclasm (Oracle: "Pyroclasm deals 2 damage
 * to each creature."), and every Rograkh dies simultaneously. The choices
 * should be made in APNAP order (101.4), which in the engine's turn order is
 * P1, P2, …, PN. P2 declines and everyone else accepts, so each result is
 * observably that owner's own choice.</p>
 *
 * <p><b>F-18 (engine, pinned and upstream):</b>
 * {@code GameImpl.checkStateBasedActions} iterates {@code state.getPlayers()}
 * (seat insertion order: P1, P2, …, PN), not the APNAP player list. So the
 * choices arrive in seat order, and each player's commanders are moved
 * before the next player chooses. Every owner is still asked exactly once and
 * every choice is honoured; only the order diverges from 101.4. The CR order
 * was pinned by a disabled test; fixed in the XMage multiplayer candidate f79e4168 (moeendres-png/mage#24) and enabled by the 2026-09-29 successor repin.</p>
 */
class XmageMultiplayerCommanderZoneChoiceTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    private static final String PYROCLASM = "Pyroclasm";
    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void eachOwnerChoosesForTheirOwnDyingCommander(int playerCount) {
        List<String> choosers = run(playerCount);
        List<String> seatOrder = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            seatOrder.add("P" + seat);
        }
        List<String> sorted = new ArrayList<>(choosers);
        java.util.Collections.sort(sorted);
        assertEquals(seatOrder, sorted,
                "every owner is asked exactly once (order: commanderZoneChoicesFollowApnapOrder)");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void commanderZoneChoicesFollowApnapOrder(int playerCount) {
        List<String> expected = new ArrayList<>();
        expected.add("P1");
        for (int seat = 2; seat <= playerCount; seat++) {
            expected.add("P" + seat);
        }
        assertEquals(expected, run(playerCount), "CR 101.4: APNAP order in turn order");
    }

    private static List<String> run(int playerCount) {
        String tag = "cmdzone-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-P1-0-Pyroclasm", PYROCLASM, "P1", "P1",
                mage.constants.Zone.HAND, false));
        for (int index = 0; index < 2; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P1-" + index + "-Mountain", "Mountain", "P1", "P1",
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();

        // Every player casts Rograkh from the command zone on their own turn.
        Set<String> cast = new HashSet<>();
        int turnsSeen = 0;
        for (int step = 0; step < 600 && cast.size() < playerCount; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            boolean ownMain = "priority".equals(cls)
                    && started.seats().get(actor).getId().equals(game.getActivePlayerId())
                    && game.getStep().getType() == PhaseStep.PRECOMBAT_MAIN
                    && game.getStack().isEmpty();
            if (ownMain && !cast.contains(actor)) {
                XmageActualCardCorpusTest.cast(started, tag + "-rograkh-" + actor, ROGRAKH);
                XmageActualCardCorpusTest.resolveAll(started, tag + "-" + actor, null,
                        XmageActualCardCorpusTest.NONE);
                assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, actor, ROGRAKH));
                cast.add(actor);
                continue;
            }
            answerRoutine(started, tag + "-t" + step, cls);
        }
        assertEquals(playerCount, cast.size(), "every commander is on the battlefield");

        // Back to P1's precombat main: Pyroclasm.
        for (int step = 0; step < 300; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            if ("priority".equals(cls)
                    && started.seats().get("P1").getId().equals(game.getActivePlayerId())
                    && game.getStep().getType() == PhaseStep.PRECOMBAT_MAIN
                    && game.getStack().isEmpty()) {
                break;
            }
            answerRoutine(started, tag + "-back" + step, cls);
        }
        XmageActualCardCorpusTest.cast(started, tag + "-pyroclasm", PYROCLASM);
        List<String> choosers = new ArrayList<>();
        XmageActualCardCorpusTest.resolveAll(started, tag + "-wipe", MOUNTAIN_LABEL,
                (cls, step) -> {
                    if (!"choose_use".equals(cls)) {
                        return false;
                    }
                    String owner = XmageActualCardCorpusTest.actorPid(started);
                    JsonObject pending = session.pendingDecisionPayload()
                            .getAsJsonObject("decision");
                    String prompt = pending.get("prompt").getAsString().toLowerCase(Locale.ROOT);
                    assertTrue(prompt.contains("command"), "command-zone choice: " + prompt);
                    choosers.add(owner);
                    XmageFullGameTaxExecutionTest.submit(session, tag + "-choice-" + owner,
                            useOption(session.legalActionsPayload(), !"P2".equals(owner)));
                    return true;
                });

        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, pid, ROGRAKH));
            int inGraveyard = XmageActualCardCorpusTest.inGraveyard(started, pid, ROGRAKH);
            boolean inCommand = false;
            for (Card card : game.getCommanderCardsFromCommandZone(
                    started.seats().get(pid), mage.constants.CommanderCardType.COMMANDER_OR_OATHBREAKER)) {
                inCommand |= ROGRAKH.equals(card.getName());
            }
            if ("P2".equals(pid)) {
                assertEquals(1, inGraveyard, "P2 declined: Rograkh stays in P2's graveyard");
                assertTrue(!inCommand);
            } else {
                assertEquals(0, inGraveyard, pid + " accepted");
                assertTrue(inCommand, pid + "'s Rograkh is back in the command zone");
            }
        }
        return choosers;
    }

    private static void answerRoutine(XmageActualCardCorpusTest.Started started, String tag,
            String cls) {
        switch (cls) {
            case "priority" -> XmageActualCardCorpusTest.pass(started, tag);
            case "declare_attacker" -> XmageFullGameTaxExecutionTest.submit(started.session(), tag,
                    XmageNativeStateRestorationTest.singleActionOfType(
                            started.session().legalActionsPayload(),
                            "declare_attackers", "hold_attacker"));
            case "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(started, tag);
            case "choose_object" -> XmageActualCardCorpusTest.chooseByExactName(started, tag,
                    "Mountain", Math.max(1, started.session().pendingDecisionPayload()
                            .getAsJsonObject("decision").get("minimum_selections").getAsInt()));
            default -> fail("unexpected decision " + cls + " for "
                    + XmageActualCardCorpusTest.actorPid(started));
        }
    }

    /** The engine labels its two options "Move to command" and "Leave in current zone (…)". */
    private static JsonObject useOption(JsonObject legal, boolean moveToCommand) {
        String wanted = moveToCommand ? "move to command" : "leave in current zone";
        JsonObject found = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            String label = action.getAsJsonObject("metadata").get("label").getAsString()
                    .toLowerCase(Locale.ROOT);
            if (label.startsWith(wanted)) {
                assertTrue(found == null, "ambiguous options: " + legal);
                found = action;
            }
        }
        assertNotNull(found, "no '" + wanted + "' option: " + legal);
        return found;
    }
}

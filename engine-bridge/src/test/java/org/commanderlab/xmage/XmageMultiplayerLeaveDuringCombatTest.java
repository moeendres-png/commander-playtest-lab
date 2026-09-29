package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * A defending player leaves mid-combat at 3–6 players, with actual cards on
 * the full-game lane (CR 800.4a, 800.4e).
 *
 * <p>P1 attacks P2 with Raging Goblin and P3 with Hellrider (Oracle: "Haste.
 * Whenever a creature you control attacks, this creature deals 1 damage to the
 * player or planeswalker it's attacking."). While both Hellrider triggers are
 * on the stack, P2 concedes.</p>
 *
 * <ul>
 *   <li>P2's objects leave the game.</li>
 *   <li>The trigger for the Goblin has no player to damage.</li>
 *   <li>The Goblin's combat damage is not assigned (800.4e).</li>
 *   <li>P3 still takes 1 from Hellrider's own trigger plus 3 combat damage.</li>
 *   <li>Nobody else is affected, and the game goes on.</li>
 * </ul>
 */
class XmageMultiplayerLeaveDuringCombatTest {

    private static final String GOBLIN = "Raging Goblin";
    private static final String HELLRIDER = "Hellrider";
    private static final String BEARS = "Grizzly Bears";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void damageIsNotAssignedToADefendingPlayerWhoLeft(int playerCount) {
        String tag = "leave-combat-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(bf("P1", GOBLIN));
        objects.add(bf("P1", HELLRIDER));
        for (int seat = 2; seat <= playerCount; seat++) {
            objects.add(bf("P" + seat, BEARS));
        }
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        XmageFullGameSession session = started.session();
        Game game = session.restorationGame();
        UUID p2 = started.seats().get("P2").getId();
        UUID p3 = started.seats().get("P3").getId();

        boolean conceded = false;
        boolean combatOver = false;
        for (int step = 0; step < 200 && !combatOver; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = session.legalActionsPayload();
            switch (cls) {
                case "priority" -> {
                    if (!conceded && game.getStep().getType() == PhaseStep.DECLARE_ATTACKERS
                            && game.getStack().size() == 2) {
                        concede(started, "P2");
                        conceded = true;
                        continue;
                    }
                    if (game.getStep().getType() == PhaseStep.END_COMBAT) {
                        combatOver = true;
                        break;
                    }
                    XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                }
                case "declare_attacker" -> {
                    String attacker = attackerName(legal);
                    XmageFullGameTaxExecutionTest.submit(session, tag + "-attack-" + step,
                            attackAt(legal, HELLRIDER.equals(attacker) ? p3 : p2));
                }
                case "trigger_order" -> XmageFullGameTaxExecutionTest.submit(session,
                        tag + "-order-" + step, lowestOption(legal));
                case "declare_blocker" -> {
                    assertFalse("P2".equals(actor), "P2 left the game and cannot block");
                    XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + step);
                }
                default -> fail("unexpected decision " + cls + " for " + actor + ": " + legal);
            }
        }
        assertTrue(conceded, "P2 conceded with both Hellrider triggers on the stack");
        assertTrue(combatOver, "combat finished");
        assertFalse(started.seats().get("P2").isInGame(), "P2 left the game");
        assertEquals(0, XmageActualCardCorpusTest.onBattlefield(started, "P2", BEARS),
                "800.4a: P2's objects left with them");
        assertEquals(36, started.seats().get("P3").getLife(),
                "P3: 1 from Hellrider's trigger + 3 combat damage");
        for (int seat = 4; seat <= playerCount; seat++) {
            assertEquals(40, started.seats().get("P" + seat).getLife());
        }
        assertEquals(40, started.seats().get("P1").getLife());
        assertEquals(1, XmageActualCardCorpusTest.onBattlefield(started, "P1", GOBLIN),
                "the Goblin is unharmed; its damage to the departed P2 was not assigned");
        assertFalse(game.hasEnded(), "P1 and P3 (and the rest) are still playing");
    }

    private static XmageNativeStateRestoration.RequestedObject bf(String pid, String name) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-0-" + name.replaceAll("[^A-Za-z]", ""), name, pid, pid,
                mage.constants.Zone.BATTLEFIELD, false);
    }

    private static void concede(XmageActualCardCorpusTest.Started started, String pid) {
        XmageFullGameSession session = started.session();
        String principal = started.seats().get(pid).getId().toString();
        assertTrue(session.concedeOfferPayload(principal).get("concede_available").getAsBoolean());
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "concede-" + pid);
        proposal.addProperty("actor_id", principal);
        proposal.addProperty("player_id", principal);
        assertEquals(principal, session.submitConcede(proposal)
                .get("conceded_actor_id").getAsString());
    }

    private static String attackerName(JsonObject legal) {
        String name = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            name = meta.get("name").getAsString();
        }
        assertNotNull(name);
        return name;
    }

    private static JsonObject attackAt(JsonObject legal, UUID defender) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (meta.has("defender_id")
                    && defender.toString().equals(meta.get("defender_id").getAsString())) {
                return element.getAsJsonObject();
            }
        }
        fail("attack at " + defender + " not offered: " + legal);
        return null;
    }

    /** The two Hellrider triggers are its own and equivalent in kind; take the lowest id. */
    private static JsonObject lowestOption(JsonObject legal) {
        JsonObject chosen = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata");
            assertEquals(HELLRIDER, meta.getAsJsonObject("xmage_option_metadata")
                    .get("source_name").getAsString());
            if (chosen == null || meta.get("option_id").getAsString().compareTo(
                    chosen.getAsJsonObject("metadata").get("option_id").getAsString()) < 0) {
                chosen = action;
            }
        }
        assertNotNull(chosen);
        return chosen;
    }
}

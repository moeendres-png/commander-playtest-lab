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
 * A defending player concedes while its own declare-blockers decision is open,
 * at 3–6 players on the full-game lane (CR 800.4a, 800.4e).
 *
 * <p>P1 attacks P2 with Raging Goblin and P3 with Hellrider; both Hellrider
 * triggers resolve (P2 and P3 take 1). P3 concedes at its own block prompt. A
 * player who left makes no choices; the game goes on for everyone else: P2
 * still declares (no) blocks, the Goblin deals P2 its 1, and Hellrider's damage
 * to the departed P3 is not assigned.</p>
 */
class XmageMultiplayerLeaveAtBlockTest {

    private static final String GOBLIN = "Raging Goblin";
    private static final String HELLRIDER = "Hellrider";
    private static final String BEARS = "Grizzly Bears";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5, 6})
    void theGameGoesOnWhenADefenderConcedesAtItsBlockPrompt(int playerCount) {
        String tag = "leave-block-" + playerCount + "p";
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
        String failure = null;
        for (int step = 0; step < 200 && !combatOver; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (!payload.get("failure").isJsonNull()) {
                failure = payload.getAsJsonObject("failure").get("message").getAsString();
                break;
            }
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            String actor = XmageActualCardCorpusTest.actorPid(started);
            JsonObject legal = session.legalActionsPayload();
            switch (cls) {
                case "priority" -> {
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
                    assertFalse(conceded && "P3".equals(actor), "P3 left the game and cannot block");
                    if (!conceded && "P3".equals(actor)) {
                        concede(started, "P3");
                        conceded = true;
                        continue;
                    }
                    XmageActualCardCorpusTest.chooseNone(started, tag + "-noblock-" + step);
                }
                default -> fail("unexpected decision " + cls + " for " + actor + ": " + legal);
            }
        }
        System.out.println("LEAVE-AT-BLOCK " + playerCount + "P conceded=" + conceded + " failure=" + failure
                + " combatOver=" + combatOver);
        assertTrue(conceded, "control: P3 conceded at its own block prompt");
        assertEquals(null, failure, "the game goes on for the remaining players (800.4a)");
        assertTrue(combatOver, "combat finished");
        assertFalse(started.seats().get("P3").isInGame(), "P3 left the game");
        assertEquals(38, started.seats().get("P2").getLife(), "P2: 1 from Hellrider's trigger + 1 Goblin combat damage");
        for (int seat = 4; seat <= playerCount; seat++) {
            assertEquals(40, started.seats().get("P" + seat).getLife());
        }
        assertEquals(40, started.seats().get("P1").getLife());
        assertFalse(game.hasEnded(), "P1, P2 (and the rest) are still playing");
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

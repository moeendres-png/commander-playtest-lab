package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * The active player concedes while one of its own decisions is open, one case
 * per decision class, at 4P and 5P on the full-game lane (CR 800.4a).
 *
 * <p>A player who left makes no choices, and the game goes on for everyone
 * else: its turn continues without an active player and the next turn belongs
 * to the next seat. Whatever the departed player was deciding has no remaining
 * effect: its permanents and its cards left with it, and a spell it was
 * casting is gone. The lane must neither answer for it nor stop the game.</p>
 *
 * <ul>
 *   <li>{@code declare_attacker}: P1 concedes at its attack declaration.</li>
 *   <li>{@code mode}: P1 concedes while choosing Izzet Charm's mode.</li>
 *   <li>{@code announce_x}: P1 concedes while announcing Blaze's X.</li>
 *   <li>{@code choice}: P1 concedes at Brave the Elements' "choose a color" on resolution.</li>
 *   <li>{@code target_amount}: P1 concedes while dividing Arc Lightning's damage.</li>
 *   <li>{@code trigger_order}: P1 casts Grizzly Bears with Impact Tremors and Purphoros
 *       out and concedes while ordering the two "damage to each opponent" triggers.
 *       Abilities a departed player controls cease to exist on the stack (800.4a),
 *       so no opponent takes any damage.</li>
 * </ul>
 */
class XmageMultiplayerLeaverDecisionClassTest {

    @ParameterizedTest(name = "{0} at {1} players")
    @CsvSource({
            "declare_attacker, 4", "declare_attacker, 5",
            "mode, 4", "mode, 5",
            "announce_x, 4", "announce_x, 5",
            "choice, 4", "choice, 5",
            "target_amount, 4", "target_amount, 5",
            "trigger_order, 4", "trigger_order, 5"
    })
    void theGameGoesOnWhenTheActivePlayerConcedesAtItsOwnDecision(String decisionClass, int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        String cast;
        String land;
        switch (decisionClass) {
            case "declare_attacker" -> {
                objects.add(XmageMultiplayerScenario.obj("P1", "Grizzly Bears", 0, Zone.BATTLEFIELD));
                cast = null;
                land = "Mountain";
            }
            case "mode" -> {
                objects.add(XmageMultiplayerScenario.obj("P1", "Izzet Charm", 0, Zone.HAND));
                objects.add(XmageMultiplayerScenario.obj("P1", "Island", 1, Zone.BATTLEFIELD));
                objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", 2, Zone.BATTLEFIELD));
                cast = "Cast Izzet Charm";
                land = "Island";
            }
            case "announce_x" -> {
                objects.add(XmageMultiplayerScenario.obj("P1", "Blaze", 0, Zone.HAND));
                for (int i = 1; i <= 3; i++) {
                    objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", i, Zone.BATTLEFIELD));
                }
                cast = "Cast Blaze";
                land = "Mountain";
            }
            case "choice" -> {
                objects.add(XmageMultiplayerScenario.obj("P1", "Brave the Elements", 0, Zone.HAND));
                objects.add(XmageMultiplayerScenario.obj("P1", "Plains", 1, Zone.BATTLEFIELD));
                cast = "Cast Brave the Elements";
                land = "Plains";
            }
            case "target_amount" -> {
                objects.add(XmageMultiplayerScenario.obj("P1", "Arc Lightning", 0, Zone.HAND));
                for (int i = 1; i <= 3; i++) {
                    objects.add(XmageMultiplayerScenario.obj("P1", "Mountain", i, Zone.BATTLEFIELD));
                }
                cast = "Cast Arc Lightning";
                land = "Mountain";
            }
            case "trigger_order" -> {
                // Two "damage to each opponent" triggers on P1's creature entering.
                objects.add(XmageMultiplayerScenario.obj("P1", "Grizzly Bears", 0, Zone.HAND));
                objects.add(XmageMultiplayerScenario.obj("P1", "Impact Tremors", 1, Zone.BATTLEFIELD));
                objects.add(XmageMultiplayerScenario.obj("P1", "Purphoros, God of the Forge", 2, Zone.BATTLEFIELD));
                objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 3, Zone.BATTLEFIELD));
                objects.add(XmageMultiplayerScenario.obj("P1", "Forest", 4, Zone.BATTLEFIELD));
                cast = "Cast Grizzly Bears";
                land = "Forest";
            }
            default -> throw new IllegalArgumentException(decisionClass);
        }
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "leave-" + decisionClass + "-" + playerCount + "p", playerCount, "P1", objects);
        Game game = s.session.restorationGame();
        if (cast != null) {
            s.submit(s.action("activate_ability", cast));
        }
        boolean conceded = false;
        int turn = game.getTurnNum();
        String failure = null;
        String nextActive = null;
        for (int i = 0; i < 400; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            if (!payload.get("failure").isJsonNull()) {
                failure = payload.getAsJsonObject("failure").get("message").getAsString();
                break;
            }
            if (conceded && game.getTurnNum() != turn) {
                nextActive = s.pidOf(game.getActivePlayerId().toString());
                break;
            }
            String cls = s.decisionClass();
            String actor = s.actor();
            if (!conceded && decisionClass.equals(cls) && "P1".equals(actor)) {
                String id = s.seats.get("P1").getId().toString();
                JsonObject concede = new JsonObject();
                concede.addProperty("proposal_id", "p1-concede");
                concede.addProperty("actor_id", id);
                concede.addProperty("player_id", id);
                s.session.submitConcede(concede);
                conceded = true;
                StringBuilder stack = new StringBuilder();
                game.getStack().forEach(o -> stack.append(o.getName()).append('@')
                        .append(s.pidOf(o.getControllerId().toString())).append(';'));
                System.out.println("LEAVER-CLASS-DIAG " + decisionClass + " " + playerCount + "P stack-after-concede=" + stack);
                continue;
            }
            if (conceded) {
                assertFalse("P1".equals(actor) && !"priority".equals(cls),
                        "the departed P1 is asked " + cls + " " + s.labels());
            }
            switch (cls) {
                case "mana_payment" -> s.payWith(land);
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "choose_object", "target" -> XmageActualCardCorpusTest.chooseNamed(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "d" + i, "Mountain",
                        payload.getAsJsonObject("decision").get("minimum_selections").getAsInt());
                case "declare_attacker", "declare_blocker" -> XmageActualCardCorpusTest.chooseNone(
                        new XmageActualCardCorpusTest.Started(s.session, s.seats, null), "none" + i);
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels() + " " + s.prompt());
            }
        }
        StringBuilder lives = new StringBuilder();
        for (int seat = 1; seat <= playerCount; seat++) {
            lives.append("P").append(seat).append('=').append(s.seats.get("P" + seat).getLife()).append(' ');
        }
        System.out.println("LEAVER-CLASS-DIAG " + decisionClass + " " + playerCount + "P lives " + lives);
        System.out.println("LEAVER-CLASS " + decisionClass + " " + playerCount + "P conceded=" + conceded
                + " failure=" + failure + " next=" + nextActive);
        assertTrue(conceded, "control: P1 was asked " + decisionClass);
        assertNull(failure, "800.4a: the game goes on after P1 concedes at its own " + decisionClass);
        assertFalse(s.seats.get("P1").isInGame(), "P1 left the game");
        assertEquals("P2", nextActive, "the next turn belongs to the next seat");
        for (int seat = 2; seat <= playerCount; seat++) {
            assertEquals(40, s.seats.get("P" + seat).getLife(), "P" + seat + " is unaffected");
        }
        assertFalse(game.hasEnded(), "the remaining players are still playing");
    }

    /**
     * Control for the fail-closed path: {@code multi_amount} (combat damage
     * assignment among several blockers) has no qualified departed-player
     * unwind yet, so P1 conceding at it still ends the lane fail-closed
     * instead of anything being answered for P1.
     */
    @ParameterizedTest(name = "{0} players")
    @org.junit.jupiter.params.provider.ValueSource(ints = {4, 5})
    void anUnqualifiedClassStillFailsClosed(int playerCount) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Craw Wurm", 0, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Grizzly Bears", 1, Zone.BATTLEFIELD));
        objects.add(XmageMultiplayerScenario.obj("P2", "Runeclaw Bear", 2, Zone.BATTLEFIELD));
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start(
                "leave-multi-amount-" + playerCount + "p", playerCount, "P1", objects);
        List<String> seen = new ArrayList<>();
        for (int i = 0; i < 200; i++) {
            JsonObject payload = s.session.pendingDecisionPayload();
            assertTrue(payload.get("failure").isJsonNull(), "control: the lane runs until P1's damage assignment "
                    + payload.get("failure") + " seen=" + seen);
            String cls = s.decisionClass();
            String actor = s.actor();
            seen.add(actor + ":" + cls);
            if ("multi_amount".equals(cls) && "P1".equals(actor)) {
                String id = s.seats.get("P1").getId().toString();
                JsonObject concede = new JsonObject();
                concede.addProperty("proposal_id", "p1-concede");
                concede.addProperty("actor_id", id);
                concede.addProperty("player_id", id);
                JsonObject result = s.session.submitConcede(concede);
                assertFalse(s.seats.get("P1").isInGame(), "P1 left the game");
                assertTrue(result.get("decision").isJsonNull(), "no frame stays answerable for P1: " + result);
                // The controller's code is either reported directly or, once the
                // engine thread has already surfaced it, wrapped as a game failure.
                String message = result.getAsJsonObject("failure").get("message").getAsString();
                assertTrue(message.startsWith("PLAYER_LEFT_GAME_UNSUPPORTED_DECISION: multi_amount")
                        || message.startsWith("XMAGE_FULL_GAME_FAILED: DecisionException: "
                                + "PLAYER_LEFT_GAME_UNSUPPORTED_DECISION: multi_amount"), result.toString());
                return;
            }
            switch (cls) {
                case "priority" -> s.submit(s.action("pass_priority", "Pass"));
                case "declare_attacker" -> s.submit(labelled(s, "attacks", "Seat 2"));
                case "declare_blocker" -> s.submit(labelled(s, "blocks", "Craw Wurm"));
                default -> fail("unexpected " + cls + " for " + actor + " " + s.labels() + " seen=" + seen);
            }
        }
        fail("P1 never reached a damage assignment: " + seen);
    }

    private static JsonObject labelled(XmageMultiplayerScenario s, String a, String b) {
        for (com.google.gson.JsonElement e : s.session.legalActionsPayload().getAsJsonArray("actions")) {
            String label = e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString();
            if (label.contains(a) && label.contains(b)) {
                return e.getAsJsonObject();
            }
        }
        fail("no option with " + a + "/" + b + " in " + s.labels());
        return null;
    }
}

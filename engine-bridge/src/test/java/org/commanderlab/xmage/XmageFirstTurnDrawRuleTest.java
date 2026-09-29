package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.CommanderDuel;
import mage.game.CommanderFreeForAll;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * CR 103.8a / 103.8c (Comprehensive Rules effective 2026-09-25): in a
 * two-player game the player who plays first skips the draw step of their
 * first turn; in other multiplayer games (other than Two-Headed Giant) no
 * player skips it. CR 903.2: a Commander game may be two-player.
 *
 * <p>Both bridge lanes previously built every table as
 * {@code CommanderFreeForAll}, which the pinned engine hard-codes to never
 * skip, so a two-player starting player drew on turn 1. These tests observe
 * engine state (hand and library sizes, and every turn-1 decision point) so
 * they fail if the starting player draws in 2P, if the skip leaks into
 * multiplayer, or if the non-starting player's first draw is lost.</p>
 *
 * <p>Decks are 99 Mountains under Rograkh, so the opening library is exactly
 * 92 after a seven-card hand and every count below is exact.</p>
 */
class XmageFirstTurnDrawRuleTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    private static final long SEED = 424242L;

    private static List<String> mountainDecks(
            XmageDeckImporter importer, String tag, int players) {
        List<String> handles = new ArrayList<>();
        for (int seat = 1; seat <= players; seat++) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck(
                    tag + "-P" + seat, tag + "-hash", mainboard, List.of(ROGRAKH))
                    .deckHandle());
        }
        return handles;
    }

    private static JsonObject seat(JsonObject readback, String pid) {
        for (JsonElement element : readback.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            if (pid.equals(seat.get("player_id").getAsString())) {
                return seat;
            }
        }
        fail("seat " + pid + " missing from readback");
        return null;
    }

    private static boolean at(JsonObject readback, int turn, String step) {
        return readback.get("turn_number").getAsInt() == turn
                && step.equals(readback.get("step").getAsString());
    }

    /**
     * Drives the full-game lane with explicit engine-offered choices only
     * (keep, self as starting player, priority pass) until the requested
     * turn reaches precombat main. Any turn-1 decision point inside the draw
     * step, and any unexpected decision class, fails the test.
     */
    private static JsonObject driveToMain(
            XmageFullGameSession session, Map<String, Player> seats,
            String tag, int turn) {
        for (int step = 0; step < 200; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            if (at(readback, turn, "PRECOMBAT_MAIN")) {
                return readback;
            }
            if (readback.get("turn_number").getAsInt() > turn) {
                fail("[" + tag + "] passed turn " + turn + " without a precombat-main decision");
            }
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                fail("[" + tag + "] engine terminal before turn " + turn + " main");
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            JsonObject action;
            if ("mulligan".equals(decisionClass)) {
                action = XmageFullGameTaxExecutionTest.singleActionOfType(
                        legal, "mulligan", "keep");
            } else if ("choose_object".equals(decisionClass)
                    && pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    && pending.get("prompt").getAsString().contains("starting player")) {
                action = XmageFullGameTaxExecutionTest.singleSelfAction(legal, actorId);
            } else if ("priority".equals(decisionClass)) {
                action = XmageFullGameTaxExecutionTest.singleActionOfType(
                        legal, "pass_priority", null);
            } else {
                fail("[" + tag + "] unexpected decision class " + decisionClass
                        + " at turn " + readback.get("turn_number").getAsInt()
                        + " step " + readback.get("step"));
                return null;
            }
            XmageFullGameTaxExecutionTest.submit(session, tag + "-" + step, action);
        }
        fail("[" + tag + "] drive bound breached");
        return null;
    }

    @Test
    void twoPlayerStartingPlayerSkipsFirstDrawButOpponentDraws() {
        String tag = "cr103-8a-2p";
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageFullGameSession session = new XmageFullGameSession(
                tag, mountainDecks(importer, tag, 2), 0, 40, SEED, importer);
        session.start();
        Map<String, Player> seats = session.restorationSeats();

        // Every decision point until turn-1 main: none may sit in the draw
        // step, and P1's post-mulligan counts must never change on the way.
        Integer openingHand = null;
        Integer openingLibrary = null;
        for (int step = 0; step < 200; step++) {
            JsonObject readback = XmageNativeStateRestoration.readback(
                    session.restorationGame(), seats);
            JsonObject payload = session.pendingDecisionPayload();
            assertTrue(!payload.get("decision").isJsonNull(), "engine terminal on turn 1");
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            // Priority decisions exist only once opening hands are final, so
            // they are the checkpoints for the post-mulligan counts.
            if ("priority".equals(decisionClass)
                    && readback.get("turn_number").getAsInt() == 1) {
                assertTrue(!"DRAW".equals(readback.get("step").getAsString()),
                        "CR 103.8a: no decision point may exist inside a skipped draw step");
                JsonObject p1 = seat(readback, "P1");
                if (openingHand == null) {
                    openingHand = p1.get("hand_count").getAsInt();
                    openingLibrary = p1.get("library_count").getAsInt();
                    assertEquals(7, openingHand, "post-mulligan opening hand");
                    assertEquals(92, openingLibrary, "post-mulligan library");
                }
                assertEquals(openingHand, p1.get("hand_count").getAsInt(),
                        "CR 103.8a: P1 hand unchanged through turn 1 up to main");
                assertEquals(openingLibrary, p1.get("library_count").getAsInt(),
                        "CR 103.8a: P1 library unchanged through turn 1 up to main");
                if (at(readback, 1, "PRECOMBAT_MAIN")) {
                    break;
                }
            }
            JsonObject legal = session.legalActionsPayload();
            String actorId = legal.get("actor_id").getAsString();
            JsonObject action;
            if ("mulligan".equals(decisionClass)) {
                action = XmageFullGameTaxExecutionTest.singleActionOfType(
                        legal, "mulligan", "keep");
            } else if ("choose_object".equals(decisionClass)) {
                action = XmageFullGameTaxExecutionTest.singleSelfAction(legal, actorId);
            } else if ("priority".equals(decisionClass)) {
                action = XmageFullGameTaxExecutionTest.singleActionOfType(
                        legal, "pass_priority", null);
            } else {
                fail("unexpected decision class on turn 1: " + decisionClass);
                return;
            }
            XmageFullGameTaxExecutionTest.submit(session, tag + "-t1-" + step, action);
        }
        assertNotNull(openingHand, "at least one turn-1 priority checkpoint was observed");
        JsonObject turn1 = XmageNativeStateRestoration.readback(
                session.restorationGame(), seats);
        assertTrue(at(turn1, 1, "PRECOMBAT_MAIN"), "turn-1 precombat main reached");
        assertEquals("P1", turn1.get("active_player").getAsString(), "P1 plays first");
        assertEquals(7, seat(turn1, "P1").get("hand_count").getAsInt());
        assertEquals(92, seat(turn1, "P1").get("library_count").getAsInt());

        // The rule is the starting player's first draw only: P2 still draws.
        JsonObject turn2 = driveToMain(session, seats, tag, 2);
        assertEquals("P2", turn2.get("active_player").getAsString());
        assertEquals(8, seat(turn2, "P2").get("hand_count").getAsInt(),
                "CR 103.8a skips only the starting player's first draw");
        assertEquals(91, seat(turn2, "P2").get("library_count").getAsInt());
        assertEquals(7, seat(turn2, "P1").get("hand_count").getAsInt());
    }

    @ParameterizedTest
    @ValueSource(ints = {3, 4, 5, 6})
    void multiplayerStartingPlayerDrawsOnFirstTurn(int players) {
        String tag = "cr103-8c-" + players + "p";
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageFullGameSession session = new XmageFullGameSession(
                tag, mountainDecks(importer, tag, players), 0, 40, SEED, importer);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        JsonObject turn1 = driveToMain(session, seats, tag, 1);
        assertEquals("P1", turn1.get("active_player").getAsString());
        assertEquals(8, seat(turn1, "P1").get("hand_count").getAsInt(),
                "CR 103.8c: in multiplayer no player skips their first draw");
        assertEquals(91, seat(turn1, "P1").get("library_count").getAsInt());
    }

    /**
     * The compatibility lane returns from {@code startGame} at turn-1 upkeep,
     * before any draw step, so the rule is observed as the engine's own
     * pending turn modification rather than as a hand size: the starting
     * player carries exactly one skip-DRAW modification in 2P and none in
     * multiplayer. The full-game test above observes the resulting draws.
     */
    @ParameterizedTest
    @ValueSource(ints = {2, 3, 4, 5})
    void compatibilityLaneAppliesTheSameFirstDrawRule(int players) {
        String tag = "cr103-8-compat-" + players + "p";
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                tag, mountainDecks(importer, tag, players), 0, 40, true);
        Game game = manager.requireGame(created.gameHandle());
        if (players == 2) {
            assertInstanceOf(CommanderDuel.class, game,
                    "2P uses the engine's two-player Commander type");
        } else {
            assertInstanceOf(CommanderFreeForAll.class, game);
        }
        manager.startGame(created.gameHandle());
        assertEquals(1, game.getState().getTurnNum());
        assertEquals(PhaseStep.UPKEEP, game.getTurnStepType(),
                "observation point precedes the first draw step");
        UUID starter = game.getStartingPlayerId();
        assertNotNull(starter);
        long skipDraw = game.getState().getTurnMods().stream()
                .filter(mod -> mod.getSkipStep() == PhaseStep.DRAW)
                .filter(mod -> starter.equals(mod.getPlayerId()))
                .count();
        long otherSkipDraw = game.getState().getTurnMods().stream()
                .filter(mod -> mod.getSkipStep() == PhaseStep.DRAW)
                .filter(mod -> !starter.equals(mod.getPlayerId()))
                .count();
        assertEquals(players == 2 ? 1 : 0, skipDraw,
                players == 2
                        ? "CR 103.8a: the 2P starting player's first draw step is skipped"
                        : "CR 103.8c: no multiplayer player skips their first draw");
        assertEquals(0, otherSkipDraw, "no other player's draw step is skipped");
        Player starterPlayer = game.getPlayer(starter);
        assertEquals(7, starterPlayer.getHand().size());
        assertEquals(92, starterPlayer.getLibrary().size());
    }
}

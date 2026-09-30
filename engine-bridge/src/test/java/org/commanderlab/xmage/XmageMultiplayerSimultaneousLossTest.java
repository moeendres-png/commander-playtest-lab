package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Simultaneous losses in multiplayer, with an actual card on the full-game
 * lane.
 *
 * <p>P1 casts Flame Rift (Oracle: "Flame Rift deals 4 damage to each
 * player.").</p>
 *
 * <p>Low life totals come from the engine's own starting life and real
 * damage, never from restored life (which the engine re-derives at game start;
 * see XmageFullGameElimExecutionTest).</p>
 *
 * <ul>
 *   <li>Some players lose (4P/5P/6P). Starting life is 7, and P1 first
 *       Lightning Bolts P2 and Lava Spikes PN, down to 4. P2 and PN then lose simultaneously
 *       to Flame Rift (CR 704.5a). The game goes on for everyone else, who end at
 *       3. P2 is next after P1 in the engine's turn order (seat order, F-41), so
 *       the next turn is P3's: a departed player's turn doesn't begin (800.4k).</li>
 *   <li>Everyone loses (3P/4P/5P). Starting life is 4, every player loses
 *       simultaneously, and the game is a draw (104.4a): every player lost and
 *       nobody won.</li>
 * </ul>
 */
class XmageMultiplayerSimultaneousLossTest {

    private static final String RIFT = "Flame Rift";
    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5, 6})
    void simultaneousLossesLeaveTheOthersPlaying(int playerCount) {
        String pn = "P" + playerCount;
        Set<String> losers = Set.of("P2", pn);
        String tag = "rift-some-" + playerCount + "p";
        XmageActualCardCorpusTest.Started started = board(tag, playerCount, 7, 2);
        Map<String, String> burnFor = Map.of("P2", "Lightning Bolt", pn, "Lava Spike");
        for (String victim : List.of("P2", pn)) {
            XmageActualCardCorpusTest.cast(started, tag + "-bolt-" + victim, burnFor.get(victim));
            XmageActualCardCorpusTest.resolveAll(started, tag + "-bolt-" + victim, MOUNTAIN_LABEL,
                    (cls, step) -> {
                        if (!"target".equals(cls)) {
                            return false;
                        }
                        XmageActualCardCorpusTest.submit(started, tag + "-t-" + victim,
                                XmageActualCardCorpusTest.playerTarget(started, victim));
                        return true;
                    });
            assertEquals(4, started.seats().get(victim).getLife());
        }
        XmageActualCardCorpusTest.cast(started, tag + "-cast", RIFT);
        Game game = started.session().restorationGame();
        drainUntilPriorityOrTerminal(started, "rift-some-" + playerCount);

        assertFalse(game.hasEnded(), "the game continues");
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            Player player = started.seats().get(pid);
            if (losers.contains(pid)) {
                assertTrue(player.hasLost(), pid + " lost");
            } else {
                assertFalse(player.hasLost(), pid + " still plays");
                assertEquals(3, player.getLife(), pid + " took 4");
            }
        }

        String prev = "P3";
        for (int step = 0; step < 200; step++) {
            String cls = XmageActualCardCorpusTest.decisionClass(started);
            if ("priority".equals(cls)
                    && !started.seats().get("P1").getId().equals(game.getActivePlayerId())) {
                break;
            }
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, "rift-pass-" + step);
                case "choose_object" -> XmageActualCardCorpusTest.chooseNamed(started,
                        "rift-discard-" + step, "Mountain", Math.max(1, started.session()
                                .pendingDecisionPayload().getAsJsonObject("decision")
                                .get("minimum_selections").getAsInt()));
                default -> fail("unexpected decision " + cls);
            }
        }
        assertEquals(started.seats().get(prev).getId(), game.getActivePlayerId(),
                "800.4k: P2 left, so the next turn is " + prev + "'s");
        assertEquals(2, game.getState().getTurnNum(), "one turn later");
    }

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {3, 4, 5})
    void everyoneLosingAtOnceIsADraw(int playerCount) {
        XmageActualCardCorpusTest.Started started = board("rift-all-" + playerCount + "p",
                playerCount, 4, 0);
        XmageActualCardCorpusTest.cast(started, "rift-all-" + playerCount + "p-cast", RIFT);
        drainUntilPriorityOrTerminal(started, "rift-all-" + playerCount);

        JsonObject payload = started.session().pendingDecisionPayload();
        assertTrue(payload.get("decision").isJsonNull(), "the game is over");
        int lost = 0;
        for (JsonElement element : payload.getAsJsonArray("outcomes")) {
            JsonObject outcome = element.getAsJsonObject();
            assertFalse(outcome.get("won").getAsBoolean(), "104.4a: nobody wins a draw");
            lost += outcome.get("lost").getAsBoolean() ? 1 : 0;
        }
        assertEquals(playerCount, lost, "every player lost simultaneously");
        assertTrue(started.session().restorationGame().hasEnded());
        assertTrue(started.session().restorationGame().isADraw(), "the engine records a draw");
    }

    private static XmageActualCardCorpusTest.Started board(String tag, int playerCount,
            int startingLife, int bolts) {
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(new XmageNativeStateRestoration.RequestedObject(
                "obj:hand-P1-0-FlameRift", RIFT, "P1", "P1", mage.constants.Zone.HAND, false));
        List<String> burn = List.of("Lightning Bolt", "Lava Spike");
        for (int index = 0; index < bolts; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:hand-P1-" + index + "-" + burn.get(index).replace(" ", ""),
                    burn.get(index), "P1", "P1", mage.constants.Zone.HAND, false));
        }
        for (int index = 0; index < 2 + bolts; index++) {
            objects.add(new XmageNativeStateRestoration.RequestedObject(
                    "obj:bf-P1-" + index + "-Mountain", "Mountain", "P1", "P1",
                    mage.constants.Zone.BATTLEFIELD, false));
        }
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(
                tag, playerCount, objects, Map.of(), 0, 424242L, startingLife);
        for (Player player : started.seats().values()) {
            assertEquals(startingLife, player.getLife(), "engine starting life");
        }
        return started;
    }

    /** Pays and passes until priority returns with an empty stack, or the game ends. */
    private static void drainUntilPriorityOrTerminal(XmageActualCardCorpusTest.Started started,
            String tag) {
        Game game = started.session().restorationGame();
        for (int step = 0; step < 80; step++) {
            JsonObject payload = started.session().pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                return;
            }
            String cls = payload.getAsJsonObject("decision").get("decision_class").getAsString();
            if ("priority".equals(cls) && game.getStack().isEmpty()
                    && XmageActualCardCorpusTest.inGraveyard(started, "P1", RIFT) == 1) {
                return;
            }
            switch (cls) {
                case "priority" -> XmageActualCardCorpusTest.pass(started, tag + "-pass-" + step);
                case "mana_payment" -> XmageActualCardCorpusTest.payOneFromRestoredMana(started,
                        tag + "-pay-" + step,
                        List.of(XmageActualCardCorpusTest.manaSourceName(MOUNTAIN_LABEL)),
                        Set.of(MOUNTAIN_LABEL));
                default -> fail("unexpected decision " + cls);
            }
        }
        fail("bound breached");
    }
}

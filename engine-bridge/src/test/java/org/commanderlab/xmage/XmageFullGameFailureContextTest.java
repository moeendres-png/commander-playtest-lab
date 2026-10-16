package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import mage.constants.Zone;
import mage.game.Game;
import org.junit.jupiter.api.Test;

/**
 * #845: when the engine goes silent (DECISION_ADVANCE_TIMEOUT) or dies with
 * OutOfMemoryError, the failure message names what the engine was doing, so a
 * CI log alone suffices for diagnosis.
 */
class XmageFullGameFailureContextTest {

    /** A spinning engine thread parks inside this uniquely named method. */
    private static void spinSilently845(AtomicBoolean stop) {
        while (!stop.get()) {
            // busy: the engine is stuck here when the timeout fires
        }
    }

    /**
     * #845(a): a thread spinning inside {@link #spinSilently845} makes
     * {@code awaitSettled} time out; the message names the thread and the
     * spinning method, on one line, within 1000 characters.
     */
    @Test
    void aSilentEngineNamesItsThreadAndTopFrames() {
        AtomicBoolean stop = new AtomicBoolean(false);
        Thread engine = new Thread(() -> spinSilently845(stop), "silent-spin-845-thread");
        engine.setDaemon(true);
        engine.start();
        try {
            XmageFullGameDecisionController.DecisionException timeout = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> XmageFullGameSession.awaitSettled(
                            new XmageFullGameDecisionController(),
                            engine,
                            Duration.ofMillis(200)));
            String message = timeout.getMessage();
            assertTrue(message.startsWith("DECISION_ADVANCE_TIMEOUT"), message);
            assertTrue(message.contains("silent-spin-845-thread"),
                    "the message names the engine thread: " + message);
            assertTrue(message.contains("spinSilently845"),
                    "the message names the spinning method: " + message);
            assertTrue(!message.contains("\n") && !message.contains("\r"),
                    "the message is one line: " + message);
            assertTrue(message.length() <= 1000,
                    "the message stays within 1000 chars, was " + message.length() + ": " + message);
        } finally {
            stop.set(true);
            engine.interrupt();
            try {
                engine.join(5_000L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            }
        }
    }

    /**
     * #845: a null engine thread is still a one-line message rather than an
     * exception from the diagnostic itself.
     */
    @Test
    void aNullEngineThreadStillProducesContext() {
        XmageFullGameDecisionController.DecisionException timeout = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> XmageFullGameSession.awaitSettled(
                        new XmageFullGameDecisionController(),
                        null,
                        Duration.ofMillis(50)));
        String message = timeout.getMessage();
        assertTrue(message.startsWith("DECISION_ADVANCE_TIMEOUT"), message);
        assertTrue(message.contains("engine=null"), message);
        assertTrue(message.length() <= 1000, message);
    }

    /**
     * #845(b): the heap-context helper, run against a real engine Game, reports
     * the four live values: turn number, stack size, battlefield permanent
     * count, controller decision count. No real OutOfMemoryError is provoked;
     * the helper is exercised directly on the diagnosed values.
     */
    @Test
    void theHeapContextHelperReportsTheFourLiveValues() {
        List<XmageNativeStateRestoration.RequestedObject> objects = List.of(
                XmageMultiplayerScenario.obj("P1", "Forest", 0, Zone.BATTLEFIELD),
                XmageMultiplayerScenario.obj("P1", "Forest", 1, Zone.BATTLEFIELD));
        XmageMultiplayerScenario scenario =
                XmageMultiplayerScenario.start("failure-context-845", 2, "P1", objects);
        Game game = scenario.session.restorationGame();
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();

        String context = XmageFullGameSession.engineHeapContext(game, controller);

        Matcher parsed = Pattern.compile(
                "turn=(\\d+) stack=(\\d+) battlefield=(\\d+) decisions=(\\d+)").matcher(context);
        assertTrue(parsed.matches(), "unexpected context shape: " + context);
        assertEquals(game.getTurnNum(), Integer.parseInt(parsed.group(1)), context);
        assertEquals(game.getStack().size(), Integer.parseInt(parsed.group(2)), context);
        assertEquals(game.getBattlefield().getAllPermanents().size(),
                Integer.parseInt(parsed.group(3)), context);
        assertEquals(controller.decisionCount(), Long.parseLong(parsed.group(4)), context);
        // Sanity: the two requested Forests are on the battlefield.
        assertTrue(game.getBattlefield().getAllPermanents().size() >= 2, context);
    }

    /**
     * #845(b), negative half: the helper never throws, even when the game is
     * null (the OOM helper must not mask the failure it describes).
     */
    @Test
    void theHeapContextHelperCannotThrow() {
        String context = XmageFullGameSession.engineHeapContext(
                null, new XmageFullGameDecisionController());
        assertEquals("context-unavailable", context);
    }
}

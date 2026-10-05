package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import org.junit.jupiter.api.Test;

/**
 * #553 Audit 3: the controller is marked terminal on the engine thread just
 * before that thread ends, while the status derives {@code terminal} from
 * thread liveness. A status built in that window reported a finished game as
 * running with no decision, which the replay consumer refused as an early
 * termination. These controls reproduce the window deterministically.
 */
class XmageFullGameSettledStatusTest {

    @Test
    void aGameMarkedOverIsReportedOnlyOnceItsThreadHasEnded() throws Exception {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        CountDownLatch marked = new CountDownLatch(1);
        Thread engine = new Thread(() -> {
            controller.markTerminal();
            marked.countDown();
            try {
                Thread.sleep(300L); // the rest of runEngine's finally block
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            }
        });
        engine.start();
        marked.await();
        // The window itself: the controller says over, the thread still lives.
        assertTrue(controller.awaitPendingOrTerminal(Duration.ofSeconds(1)));
        assertTrue(engine.isAlive(), "the race window must be open for this control to mean anything");
        XmageFullGameSession.awaitSettled(controller, engine, Duration.ofSeconds(5));
        assertFalse(engine.isAlive());
    }

    @Test
    void anEngineThatNeitherParksNorEndsIsAnExplicitTimeout() throws Exception {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        Thread engine = new Thread(() -> {
            try {
                Thread.sleep(2_000L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            }
        });
        engine.start();
        try {
            XmageFullGameDecisionController.DecisionException timeout = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> XmageFullGameSession.awaitSettled(
                            controller, engine, Duration.ofMillis(200)));
            assertTrue(timeout.getMessage().startsWith("DECISION_ADVANCE_TIMEOUT"),
                    timeout.getMessage());
        } finally {
            engine.interrupt();
            engine.join();
        }
    }

    @Test
    void aGameOverWhoseThreadNeverEndsIsAnExplicitTimeout() throws Exception {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        CountDownLatch release = new CountDownLatch(1);
        Thread engine = new Thread(() -> {
            controller.markTerminal();
            try {
                release.await();
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            }
        });
        engine.start();
        try {
            XmageFullGameDecisionController.DecisionException stuck = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class,
                    () -> XmageFullGameSession.awaitSettled(
                            controller, engine, Duration.ofMillis(300)));
            assertTrue(stuck.getMessage().contains("did not end"), stuck.getMessage());
        } finally {
            release.countDown();
            engine.join();
        }
    }
}

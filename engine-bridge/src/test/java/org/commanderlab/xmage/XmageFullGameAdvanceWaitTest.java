package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Bridge-lean #1264 step 3 (NEUTRAL): waiting for the engine to consume a
 * submitted decision blocks on the controller monitor instead of copying the
 * pending request every millisecond. Same outcomes as before: return on
 * advance, on terminal failure, on game over; DECISION_ADVANCE_TIMEOUT on the
 * deadline and on interruption.
 */
class XmageFullGameAdvanceWaitTest {

    private static void setPending(XmageFullGameDecisionController controller, String id) throws Exception {
        Field field = XmageFullGameDecisionController.class.getDeclaredField("pendingRequest");
        field.setAccessible(true);
        synchronized (controller) {
            if (id == null) {
                field.set(controller, null);
            } else {
                JsonObject request = new JsonObject();
                request.addProperty("decision_id", id);
                request.addProperty("decision_class", "priority");
                field.set(controller, request);
            }
            controller.notifyAll();
        }
    }

    private static long millisSince(long startNanos) {
        return (System.nanoTime() - startNanos) / 1_000_000L;
    }

    @Test
    void controllerWaitReturnsOnReplacementWithoutPollingDelay() throws Exception {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        setPending(controller, "d1");
        Thread other = new Thread(() -> {
            try {
                Thread.sleep(150L);
                setPending(controller, "d2");
            } catch (Exception exc) {
                throw new IllegalStateException(exc);
            }
        });
        other.start();
        long start = System.nanoTime();
        long deadline = start + Duration.ofSeconds(10).toNanos();
        boolean advanced = false;
        while (!advanced) {
            advanced = controller.awaitDecisionAdvance("d1", deadline, 5_000L);
        }
        long waited = millisSince(start);
        other.join();
        assertTrue(waited >= 100L && waited < 2_000L, "waited " + waited);
        assertEquals("d2", controller.pendingDecisionId());
        assertEquals("priority", controller.pendingDecisionClass());
        assertTrue(controller.hasPendingDecision());
    }

    @Test
    void controllerWaitReturnsOnConsumptionTerminalAndFailure() throws Exception {
        XmageFullGameDecisionController consumed = new XmageFullGameDecisionController();
        setPending(consumed, "d1");
        Thread consume = new Thread(() -> {
            try {
                Thread.sleep(100L);
                setPending(consumed, null);
            } catch (Exception exc) {
                throw new IllegalStateException(exc);
            }
        });
        consume.start();
        assertTrue(waitUntilAdvanced(consumed, "d1"));
        consume.join();
        assertFalse(consumed.hasPendingDecision());

        XmageFullGameDecisionController terminal = new XmageFullGameDecisionController();
        setPending(terminal, "d1");
        Thread mark = new Thread(() -> {
            try {
                Thread.sleep(100L);
            } catch (InterruptedException exc) {
                return;
            }
            terminal.markTerminal();
        });
        mark.start();
        assertTrue(waitUntilAdvanced(terminal, "d1"));
        mark.join();
        assertTrue(terminal.hasPendingDecision(), "game over does not clear the frame; the wait still ends");

        XmageFullGameDecisionController failed = new XmageFullGameDecisionController();
        setPending(failed, "d1");
        Thread fail = new Thread(() -> {
            try {
                Thread.sleep(100L);
            } catch (InterruptedException exc) {
                return;
            }
            failed.failClosed("XMAGE_FULL_GAME_FAILED", "test");
        });
        fail.start();
        assertTrue(waitUntilAdvanced(failed, "d1"));
        fail.join();
    }

    private static boolean waitUntilAdvanced(XmageFullGameDecisionController controller, String id)
            throws Exception {
        long start = System.nanoTime();
        long deadline = start + Duration.ofSeconds(10).toNanos();
        boolean advanced = false;
        while (!advanced && System.nanoTime() < deadline) {
            advanced = controller.awaitDecisionAdvance(id, deadline, 5_000L);
        }
        assertTrue(millisSince(start) < 3_000L, "wait must end by notification, not by the 5 s cap");
        return advanced;
    }

    @Test
    void controllerWaitTimesOutAtTheDeadlineAndKeepsTheFrame() throws Exception {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        setPending(controller, "d1");
        long start = System.nanoTime();
        long deadline = start + Duration.ofMillis(250).toNanos();
        boolean advanced = true;
        while (System.nanoTime() < deadline && advanced) {
            advanced = controller.awaitDecisionAdvance("d1", deadline, 5_000L);
        }
        assertFalse(advanced);
        assertFalse(controller.awaitDecisionAdvance("d1", deadline, 5_000L), "past the deadline: false at once");
        assertTrue(millisSince(start) >= 240L && millisSince(start) < 2_000L);
        assertEquals("d1", controller.pendingDecisionId());
    }

    @Test
    void controllerWaitIsInterruptible() throws Exception {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        setPending(controller, "d1");
        AtomicReference<Throwable> seen = new AtomicReference<>();
        Thread waiter = new Thread(() -> {
            try {
                controller.awaitDecisionAdvance("d1", System.nanoTime() + Duration.ofSeconds(30).toNanos(), 5_000L);
            } catch (Throwable exc) {
                seen.set(exc);
            }
        });
        waiter.start();
        Thread.sleep(100L);
        waiter.interrupt();
        waiter.join(5_000L);
        assertTrue(seen.get() instanceof InterruptedException, String.valueOf(seen.get()));
    }

    // ---- session level, live four-player game ----

    private static XmageFullGameSession liveSession(String id) throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = XmageFullGameHiddenInformationTest.importCopies(
                importer, XmageFullGameHiddenInformationTest.loadRogShaiRuntimeDeck(), 4);
        XmageFullGameSession session = new XmageFullGameSession(id, handles, 0, 40, 10704L, importer);
        session.start();
        return session;
    }

    private static void awaitAdvance(XmageFullGameSession session, String id, Duration timeout) throws Throwable {
        Method method = XmageFullGameSession.class.getDeclaredMethod(
                "awaitDecisionAdvance", String.class, Duration.class);
        method.setAccessible(true);
        try {
            method.invoke(session, id, timeout);
        } catch (InvocationTargetException exc) {
            throw exc.getCause();
        }
    }

    private static XmageFullGameDecisionController controllerOf(XmageFullGameSession session) throws Exception {
        return XmageFullGameHiddenInformationTest.field(
                session, "controller", XmageFullGameDecisionController.class);
    }

    @Test
    void sessionAdvancesWhenTheEngineConsumesTheFrame() throws Exception {
        XmageFullGameSession session = liveSession("lean-1264-wait-advance");
        for (int step = 0; step < 12; step++) {
            JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
            String before = pending.get("decision_id").getAsString();
            XmageFullGameHiddenInformationTest.answerNeutrally(session, pending);
            JsonObject after = session.pendingDecisionPayload();
            if (!after.get("decision").isJsonNull()) {
                assertNotEquals(before, after.getAsJsonObject("decision").get("decision_id").getAsString());
            }
        }
    }

    @Test
    void sessionTimesOutWhenTheFrameIsNeverConsumed() throws Throwable {
        XmageFullGameSession session = liveSession("lean-1264-wait-timeout");
        String id = session.pendingDecisionPayload().getAsJsonObject("decision").get("decision_id").getAsString();
        long start = System.nanoTime();
        XmageFullGameDecisionController.DecisionException timeout = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> {
                    try {
                        awaitAdvance(session, id, Duration.ofMillis(300));
                    } catch (RuntimeException exc) {
                        throw exc;
                    } catch (Throwable exc) {
                        throw new IllegalStateException(exc);
                    }
                });
        assertEquals("DECISION_ADVANCE_TIMEOUT: engine did not consume " + id, timeout.getMessage());
        assertTrue(millisSince(start) >= 290L && millisSince(start) < 3_000L, "took " + millisSince(start));
    }

    @Test
    void sessionStopsWaitingWhenTheGameFailsOrEnds() throws Throwable {
        XmageFullGameSession session = liveSession("lean-1264-wait-failure");
        String id = session.pendingDecisionPayload().getAsJsonObject("decision").get("decision_id").getAsString();
        XmageFullGameDecisionController controller = controllerOf(session);
        Thread failer = new Thread(() -> {
            try {
                Thread.sleep(200L);
            } catch (InterruptedException exc) {
                return;
            }
            controller.failClosed("XMAGE_FULL_GAME_FAILED", "lean-1264 test");
        });
        failer.start();
        long start = System.nanoTime();
        awaitAdvance(session, id, Duration.ofSeconds(20));
        failer.join();
        assertTrue(millisSince(start) >= 150L && millisSince(start) < 5_000L, "took " + millisSince(start));
        assertTrue(controller.terminalFailure() != null);
    }

    @Test
    void sessionWaitIsInterruptedLikeBefore() throws Throwable {
        XmageFullGameSession session = liveSession("lean-1264-wait-interrupt");
        String id = session.pendingDecisionPayload().getAsJsonObject("decision").get("decision_id").getAsString();
        Thread.currentThread().interrupt();
        try {
            Throwable failure = assertThrows(Throwable.class, () -> awaitAdvance(session, id, Duration.ofSeconds(20)));
            assertTrue(failure instanceof XmageFullGameDecisionController.DecisionException, String.valueOf(failure));
            assertEquals("DECISION_ADVANCE_TIMEOUT: interrupted while advancing " + id, failure.getMessage());
            assertTrue(Thread.currentThread().isInterrupted(), "interrupt flag restored");
        } finally {
            Thread.interrupted();
        }
    }
}

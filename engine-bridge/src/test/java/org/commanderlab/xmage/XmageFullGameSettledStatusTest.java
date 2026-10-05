package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
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
        CountDownLatch release = new CountDownLatch(1);
        Thread engine = new Thread(() -> {
            controller.markTerminal();
            marked.countDown();
            try {
                release.await(); // the rest of runEngine's finally block
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            }
        });
        engine.start();
        marked.await();
        // The window itself: the controller says over, the thread still lives.
        assertTrue(controller.awaitPendingOrTerminal(Duration.ofSeconds(1)));
        assertTrue(engine.isAlive(), "the race window must be open for this control to mean anything");
        releaseLater(release);
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

    /**
     * The real request path: a 2P game ends by concession while the engine
     * thread is held right after markTerminal. get_full_game_decision must
     * answer a settled terminal status, never "not terminal, no decision".
     */
    @Test
    void theDecisionRequestOfAGameJustEndedReportsItTerminal() throws Exception {
        CountDownLatch marked = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        XmageFullGameSession.afterTerminalMarked = () -> {
            marked.countDown();
            try {
                release.await();
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            }
        };
        try {
            XmageDeckImporter importer = new XmageDeckImporter();
            List<String> handles = rogShaiCopies(importer, 2);
            XmageFullGameSession session = new XmageFullGameSession(
                    "settled-status-concede", handles, 0, 40, 424242L, importer);
            session.start();
            JsonObject first = session.pendingDecisionPayload();
            assertFalse(first.get("decision").isJsonNull(), first.toString());
            String actor = session.legalActionsPayload().get("actor_id").getAsString();
            JsonObject concede = new JsonObject();
            concede.addProperty("proposal_id", "settled-status-concede");
            concede.addProperty("actor_id", actor);
            concede.addProperty("player_id", actor);
            // The engine thread is held in the window for a second after the
            // game is marked over; the concession's own decision request is
            // answered inside that window.
            Thread opener = new Thread(() -> {
                try {
                    if (marked.await(30, java.util.concurrent.TimeUnit.SECONDS)) {
                        Thread.sleep(1_000L);
                    }
                } catch (InterruptedException exc) {
                    Thread.currentThread().interrupt();
                }
                release.countDown();
            });
            opener.setDaemon(true);
            opener.start();
            JsonObject settled = session.submitConcede(concede);
            assertTrue(marked.getCount() == 0, "the game must end by the concession");
            assertTrue(settled.get("decision").isJsonNull(), settled.toString());
            assertTrue(settled.get("terminal").getAsBoolean(), settled.toString());
            assertFalse(settled.get("engine_thread_alive").getAsBoolean(), settled.toString());
            JsonObject again = session.pendingDecisionPayload();
            assertTrue(again.get("terminal").getAsBoolean(), again.toString());
        } finally {
            release.countDown();
            XmageFullGameSession.afterTerminalMarked = () -> { };
        }
    }

    private static void releaseLater(CountDownLatch release) {
        Thread releaser = new Thread(() -> {
            try {
                Thread.sleep(200L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
            }
            release.countDown();
        });
        releaser.setDaemon(true);
        releaser.start();
    }

    private static List<String> rogShaiCopies(XmageDeckImporter importer, int count)
            throws Exception {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        JsonObject root = JsonParser.parseString(Files.readString(
                Path.of(repoRoot, "data", "decks", "rogshai_current.json"),
                StandardCharsets.UTF_8)).getAsJsonObject();
        List<String> mainboard = new ArrayList<>();
        List<String> commanders = new ArrayList<>();
        root.getAsJsonArray("cards").forEach(element -> {
            JsonObject card = element.getAsJsonObject();
            List<String> target = "commander".equals(card.get("zone").getAsString())
                    ? commanders : mainboard;
            for (int copy = 0; copy < card.get("quantity").getAsInt(); copy++) {
                target.add(card.get("oracle_name").getAsString());
            }
        });
        List<String> handles = new ArrayList<>();
        for (int copy = 0; copy < count; copy++) {
            handles.add(importer.importCommanderDeck(root.get("deck_id").getAsString(),
                    root.get("deck_hash").getAsString(), mainboard, commanders).deckHandle());
        }
        return handles;
    }
}

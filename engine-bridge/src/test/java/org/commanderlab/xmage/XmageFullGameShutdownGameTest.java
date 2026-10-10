package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 SLOT-06: {@code shutdown_game} on the full-game production lane.
 *
 * <p>Shutdown ends the native game, stops decision intake and ends the engine
 * thread; every later decision read, submission or concession is refused with a
 * typed {@code FULL_GAME_SHUT_DOWN} error, a second shutdown is refused, and the
 * engine process itself still answers (its own shutdown still works).</p>
 */
class XmageFullGameShutdownGameTest {

    @Test
    void shutdownEndsTheGameAndRefusesLaterDecisions() throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("issue662-shutdown", 2, 6650L);
        FullGameTestPilot.play(session, 40);
        JsonObject frame = session.legalActionsPayload();
        JsonObject proposal = FullGameTestPilot.choose(frame);

        JsonObject result = session.shutdownGame();
        assertTrue(result.get("shut_down").getAsBoolean());
        assertFalse(result.get("engine_thread_alive").getAsBoolean());
        assertTrue(result.get("game_over").getAsBoolean());

        JsonObject bound = new JsonObject();
        bound.addProperty("actor_id", frame.get("actor_id").getAsString());
        bound.addProperty("decision_class", frame.get("decision_class").getAsString());
        for (Runnable refused : new Runnable[] {
                session::legalActionsPayload,
                () -> session.legalActionsPayload(bound),
                () -> session.submitAction(proposal),
                () -> session.concedeOfferPayload(frame.get("actor_id").getAsString()),
                session::shutdownGame}) {
            XmageFullGameDecisionController.DecisionException failure = assertThrows(
                    XmageFullGameDecisionController.DecisionException.class, refused::run);
            assertTrue(failure.getMessage().startsWith("FULL_GAME_SHUT_DOWN"), failure.getMessage());
        }
        // The result and the public log stay readable after the shutdown.
        assertTrue(session.eventLogPayload(0).get("latest_offset").getAsInt() > 0);
    }

    @Test
    void bridgeShutdownGameKeepsTheEngineUp() {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        JsonObject before = response(bridge, "shutdown_game");
        assertFalse(before.get("success").getAsBoolean(), "no game to shut down yet");
        JsonObject engine = response(bridge, "shutdown_engine");
        assertTrue(engine.get("success").getAsBoolean());
        assertEquals(true, engine.getAsJsonObject("payload").get("shutdown").getAsBoolean());
    }

    private static JsonObject response(XmageFullGameJsonlBridge bridge, String type) {
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        request.addProperty("request_id", "issue662-" + type);
        request.addProperty("message_type", type);
        request.add("payload", new JsonObject());
        return JsonParser.parseString(bridge.handle(request.toString()).json()).getAsJsonObject();
    }
}

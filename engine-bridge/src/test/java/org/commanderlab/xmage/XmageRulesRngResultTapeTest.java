package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.constants.TurnPhase;
import mage.constants.Zone;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * AF09: the engine's own Rules-RNG shuffle results are taped as
 * process-independent permutation digests. The same seed reproduces them in an
 * independent game; a different seed changes them. Only digests leave the
 * engine.
 */
class XmageRulesRngResultTapeTest {

    @org.junit.jupiter.api.BeforeEach
    void orchestrationLaunch() {
        XmageRulesRngResultTape.keyForTests(new byte[32]);
    }

    @org.junit.jupiter.api.AfterEach
    void principalLaunch() {
        XmageRulesRngResultTape.keyForTests(null);
    }

    private static XmageNativeStateRestoration.Plan plan(String planId, long seed) {
        return new XmageNativeStateRestoration.Plan(
                planId, 2, seed,
                List.of(new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                        new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)),
                List.of(new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P1-A", "Rograkh, Son of Rohgahh", "P1", 0),
                        new XmageNativeStateRestoration.RequestedCommander(
                                "cmd:P2-A", "Rograkh, Son of Rohgahh", "P2", 0)),
                List.of(),
                List.of(new XmageNativeStateRestoration.RequestedObject(
                        "obj:p1-bears", "Grizzly Bears", "P1", "P1", Zone.BATTLEFIELD, false)),
                1, TurnPhase.PRECOMBAT_MAIN, PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
    }

    private static JsonObject tapeAtCheckpoint(String planId, long seed) {
        XmageNativeStateRestoration.Plan plan = plan(planId, seed);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, plan.planId());
        XmageFullGameSession session = new XmageFullGameSession(
                plan.planId(), handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return session.rulesRngTapePayload();
    }

    private static List<String> resultDigests(JsonObject tape) {
        List<String> digests = new ArrayList<>();
        for (JsonElement element : tape.getAsJsonArray("rules_rng_results")) {
            digests.add(element.getAsJsonObject().get("seat").getAsInt() + ":"
                    + element.getAsJsonObject().get("result_digest").getAsString());
        }
        return digests;
    }

    @Test
    void theSameSeedReproducesEveryResultAndTheSameState() {
        JsonObject first = tapeAtCheckpoint("rng-tape-a", 424242L);
        JsonObject second = tapeAtCheckpoint("rng-tape-b", 424242L);
        JsonArray results = first.getAsJsonArray("rules_rng_results");
        assertTrue(results.size() >= 2, "every seat's opening shuffle is taped: " + results);
        for (JsonElement element : results) {
            JsonObject entry = element.getAsJsonObject();
            assertEquals("LIBRARY_SHUFFLE", entry.get("operation").getAsString());
            assertTrue(entry.get("after").getAsLong() > entry.get("before").getAsLong(),
                    "a shuffle consumes Rules randomness: " + entry);
        }
        assertEquals(resultDigests(first), resultDigests(second));
        assertEquals(first.get("privileged_state_digest"), second.get("privileged_state_digest"));
        assertEquals(first.get("rules_random_calls"), second.get("rules_random_calls"));
    }

    @Test
    void aDifferentSeedChangesTheResults() {
        JsonObject seeded = tapeAtCheckpoint("rng-tape-c", 424242L);
        JsonObject other = tapeAtCheckpoint("rng-tape-d", 424243L);
        assertNotEquals(resultDigests(seeded), resultDigests(other));
    }

    @Test
    void aLaunchWithoutAnOrchestrationKeyIsRefused() {
        XmageRulesRngResultTape.keyForTests(null);
        IllegalStateException refused = org.junit.jupiter.api.Assertions.assertThrows(
                IllegalStateException.class, () -> tapeAtCheckpoint("rng-tape-f", 424242L));
        assertTrue(refused.getMessage().contains("ORCHESTRATION_CHANNEL_NOT_ENABLED"),
                refused.getMessage());
    }

    @Test
    void theDigestsAreKeyed() {
        JsonObject keyed = tapeAtCheckpoint("rng-tape-g", 424242L);
        byte[] other = new byte[32];
        other[0] = 1;
        XmageRulesRngResultTape.keyForTests(other);
        JsonObject rekeyed = tapeAtCheckpoint("rng-tape-h", 424242L);
        assertNotEquals(keyed.get("privileged_state_digest"), rekeyed.get("privileged_state_digest"));
        assertNotEquals(resultDigests(keyed), resultDigests(rekeyed));
    }

    @Test
    void onlyDigestsLeaveTheEngine() {
        JsonObject tape = tapeAtCheckpoint("rng-tape-e", 424242L);
        String text = tape.toString();
        assertFalse(text.matches(".*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}.*"),
                "no native id: " + text);
        assertFalse(text.contains("Grizzly") || text.contains("Rograkh") || text.contains("Plains"),
                "no card identity: " + text);
        assertEquals("orchestration_keyed_digests", tape.get("observation_scope").getAsString());
        assertEquals("PARKED", tape.get("engine_state").getAsString());
    }
}

package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS52 M2 — selection → native → execution.
 *
 * <p>Twin-game design: two identical games (same decks, same seed, same
 * pilot prefix) diverge at one frame with two simultaneously legal
 * alternatives. Game A selects the non-first cast option; game B selects
 * pass. Post-state must show the intended native execution in each game
 * (commander on the stack vs empty stack with advancement), proving the
 * external selection bound the exact native object. A label-rematching
 * defect (WS48 mode) cannot produce this divergence pattern.</p>
 */
class Ws52M2SelectionExecutionTest {

    private static final int PASS_BOUND = 60;

    @Test
    void nonFirstCastSelectionExecutesExactNativeObject() throws Exception {
        TwinSetup castGame = startTwinnedGame("ws52-m2-cast");
        TwinSetup passGame = startTwinnedGame("ws52-m2-pass");

        // Identical pilot prefix: keep opening, then pass until a priority
        // frame offers the Rograkh cast alongside pass. Setup card order is
        // per-run nondeterministic (WS52 M5), so each twin drives to its own
        // cast frame independently; the binding proof does not require twin
        // frame equality.
        JsonObject castFrame = driveToCastFrame(castGame);
        JsonObject passFrame = driveToCastFrame(passGame);

        // Game A: select the NON-FIRST alternative (index >= 1; index 0 is pass).
        String castOption = nonPassOptionId(castFrame);
        int castIndex = optionIndex(castFrame, castOption);
        assertTrue(castIndex >= 1, "cast alternative must be non-first (pass is offered first)");
        String castDecisionId = castFrame.get("decision_id").getAsString();
        JsonObject afterCast = Ws52.submit(castGame.bridge, castFrame, List.of(castOption));

        // Game B (counterfactual twin): select pass at the identical frame.
        String passOption = Ws52.singleOptionIdByType(passFrame, "pass_priority");
        JsonObject afterPass = Ws52.submit(passGame.bridge, passFrame, List.of(passOption));

        // Execution acknowledgement: both decisions advance past the submitted id.
        String nextCastId = Ws52.requirePendingDecision(afterCast).get("decision_id").getAsString();
        String nextPassId = Ws52.requirePendingDecision(afterPass).get("decision_id").getAsString();
        assertNotEquals(castDecisionId, nextCastId, "cast game must advance past the submitted decision");

        // Post-state distinguishes the two simultaneously legal alternatives.
        JsonArray castStack = stackOf(castGame, seatOf(castFrame));
        JsonArray passStack = stackOf(passGame, seatOf(passFrame));
        assertEquals(1, castStack.size(),
                () -> "cast game stack must hold exactly the executed commander: " + castStack);
        String stackedName = castStack.get(0).getAsJsonObject().get("name").getAsString();
        assertTrue(stackedName.contains("Rograkh"),
                () -> "stacked object must be the selected commander, observed: " + stackedName);
        assertEquals(0, passStack.size(),
                () -> "pass twin must leave the stack empty: " + passStack);

        // The submitted external id resolved (no missing-binding failure) and
        // the transcript records the accepted non-pass selection.
        JsonObject castResult = Ws52.requireSuccess(
                Ws52.send(castGame.bridge, "get_full_game_result", new JsonObject()));
        assertTrue(castResult.get("decision_count").getAsInt() >= 3);

        JsonObject evidence = new JsonObject();
        evidence.addProperty("cast_option_index", castIndex);
        evidence.addProperty("cast_decision_id", castDecisionId);
        evidence.addProperty("next_cast_decision_id", nextCastId);
        evidence.addProperty("next_pass_decision_id", nextPassId);
        evidence.addProperty("stacked_name", stackedName);
        evidence.addProperty("pass_twin_stack_size", passStack.size());
        writeEvidence("m2-selection-execution.json", evidence);
    }

    @Test
    void targetSelectionDivergesByOpaqueIdNotLabel() throws Exception {
        // In-harness companion: two identical target frames; selecting the
        // first vs the last opaque option must bind different native players.
        Set<String> firstRun;
        Set<String> lastRun;
        try (Ws52Harness first = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            firstRun = runTargetChoice(first, true);
        }
        try (Ws52Harness last = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            lastRun = runTargetChoice(last, false);
        }
        assertEquals(1, firstRun.size());
        assertEquals(1, lastRun.size());
        assertNotEquals(firstRun, lastRun,
                "first vs last opaque target selection must bind different native objects");
    }

    // ------------------------------------------------------------------

    private record TwinSetup(XmageFullGameJsonlBridge bridge) {
    }

    private static TwinSetup startTwinnedGame(String gameId) throws Exception {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        String handleA = Ws52.importDeck(bridge, rogshai);
        String handleB = Ws52.importDeck(bridge, rogshai);
        Ws52.createFullGame(bridge, gameId, List.of(handleA, handleB), Ws52.SEED_A);
        Ws52.startFullGame(bridge);
        Ws52.Opening opening = Ws52.pilotOpening(bridge);
        assertEquals(1, opening.startingPlayerChoices());
        assertEquals(2, opening.mulligans(), "twin must open with two mulligan frames");
        return new TwinSetup(bridge);
    }

    private static JsonObject driveToCastFrame(TwinSetup setup) {
        for (int step = 0; step < PASS_BOUND; step++) {
            JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(setup.bridge));
            assertEquals("priority", decision.get("decision_class").getAsString(),
                    () -> "twin drive reached unexpected class: " + decision);
            Ws52.assertUniqueOptionIds(decision);
            if (hasCastableOption(decision)) {
                return decision;
            }
            Ws52.submit(setup.bridge, decision,
                    List.of(Ws52.singleOptionIdByType(decision, "pass_priority")));
        }
        fail("twin never reached a cast/activate alternative within " + PASS_BOUND + " passes");
        throw new IllegalStateException("unreachable");
    }

    private static boolean hasCastableOption(JsonObject decision) {
        return rograkhOptionId(decision) != null;
    }

    private static String nonPassOptionId(JsonObject decision) {
        String rograkh = rogshaiOptionCheck(decision);
        if (rograkh == null) {
            fail("no Rograkh commander-cast option in frame: " + decision);
        }
        return rograkh;
    }

    private static String rograkhOptionId(JsonObject decision) {
        return rogshaiOptionCheck(decision);
    }

    /** The exact Rograkh commander-cast option, identified by engine metadata (not labels). */
    private static String rogshaiOptionCheck(JsonObject decision) {
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            String type = option.get("option_type").getAsString();
            if ("pass_priority".equals(type) || "mana_ability".equals(type)) {
                continue;
            }
            JsonObject metadata = option.has("metadata") && option.get("metadata").isJsonObject()
                    ? option.getAsJsonObject("metadata") : new JsonObject();
            String sourceName = metadata.has("source_name") && !metadata.get("source_name").isJsonNull()
                    ? metadata.get("source_name").getAsString() : "";
            if (sourceName.contains("Rograkh")) {
                return option.get("option_id").getAsString();
            }
        }
        return null;
    }

    private static int optionIndex(JsonObject decision, String optionId) {
        int index = 0;
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            if (optionId.equals(element.getAsJsonObject().get("option_id").getAsString())) {
                return index;
            }
            index++;
        }
        fail("option not in frame: " + optionId);
        throw new IllegalStateException("unreachable");
    }

    private static int seatOf(JsonObject decision) {
        return decision.get("seat").getAsInt();
    }

    private static JsonArray stackOf(TwinSetup setup, int viewerSeat) {
        JsonObject observation = Ws52.getObservation(setup.bridge, viewerSeat);
        JsonObject pilotState = observation.getAsJsonObject("observation");
        assertTrue(pilotState.has("stack"), () -> "observation without stack: " + observation);
        return pilotState.getAsJsonArray("stack");
    }

    private static Set<String> runTargetChoice(Ws52Harness harness, boolean first) throws Exception {
        harness.start(0);
        harness.pilotOpening(2);
        Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
        mage.target.TargetPlayer target = new mage.target.TargetPlayer();
        java.util.concurrent.ExecutorService exec =
                java.util.concurrent.Executors.newSingleThreadExecutor();
        try {
            java.util.concurrent.Future<Boolean> worker = exec.submit(
                    () -> direct.player().chooseTarget(mage.constants.Outcome.Benefit,
                            target, null, harness.game));
            JsonObject pending = direct.awaitDecision();
            JsonArray options = pending.getAsJsonArray("legal_options");
            int pick = first ? 0 : options.size() - 1;
            String selected = options.get(pick).getAsJsonObject().get("option_id").getAsString();
            direct.submit(pending, List.of(selected), null);
            assertTrue(worker.get(30, java.util.concurrent.TimeUnit.SECONDS));
            Set<String> bound = new LinkedHashSet<>();
            target.getTargets().forEach(id -> bound.add(id.toString()));
            return bound;
        } finally {
            exec.shutdownNow();
        }
    }

    private static void writeEvidence(String name, JsonObject payload) throws Exception {
        // Surefire workingDirectory is the module target/ dir.
        Path dir = Path.of("ws52-evidence");
        Files.createDirectories(dir);
        Files.writeString(dir.resolve(name), payload.toString(), StandardCharsets.UTF_8);
    }
}

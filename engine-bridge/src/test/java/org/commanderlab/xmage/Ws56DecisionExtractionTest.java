package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.ActivatedAbility;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS56 M1/M2 — Authoritative decision extraction + selection→native→execution
 * on the successor (with freshness + mode reassessment).
 *
 * <p>M1: legal Decision options still originate from XMage; no legality
 * reconstruction in CPL; mode handling explicitly reassessed (visible modes
 * cross with opaque identity; hidden-library modal source still fails closed
 * via the gateway — see Ws56ModeIdentityTest for the full mode matrix).</p>
 *
 * <p>M2: external selected option → exactly one current native binding →
 * intended native execution, with competing alternatives and non-first
 * choices.</p>
 */
class Ws56DecisionExtractionTest {

    @Test
    void m1PriorityFrameEqualsEnginePlayableSet() throws Exception {
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        try (Ws52Harness harness = new Ws52Harness("ws56-m1",
                rogshai.mainboard(), rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            harness.start(0);
            harness.pilotOpening(2);
            JsonObject credited = null;
            for (int step = 0; step < 60; step++) {
                JsonObject pending = harness.awaitFrame();
                assertEquals("priority", pending.get("decision_class").getAsString());
                Ws52.assertUniqueOptionIds(pending);
                // Freshness present on every credited frame.
                assertTrue(pending.has("frame_digest") && pending.has("option_digest"),
                        "M1 frame must carry freshness: " + pending);
                if (hasNonPassOption(pending)) {
                    credited = pending;
                    break;
                }
                harness.submit(pending, List.of(Ws52.singleOptionIdByType(pending, "pass_priority")), null);
            }
            assertNotNull(credited, "no priority frame with cast/activate within 60 passes");

            UUID actorId = UUID.fromString(credited.get("actor_id").getAsString());
            Player actor = harness.game.getPlayer(actorId);
            assertNotNull(actor);
            List<ActivatedAbility> playable = actor.getPlayable(harness.game, false);
            Set<String> expectedIds = new LinkedHashSet<>();
            expectedIds.add(XmageFullGameDecisionController.stableId(
                    "priority-pass", actor.getId().toString()));
            for (ActivatedAbility ability : playable) {
                String source = ability.getSourceId() == null ? "<none>" : ability.getSourceId().toString();
                expectedIds.add(XmageFullGameDecisionController.stableId(
                        "priority", source, ability.getOriginalId().toString()));
            }
            Set<String> offeredIds = new LinkedHashSet<>();
            for (JsonElement e : credited.getAsJsonArray("legal_options")) {
                offeredIds.add(e.getAsJsonObject().get("option_id").getAsString());
            }
            assertEquals(expectedIds, offeredIds,
                    "credited priority set must equal engine playable set exactly (successor)");
            long passCount = credited.getAsJsonArray("legal_options").asList().stream()
                    .map(e -> e.getAsJsonObject())
                    .filter(o -> "pass_priority".equals(o.get("option_type").getAsString()))
                    .count();
            assertEquals(1, passCount);

            Set<String> forbidden = harness.ledger.forbiddenIdentityTokens(harness.game, actor);
            String frameText = credited.toString();
            for (String token : forbidden) {
                if (token == null || token.isBlank()) continue;
                assertTrue(!frameText.contains(token), () -> "hidden token in M1 frame: " + token);
            }
            JsonObject evidence = new JsonObject();
            evidence.addProperty("offered_options", offeredIds.size());
            evidence.addProperty("engine_playable", playable.size() + 1);
            evidence.addProperty("freshness_present", true);
            evidence.addProperty("mode_reassessment", "visible modes cross (Ws56ModeIdentityTest); hidden-library modal source still fail-closed via gateway");
            writeEvidence("m1-extraction.json", evidence);
        }
    }

    @Test
    void m1TargetFrameEqualsEnginePossibleTargets() throws Exception {
        try (Ws52Harness harness = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            mage.target.TargetPlayer target = new mage.target.TargetPlayer();
            java.util.concurrent.ExecutorService exec = java.util.concurrent.Executors.newSingleThreadExecutor();
            try {
                java.util.concurrent.Future<Boolean> worker = exec.submit(
                        () -> direct.player().chooseTarget(
                                mage.constants.Outcome.Benefit, target, null, harness.game));
                JsonObject pending = direct.awaitDecision();
                assertEquals("target", pending.get("decision_class").getAsString());
                Ws52.assertUniqueOptionIds(pending);
                Set<UUID> possible = target.possibleTargets(direct.player().getId(), null, harness.game);
                assertTrue(possible.size() >= 2);
                assertEquals(possible.size(), pending.getAsJsonArray("legal_options").size());
                for (JsonElement e : pending.getAsJsonArray("legal_options")) {
                    String id = e.getAsJsonObject().get("option_id").getAsString();
                    assertTrue(id.startsWith("obj-"), "target id must be opaque handle: " + id);
                }
                JsonArray options = pending.getAsJsonArray("legal_options");
                String selected = options.get(options.size() - 1).getAsJsonObject().get("option_id").getAsString();
                direct.submit(pending, List.of(selected), null);
                assertTrue(worker.get(30, java.util.concurrent.TimeUnit.SECONDS));
                assertEquals(1, target.getTargets().size());
                assertTrue(harness.game.getPlayer(target.getTargets().iterator().next()) != null);
            } finally {
                exec.shutdownNow();
            }
        }
    }

    @Test
    void m2NonFirstCastExecutesExactNative() throws Exception {
        TwinSetup castGame = startTwinnedGame("ws56-m2-cast");
        TwinSetup passGame = startTwinnedGame("ws56-m2-pass");
        JsonObject castFrame = driveToCastFrame(castGame);
        JsonObject passFrame = driveToCastFrame(passGame);
        String castOption = nonPassOptionId(castFrame);
        int castIndex = optionIndex(castFrame, castOption);
        assertTrue(castIndex >= 1, "cast must be non-first (pass is first)");
        String castDecisionId = castFrame.get("decision_id").getAsString();
        JsonObject afterCast = Ws52.submit(castGame.bridge, castFrame, List.of(castOption));
        String passOption = Ws52.singleOptionIdByType(passFrame, "pass_priority");
        JsonObject afterPass = Ws52.submit(passGame.bridge, passFrame, List.of(passOption));
        String nextCastId = Ws52.requirePendingDecision(afterCast).get("decision_id").getAsString();
        String nextPassId = Ws52.requirePendingDecision(afterPass).get("decision_id").getAsString();
        assertNotEquals(castDecisionId, nextCastId);
        JsonArray castStack = stackOf(castGame, seatOf(castFrame));
        JsonArray passStack = stackOf(passGame, seatOf(passFrame));
        assertEquals(1, castStack.size(), () -> "cast stack must hold commander: " + castStack);
        assertTrue(castStack.get(0).getAsJsonObject().get("name").getAsString().contains("Rograkh"));
        assertEquals(0, passStack.size(), () -> "pass twin must leave stack empty: " + passStack);
        JsonObject evidence = new JsonObject();
        evidence.addProperty("cast_option_index", castIndex);
        evidence.addProperty("stacked_name", castStack.get(0).getAsJsonObject().get("name").getAsString());
        evidence.addProperty("pass_twin_stack_size", passStack.size());
        evidence.addProperty("next_cast_id", nextCastId);
        evidence.addProperty("next_pass_id", nextPassId);
        writeEvidence("m2-selection.json", evidence);
    }

    @Test
    void m2TargetDivergesByOpaqueId() throws Exception {
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
        assertNotEquals(firstRun, lastRun, "first vs last opaque target must bind different natives");
    }

    // ------------------------------------------------------------------

    private record TwinSetup(XmageFullGameJsonlBridge bridge) {}

    private static TwinSetup startTwinnedGame(String gameId) throws Exception {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        String handleA = Ws52.importDeck(bridge, rogshai);
        String handleB = Ws52.importDeck(bridge, rogshai);
        Ws52.createFullGame(bridge, gameId, List.of(handleA, handleB), Ws52.SEED_A);
        Ws52.startFullGame(bridge);
        Ws52.Opening opening = Ws52.pilotOpening(bridge);
        assertEquals(1, opening.startingPlayerChoices());
        assertEquals(2, opening.mulligans());
        return new TwinSetup(bridge);
    }

    private static JsonObject driveToCastFrame(TwinSetup setup) {
        for (int step = 0; step < 60; step++) {
            JsonObject decision = Ws52.requirePendingDecision(Ws52.getDecision(setup.bridge));
            assertEquals("priority", decision.get("decision_class").getAsString());
            Ws52.assertUniqueOptionIds(decision);
            if (rograkhOptionId(decision) != null) return decision;
            Ws52.submit(setup.bridge, decision,
                    List.of(Ws52.singleOptionIdByType(decision, "pass_priority")));
        }
        fail("twin never reached cast alternative");
        throw new IllegalStateException("unreachable");
    }

    private static String nonPassOptionId(JsonObject decision) {
        String r = rograkhOptionId(decision);
        if (r == null) fail("no Rograkh option in frame: " + decision);
        return r;
    }

    private static String rograkhOptionId(JsonObject decision) {
        for (JsonElement e : decision.getAsJsonArray("legal_options")) {
            JsonObject o = e.getAsJsonObject();
            String type = o.get("option_type").getAsString();
            if ("pass_priority".equals(type) || "mana_ability".equals(type)) continue;
            JsonObject meta = o.has("metadata") && o.get("metadata").isJsonObject()
                    ? o.getAsJsonObject("metadata") : new JsonObject();
            String sourceName = meta.has("source_name") && !meta.get("source_name").isJsonNull()
                    ? meta.get("source_name").getAsString() : "";
            if (sourceName.contains("Rograkh")) return o.get("option_id").getAsString();
        }
        return null;
    }

    private static int optionIndex(JsonObject decision, String optionId) {
        int i = 0;
        for (JsonElement e : decision.getAsJsonArray("legal_options")) {
            if (optionId.equals(e.getAsJsonObject().get("option_id").getAsString())) return i;
            i++;
        }
        fail("option not in frame");
        throw new IllegalStateException("unreachable");
    }

    private static int seatOf(JsonObject decision) { return decision.get("seat").getAsInt(); }

    private static JsonArray stackOf(TwinSetup setup, int viewerSeat) {
        JsonObject obs = Ws52.getObservation(setup.bridge, viewerSeat);
        return obs.getAsJsonObject("observation").getAsJsonArray("stack");
    }

    private static Set<String> runTargetChoice(Ws52Harness harness, boolean first) throws Exception {
        harness.start(0);
        harness.pilotOpening(2);
        Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
        mage.target.TargetPlayer target = new mage.target.TargetPlayer();
        java.util.concurrent.ExecutorService exec = java.util.concurrent.Executors.newSingleThreadExecutor();
        try {
            java.util.concurrent.Future<Boolean> worker = exec.submit(
                    () -> direct.player().chooseTarget(mage.constants.Outcome.Benefit, target, null, harness.game));
            JsonObject pending = direct.awaitDecision();
            JsonArray options = pending.getAsJsonArray("legal_options");
            int pick = first ? 0 : options.size() - 1;
            String selected = options.get(pick).getAsJsonObject().get("option_id").getAsString();
            direct.submit(pending, List.of(selected), null);
            assertTrue(worker.get(30, java.util.concurrent.TimeUnit.SECONDS));
            Set<String> bound = new LinkedHashSet<>();
            target.getTargets().forEach(id -> bound.add(id.toString()));
            return bound;
        } finally { exec.shutdownNow(); }
    }

    private static boolean hasNonPassOption(JsonObject decision) {
        for (JsonElement e : decision.getAsJsonArray("legal_options")) {
            if (!"pass_priority".equals(e.getAsJsonObject().get("option_type").getAsString())) return true;
        }
        return false;
    }

    private static void writeEvidence(String name, JsonObject payload) throws Exception {
        Path dir = Path.of("ws56-evidence");
        Files.createDirectories(dir);
        Files.writeString(dir.resolve(name), payload.toString(), StandardCharsets.UTF_8);
    }
}

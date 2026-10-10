package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 SLOT-06 (c): {@code export_replay} plus a clean-process verifier.
 *
 * <ul>
 *   <li>R1: the export carries protocol version, engine identity, seed, decklists,
 *       seating and the ordered semantic decision record.</li>
 *   <li>R2: a fresh JVM ({@code Main full-game-replay <export>}) replays it from
 *       the export alone; every frame's offered-option digest and the final
 *       semantic state digest must match (2P and 4P real decks).</li>
 *   <li>R3: a tampered choice, a tampered seed, a truncated record, a broken record
 *       digest each end as DIVERGED, never as a match; an export before start is
 *       refused.</li>
 *   <li>R3: a frame the tape does not cover (the engine asks again after the last
 *       recorded decision, or on a different frame) is reported as
 *       {@code unrecorded_frame} at the record's end; a broken or missing
 *       {@code ordering_keys} or {@code final_pending} is a divergence.</li>
 *   <li>R4: no pilot-facing frame carries the record or the export; verifier
 *       errors carry only the exception class and typed code.</li>
 *   <li>The verifier ends its own game ({@code shutdown_clean}).</li>
 * </ul>
 */
class XmageFullGameReplayExportTest {

    private static final int DECISIONS = 160;

    @ParameterizedTest(name = "{0} players, seed {1}")
    @CsvSource({"2, 6660", "4, 6661"})
    void freshJvmReplaysTheExport(int players, long seed) throws Exception {
        JsonObject export = recordedExport(players, seed);
        assertEquals(XmageFullGameReplay.SCHEMA_VERSION, export.get("schema_version").getAsString());
        assertEquals(seed, export.get("seed").getAsLong());
        assertEquals(players, export.getAsJsonArray("decks").size());
        assertTrue(export.get("decision_count").getAsInt() >= DECISIONS / 2, "non-vacuous record");
        assertEquals("orchestration_only", export.get("scope").getAsString());

        assertTrue(export.has("final_pending"), "the export names the frame it ended on");
        for (JsonElement element : export.getAsJsonArray("decisions")) {
            JsonObject entry = element.getAsJsonObject();
            if ("decision".equals(entry.get("kind").getAsString())) {
                assertTrue(entry.has("ordering_keys"), "decision " + entry.get("index") + " records no ordering");
            }
        }

        JsonObject verdict = replayInFreshJvm(export);
        assertEquals("REPLAY_MATCH", verdict.get("verdict").getAsString(), verdict.toString());
        assertEquals(export.get("final_state_digest").getAsString(), verdict.get("final_state_digest").getAsString());
        assertTrue(verdict.get("shutdown_clean").getAsBoolean(), "the verifier ended its own game: " + verdict);
    }

    @Test
    void tamperedChoiceSeedTruncationAndDigestDiverge() throws Exception {
        JsonObject export = recordedExport(2, 6662L);
        JsonArray decisions = export.getAsJsonArray("decisions");

        // Tampered choice: the first priority decision that passed is changed to play
        // differently is not guaranteed; instead swap a chosen key for another key
        // the same frame offered, found by replaying the frame's offered set.
        JsonObject tamperedChoice = export.deepCopy();
        int tampered = swapFirstChoice(tamperedChoice);
        refreshDigest(tamperedChoice);
        JsonObject choiceVerdict = replayInFreshJvm(tamperedChoice);
        assertEquals("DIVERGED", choiceVerdict.get("verdict").getAsString(), choiceVerdict.toString());
        assertTrue(choiceVerdict.get("first_divergence_index").getAsInt() >= tampered, choiceVerdict.toString());

        JsonObject tamperedSeed = export.deepCopy();
        tamperedSeed.addProperty("seed", export.get("seed").getAsLong() + 1);
        JsonObject seedVerdict = replayInFreshJvm(tamperedSeed);
        assertEquals("DIVERGED", seedVerdict.get("verdict").getAsString(), seedVerdict.toString());

        JsonObject truncated = export.deepCopy();
        JsonArray kept = new JsonArray();
        for (int index = 0; index < decisions.size() - 5; index++) {
            kept.add(decisions.get(index));
        }
        truncated.add("decisions", kept);
        truncated.addProperty("decision_count", kept.size());
        refreshDigest(truncated);
        JsonObject truncatedVerdict = replayInFreshJvm(truncated);
        assertEquals("DIVERGED", truncatedVerdict.get("verdict").getAsString(), truncatedVerdict.toString());
        // The engine asks for the first dropped frame; the tape has none for it.
        assertEquals("unrecorded_frame", truncatedVerdict.get("field").getAsString(), truncatedVerdict.toString());
        assertEquals(kept.size(), truncatedVerdict.get("first_divergence_index").getAsInt());

        int first = firstDecisionIndex(decisions);
        JsonObject badOrdering = export.deepCopy();
        JsonArray bogus = new JsonArray();
        bogus.add("generic|not offered#1");
        badOrdering.getAsJsonArray("decisions").get(first).getAsJsonObject().add("ordering_keys", bogus);
        refreshDigest(badOrdering);
        JsonObject orderingVerdict = replayInFreshJvm(badOrdering);
        assertEquals("DIVERGED", orderingVerdict.get("verdict").getAsString(), orderingVerdict.toString());
        assertEquals("ordering_key", orderingVerdict.get("field").getAsString());
        assertEquals(first, orderingVerdict.get("first_divergence_index").getAsInt());

        JsonObject missingOrdering = export.deepCopy();
        missingOrdering.getAsJsonArray("decisions").get(first).getAsJsonObject().remove("ordering_keys");
        refreshDigest(missingOrdering);
        JsonObject missingVerdict = replayInFreshJvm(missingOrdering);
        assertEquals("DIVERGED", missingVerdict.get("verdict").getAsString(), missingVerdict.toString());
        assertEquals("ordering_keys", missingVerdict.get("field").getAsString());

        // A concession the replayed engine refuses (the same seat conceding twice)
        // is a divergence, not an error.
        JsonObject badConcession = export.deepCopy();
        JsonArray withConcede = new JsonArray();
        for (int copy = 0; copy < 2; copy++) {
            JsonObject concede = new JsonObject();
            concede.addProperty("kind", "concede");
            concede.addProperty("index", copy);
            concede.addProperty("actor_seat", 1);
            withConcede.add(concede);
        }
        badConcession.getAsJsonArray("decisions").forEach(withConcede::add);
        badConcession.add("decisions", withConcede);
        badConcession.addProperty("decision_count", withConcede.size());
        refreshDigest(badConcession);
        JsonObject concessionVerdict = replayInFreshJvm(badConcession);
        assertEquals("DIVERGED", concessionVerdict.get("verdict").getAsString(), concessionVerdict.toString());
        assertEquals("concession", concessionVerdict.get("field").getAsString(), concessionVerdict.toString());
        assertEquals(1, concessionVerdict.get("first_divergence_index").getAsInt());

        // The engine's own decision offset binds each entry to its frame.
        JsonObject badOffset = export.deepCopy();
        JsonObject shifted = badOffset.getAsJsonArray("decisions").get(first).getAsJsonObject();
        shifted.addProperty("decision_offset", shifted.get("decision_offset").getAsLong() + 1);
        refreshDigest(badOffset);
        JsonObject offsetVerdict = replayInFreshJvm(badOffset);
        assertEquals("DIVERGED", offsetVerdict.get("verdict").getAsString(), offsetVerdict.toString());
        assertEquals("decision_offset", offsetVerdict.get("field").getAsString());
        assertEquals(first, offsetVerdict.get("first_divergence_index").getAsInt());

        // The replayed engine must end in the exported engine state.
        JsonObject otherState = export.deepCopy();
        otherState.addProperty("final_engine_state", "CLEAN_TERMINAL");
        JsonObject stateVerdict = replayInFreshJvm(otherState);
        assertEquals("DIVERGED", stateVerdict.get("verdict").getAsString(), stateVerdict.toString());
        assertEquals("engine_state", stateVerdict.get("field").getAsString());
        assertEquals("PARKED", stateVerdict.get("observed").getAsString());

        JsonObject missingFrame = export.deepCopy();
        missingFrame.remove("final_pending");
        JsonObject frameVerdict = replayInFreshJvm(missingFrame);
        assertEquals("DIVERGED", frameVerdict.get("verdict").getAsString(), frameVerdict.toString());
        assertEquals("final_pending", frameVerdict.get("field").getAsString());

        JsonObject brokenDigest = export.deepCopy();
        brokenDigest.addProperty("decisions_digest", "0".repeat(64));
        JsonObject digestVerdict = replayInFreshJvm(brokenDigest);
        assertEquals("DIVERGED", digestVerdict.get("verdict").getAsString());
        assertEquals("decisions_digest", digestVerdict.get("field").getAsString());
    }

    @Test
    void exportBeforeStartIsRefusedAndNoPilotFrameCarriesTheRecord() throws Exception {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        request.addProperty("request_id", "issue662-replay");
        request.addProperty("message_type", "export_replay");
        request.add("payload", new JsonObject());
        JsonObject response = JsonParser.parseString(bridge.handle(request.toString()).json()).getAsJsonObject();
        assertFalse(response.get("success").getAsBoolean(), "no replay export without a started game");

        XmageFullGameSession session = FullGameTestPilot.realDeckSession("issue662-replay-r4", 2, 6663L);
        for (int step = 0; step < 60; step++) {
            JsonObject frame = session.legalActionsPayload();
            String text = frame.toString();
            for (String field : List.of("\"decisions\"", "\"decks\"", "\"offered_digest\"",
                    "\"chosen_keys\"", "\"final_state_digest\"", "\"decisions_digest\"")) {
                assertFalse(text.contains(field), "a pilot-facing frame carries " + field);
            }
            session.submitAction(FullGameTestPilot.choose(frame));
        }
    }

    @Test
    void verifierErrorsCarryOnlyClassAndTypedCode() throws Exception {
        assertEquals("DecisionException: ILLEGAL_ACTION", XmageFullGameReplayVerifier.redactedError(
                new XmageFullGameDecisionController.DecisionException(
                        "ILLEGAL_ACTION: option not offered by XMage: 3f2b9c1e-0000-4000-8000-000000000000")));
        assertEquals("IllegalStateException", XmageFullGameReplayVerifier.redactedError(
                new IllegalStateException("Sol Ring is in the library of seat 2 at /tmp/secret.json")));

        // In-process run on an export whose deck import fails with a message that
        // names a card: the raw message carries it, the verdict must not.
        String secret = "Zzyzx Hidden Library Card";
        List<String> main = new ArrayList<>();
        main.add(secret);
        for (int copy = 0; copy < 98; copy++) {
            main.add("Island");
        }
        RuntimeException raw = org.junit.jupiter.api.Assertions.assertThrows(RuntimeException.class,
                () -> new XmageDeckImporter().importCommanderDeck(
                        "secret-deck-id", "0".repeat(64), main, List.of("Atraxa, Praetors' Voice")));
        assertTrue(raw.getMessage().contains("Zzyzx"), "non-vacuous: the raw failure names the card");

        JsonObject export = new JsonObject();
        export.addProperty("schema_version", XmageFullGameReplay.SCHEMA_VERSION);
        JsonArray decisions = new JsonArray();
        export.add("decisions", decisions);
        export.addProperty("decision_count", 0);
        export.addProperty("decisions_digest", XmageFullGameReplay.sha256(decisions.toString()));
        JsonObject deck = new JsonObject();
        deck.addProperty("deck_id", "secret-deck-id");
        deck.addProperty("deck_hash", "0".repeat(64));
        JsonArray mainboard = new JsonArray();
        main.forEach(mainboard::add);
        deck.add("mainboard", mainboard);
        JsonArray commanders = new JsonArray();
        commanders.add("Atraxa, Praetors' Voice");
        deck.add("commanders", commanders);
        JsonArray decks = new JsonArray();
        decks.add(deck);
        export.add("decks", decks);
        Path file = FullGameTestPilot.writeTemp("issue662-replay-error", export);
        java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
        int code = XmageFullGameReplayVerifier.run(file, new java.io.PrintStream(bytes, true, StandardCharsets.UTF_8));
        String printed = bytes.toString(StandardCharsets.UTF_8);
        assertEquals(2, code);
        assertTrue(printed.contains("\"verdict\":\"ERROR\""));
        for (String leak : List.of("Zzyzx", "secret-deck-id", file.toString())) {
            assertFalse(printed.contains(leak), "verifier error leaks a recorded value");
        }
    }

    @Test
    void aNonEmptyOrderingIsRecordedAndReplayed() throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession("issue662-ordering", 2, 6665L);
        List<String> orderedKeys = null;
        for (int step = 0; step < 60 && orderedKeys == null; step++) {
            JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
            JsonArray options = pending.getAsJsonArray("legal_options");
            String passId = null;
            for (JsonElement element : options) {
                JsonObject option = element.getAsJsonObject();
                if ("pass_priority".equals(option.has("option_type") ? option.get("option_type").getAsString() : "")) {
                    passId = option.get("option_id").getAsString();
                }
            }
            if ("priority".equals(pending.get("decision_class").getAsString()) && passId != null && options.size() > 1) {
                List<String> ids = XmageFullGameReplay.optionIds(options);
                List<String> keys = XmageFullGameReplay.semanticKeys(options);
                JsonArray selected = new JsonArray();
                selected.add(passId);
                JsonArray ordering = new JsonArray();
                ordering.add(ids.get(1));
                ordering.add(ids.get(0));
                JsonObject response = new JsonObject();
                response.addProperty("decision_id", pending.get("decision_id").getAsString());
                response.addProperty("actor_id", pending.get("actor_id").getAsString());
                response.add("selected_option_ids", selected);
                response.add("ordering", ordering);
                session.submit(response);
                orderedKeys = List.of(keys.get(1), keys.get(0));
            } else {
                session.submitAction(FullGameTestPilot.choose(session.legalActionsPayload()));
            }
        }
        assertTrue(orderedKeys != null, "a priority frame with a pass and an alternative was offered");
        FullGameTestPilot.play(session, 20);
        JsonObject export = session.replayExportPayload();
        boolean found = false;
        for (JsonElement element : export.getAsJsonArray("decisions")) {
            JsonObject entry = element.getAsJsonObject();
            if (entry.has("ordering_keys") && entry.getAsJsonArray("ordering_keys").size() == 2) {
                assertEquals(orderedKeys, keysOf(entry.getAsJsonArray("ordering_keys")));
                found = true;
            }
        }
        assertTrue(found, "the non-empty ordering is in the record");
        JsonObject verdict = replayInFreshJvm(export);
        assertEquals("REPLAY_MATCH", verdict.get("verdict").getAsString(), verdict.toString());
    }

    // ---- helpers --------------------------------------------------------------

    static int firstDecisionIndex(JsonArray decisions) {
        for (int index = 0; index < decisions.size(); index++) {
            if ("decision".equals(decisions.get(index).getAsJsonObject().get("kind").getAsString())) {
                return index;
            }
        }
        throw new AssertionError("no decision entry");
    }

    static JsonObject recordedExport(int players, long seed) throws Exception {
        XmageFullGameSession session = FullGameTestPilot.realDeckSession(
                "issue662-replay-" + players + "p-" + seed, players, seed);
        FullGameTestPilot.play(session, DECISIONS);
        return session.replayExportPayload();
    }

    /** Swap the first chosen key that has an offered alternative; returns its index. */
    static int swapFirstChoice(JsonObject export) throws Exception {
        // Re-run the same game in-process to read each frame's offered keys.
        XmageFullGameSession session = FullGameTestPilot.realDeckSession(
                "issue662-replay-tamper", export.getAsJsonArray("decks").size(), export.get("seed").getAsLong());
        JsonArray decisions = export.getAsJsonArray("decisions");
        for (int index = 0; index < decisions.size(); index++) {
            JsonObject entry = decisions.get(index).getAsJsonObject();
            JsonObject pending = session.pendingDecisionPayload().getAsJsonObject("decision");
            List<String> keys = XmageFullGameReplay.semanticKeys(pending.getAsJsonArray("legal_options"));
            JsonArray chosen = entry.getAsJsonArray("chosen_keys");
            if (chosen.size() == 1 && keys.size() > 1 && "priority".equals(entry.get("decision_class").getAsString())) {
                String other = keys.stream().filter(key -> !key.equals(chosen.get(0).getAsString()))
                        .findFirst().orElseThrow();
                JsonArray replaced = new JsonArray();
                replaced.add(other);
                entry.add("chosen_keys", replaced);
                return index;
            }
            session.submitAction(FullGameTestPilot.choose(session.legalActionsPayload()));
        }
        throw new AssertionError("no decision with an alternative to tamper");
    }

    static void refreshDigest(JsonObject export) {
        export.addProperty("decisions_digest",
                XmageFullGameReplay.sha256(export.getAsJsonArray("decisions").toString()));
    }

    static JsonObject replayInFreshJvm(JsonObject export) throws Exception {
        Path file = FullGameTestPilot.writeTemp("issue662-replay", export);
        List<String> command = new ArrayList<>();
        command.add(Path.of(System.getProperty("java.home"), "bin", "java").toString());
        command.add("-Djava.awt.headless=true");
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot != null) {
            command.add("-Dcommanderlab.repoRoot=" + repoRoot);
        }
        command.add("-cp");
        command.add(System.getProperty("java.class.path"));
        command.add("org.commanderlab.xmage.Main");
        command.add("full-game-replay");
        command.add(file.toString());
        Process process = new ProcessBuilder(command)
                .directory(new File(System.getProperty("user.dir")))
                .redirectError(ProcessBuilder.Redirect.DISCARD)
                .start();
        String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        assertTrue(process.waitFor(600, TimeUnit.SECONDS), "verifier process ended");
        String last = null;
        for (String line : output.split("\n")) {
            if (line.startsWith("{") && line.contains("\"verdict\"")) {
                last = line;
            }
        }
        assertTrue(last != null, "verifier printed a verdict: " + output);
        JsonObject verdict = JsonParser.parseString(last).getAsJsonObject();
        int exit = process.exitValue();
        String result = verdict.get("verdict").getAsString();
        assertEquals("REPLAY_MATCH".equals(result) ? 0 : "DIVERGED".equals(result) ? 1 : 2, exit, result);
        return verdict;
    }

    private static List<String> keysOf(JsonArray array) {
        List<String> keys = new ArrayList<>();
        for (JsonElement element : array) {
            keys.add(element.getAsString());
        }
        return keys;
    }
}

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
 *   <li>R4: no pilot-facing frame carries the record or the export.</li>
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

        JsonObject verdict = replayInFreshJvm(export);
        assertEquals("REPLAY_MATCH", verdict.get("verdict").getAsString(), verdict.toString());
        assertEquals(export.get("final_state_digest").getAsString(), verdict.get("final_state_digest").getAsString());
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
        assertEquals("final_state_digest", truncatedVerdict.get("field").getAsString());

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

    // ---- helpers --------------------------------------------------------------

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
        assertEquals("REPLAY_MATCH".equals(verdict.get("verdict").getAsString()) ? 0 : 1, exit, verdict.toString());
        return verdict;
    }

    @SuppressWarnings("unused")
    private static List<String> keysOf(JsonArray array) {
        List<String> keys = new ArrayList<>();
        for (JsonElement element : array) {
            keys.add(element.getAsString());
        }
        return keys;
    }
}

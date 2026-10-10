package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * #662 SLOT-06 (c) R2/R3: replays a full-game replay export in this (fresh) JVM.
 *
 * <p>Input is only the export: seed, decklists, seating and the ordered semantic
 * decision record. The verifier starts the same game, and at every recorded
 * decision checks that the engine asks the same class of the same seat and offers
 * the same option set (offered-option digest) before re-submitting the recorded
 * choice by semantic key. At the end the semantic state digest must equal the
 * exported one. The first difference is reported as a divergence; nothing is
 * defaulted, and a frame the record does not cover is a divergence.</p>
 *
 * <p>Output: one JSON line. Exit code 0 = REPLAY_MATCH, 1 = DIVERGED, 2 = error.</p>
 */
final class XmageFullGameReplayVerifier {

    private XmageFullGameReplayVerifier() {
    }

    static int run(Path exportPath, PrintStream out) {
        JsonObject verdict;
        int code;
        try {
            JsonObject export = JsonParser.parseString(
                    Files.readString(exportPath, StandardCharsets.UTF_8)).getAsJsonObject();
            verdict = verify(export);
            String result = verdict.get("verdict").getAsString();
            code = "REPLAY_MATCH".equals(result) ? 0 : "DIVERGED".equals(result) ? 1 : 2;
        } catch (Exception exc) {
            verdict = new JsonObject();
            verdict.addProperty("verdict", "ERROR");
            verdict.addProperty("error", redactedError(exc));
            code = 2;
        }
        out.println(verdict);
        out.flush();
        return code;
    }

    static JsonObject verify(JsonObject export) {
        if (!XmageFullGameReplay.SCHEMA_VERSION.equals(text(export, "schema_version"))) {
            return diverged(-1, "schema_version", XmageFullGameReplay.SCHEMA_VERSION, text(export, "schema_version"));
        }
        JsonArray decisions = export.getAsJsonArray("decisions");
        String digest = XmageFullGameReplay.sha256(decisions.toString());
        if (!digest.equals(text(export, "decisions_digest"))
                || decisions.size() != export.get("decision_count").getAsInt()) {
            return diverged(-1, "decisions_digest", text(export, "decisions_digest"), digest);
        }

        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>();
        for (JsonElement element : export.getAsJsonArray("decks")) {
            JsonObject deck = element.getAsJsonObject();
            handles.add(importer.importCommanderDeck(
                    text(deck, "deck_id"), text(deck, "deck_hash"),
                    strings(deck.getAsJsonArray("mainboard")),
                    strings(deck.getAsJsonArray("commanders"))).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                "replay-verifier", handles,
                export.get("starting_player_seat").getAsInt(),
                export.get("starting_life").getAsInt(),
                export.get("seed").getAsLong(),
                importer);
        JsonObject verdict;
        try {
            session.start();
            verdict = replay(session, export, decisions);
        } catch (RuntimeException exc) {
            shutdownQuietly(session);
            throw exc;
        }
        // The verifier owns its game: end it and join the engine thread instead
        // of leaving that to process exit.
        boolean clean = shutdownQuietly(session);
        verdict.addProperty("shutdown_clean", clean);
        if (!clean) {
            // A replay whose engine could not be ended proves nothing: fail closed.
            verdict.addProperty("replay_verdict", verdict.get("verdict").getAsString());
            verdict.addProperty("verdict", "ERROR");
            verdict.addProperty("error", "FULL_GAME_SHUTDOWN_TIMEOUT");
        }
        return verdict;
    }

    private static boolean shutdownQuietly(XmageFullGameSession session) {
        try {
            session.shutdownGame();
            return true;
        } catch (RuntimeException shutdownFailure) {
            return false;
        }
    }

    private static JsonObject replay(XmageFullGameSession session, JsonObject export, JsonArray decisions) {
        for (int index = 0; index < decisions.size(); index++) {
            JsonObject entry = decisions.get(index).getAsJsonObject();
            JsonObject status = session.pendingDecisionPayload();
            if ("concede".equals(text(entry, "kind"))) {
                try {
                    int seat = entry.get("actor_seat").getAsInt();
                    String principal = status.getAsJsonArray("outcomes").get(seat)
                            .getAsJsonObject().get("player_id").getAsString();
                    JsonObject concede = new JsonObject();
                    concede.addProperty("proposal_id", "replay-" + index);
                    concede.addProperty("actor_id", principal);
                    concede.addProperty("player_id", principal);
                    session.submitConcede(concede);
                } catch (RuntimeException rejected) {
                    return diverged(index, "concession", "accepted", "rejected: " + redactedError(rejected));
                }
                continue;
            }
            if (status.get("decision") == null || status.get("decision").isJsonNull()) {
                return diverged(index, "pending_decision", text(entry, "decision_class"), "none (engine ended)");
            }
            JsonObject pending = status.getAsJsonObject("decision");
            if (!text(entry, "decision_class").equals(text(pending, "decision_class"))) {
                return diverged(index, "decision_class", text(entry, "decision_class"), text(pending, "decision_class"));
            }
            if (entry.get("actor_seat").getAsInt() != pending.get("seat").getAsInt()) {
                return diverged(index, "actor_seat", entry.get("actor_seat").getAsString(),
                        pending.get("seat").getAsString());
            }
            if (!entry.has("decision_offset")
                    || entry.get("decision_offset").getAsLong() != pending.get("decision_offset").getAsLong()) {
                return diverged(index, "decision_offset", text(entry, "decision_offset"),
                        pending.get("decision_offset").getAsString());
            }
            String offered = XmageFullGameReplay.offeredDigest(pending);
            if (!offered.equals(text(entry, "offered_digest"))) {
                return diverged(index, "offered_digest", text(entry, "offered_digest"), offered);
            }
            JsonArray options = pending.getAsJsonArray("legal_options");
            List<String> keys = XmageFullGameReplay.semanticKeys(options);
            List<String> ids = XmageFullGameReplay.optionIds(options);
            JsonArray selected = new JsonArray();
            for (JsonElement chosen : entry.getAsJsonArray("chosen_keys")) {
                int position = keys.indexOf(chosen.getAsString());
                if (position < 0) {
                    return diverged(index, "chosen_key", "recorded key", "not offered");
                }
                selected.add(ids.get(position));
            }
            JsonArray ordering = new JsonArray();
            JsonArray orderingKeys = entry.has("ordering_keys") ? entry.getAsJsonArray("ordering_keys") : null;
            if (orderingKeys == null) {
                // Schema 1.1.0 records the ordering of every decision; a missing
                // field is a broken record, never "no ordering".
                return diverged(index, "ordering_keys", "present", "missing");
            }
            for (JsonElement ordered : orderingKeys) {
                int position = keys.indexOf(ordered.getAsString());
                if (position < 0) {
                    return diverged(index, "ordering_key", "recorded key", "not offered");
                }
                ordering.add(ids.get(position));
            }
            JsonObject response = new JsonObject();
            response.addProperty("decision_id", text(pending, "decision_id"));
            response.addProperty("actor_id", text(pending, "actor_id"));
            response.add("selected_option_ids", selected);
            response.add("ordering", ordering);
            response.add("numeric_choice", entry.has("numeric_choice") ? entry.get("numeric_choice") : JsonNull.INSTANCE);
            response.add("numeric_choices", entry.has("numeric_choices") ? entry.get("numeric_choices") : JsonNull.INSTANCE);
            try {
                session.submit(response);
            } catch (RuntimeException rejected) {
                return diverged(index, "submission", "accepted", "rejected: " + redactedError(rejected));
            }
        }
        // R3: the engine must now be on exactly the frame the export ended on. A
        // further frame is one the tape does not cover; nothing is defaulted.
        JsonObject finalStatus = session.pendingDecisionPayload();
        JsonObject finalPending = finalStatus.get("decision") == null || finalStatus.get("decision").isJsonNull()
                ? null : finalStatus.getAsJsonObject("decision");
        JsonElement observedFrame = XmageFullGameReplay.pendingFrame(finalPending);
        JsonElement expectedFrame = export.has("final_pending") ? export.get("final_pending") : null;
        if (expectedFrame == null) {
            return diverged(decisions.size(), "final_pending", "present", "missing");
        }
        if (!expectedFrame.equals(observedFrame)) {
            return diverged(decisions.size(), "unrecorded_frame", frameLabel(expectedFrame), frameLabel(observedFrame));
        }
        String observedState = session.replayEngineState();
        if (!text(export, "final_engine_state").equals(observedState)) {
            // A replay that ends FAILED (or anywhere but the exported state) never
            // matches, even with equal public digests.
            return diverged(decisions.size(), "engine_state", text(export, "final_engine_state"), observedState);
        }
        String finalDigest = session.semanticStateDigest();
        if (!finalDigest.equals(text(export, "final_state_digest"))) {
            return diverged(decisions.size(), "final_state_digest", text(export, "final_state_digest"), finalDigest);
        }
        JsonObject verdict = new JsonObject();
        verdict.addProperty("verdict", "REPLAY_MATCH");
        verdict.addProperty("decisions_replayed", decisions.size());
        verdict.addProperty("final_state_digest", finalDigest);
        verdict.addProperty("process", "fresh JVM via Main full-game-replay");
        return verdict;
    }

    /**
     * A divergence names the record index and field only. Expected and observed
     * values are digests, classes, seats or semantic keys of the replaying
     * orchestrator's own record; the report is orchestration-only (R4).
     */
    private static JsonObject diverged(int index, String field, String expected, String observed) {
        JsonObject verdict = new JsonObject();
        verdict.addProperty("verdict", "DIVERGED");
        verdict.addProperty("first_divergence_index", index);
        verdict.addProperty("field", field);
        verdict.addProperty("expected", expected);
        verdict.addProperty("observed", observed);
        return verdict;
    }

    /** Class and frame only: digests stay out of the label, the record index locates it. */
    private static String frameLabel(JsonElement frame) {
        if (frame == null || frame.isJsonNull()) {
            return "none";
        }
        JsonObject object = frame.getAsJsonObject();
        return text(object, "decision_class") + "@seat" + text(object, "actor_seat");
    }

    /**
     * R4: an error names the exception class and, when the message starts with
     * one, its typed code (e.g. {@code ILLEGAL_ACTION}); the free-text rest may
     * carry option ids, card names or paths and is dropped.
     */
    static String redactedError(Throwable exc) {
        String message = exc.getMessage() == null ? "" : exc.getMessage();
        java.util.regex.Matcher code = java.util.regex.Pattern.compile("^([A-Z][A-Z0-9_]{2,})(:|$)").matcher(message);
        return exc.getClass().getSimpleName() + (code.find() ? ": " + code.group(1) : "");
    }

    private static String text(JsonObject object, String field) {
        return object.has(field) && !object.get(field).isJsonNull() ? object.get(field).getAsString() : "";
    }

    private static List<String> strings(JsonArray array) {
        List<String> values = new ArrayList<>();
        array.forEach(element -> values.add(element.getAsString()));
        return values;
    }
}

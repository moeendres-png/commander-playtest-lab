package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * WS60 scenario execution driver.
 *
 * <p>Builds a four-player Commander game from scenario decks through
 * {@link Ws52Harness} (same engine calls and order as the qualified lane),
 * arms a {@link Ws60EventTape} before the game starts, then drives the engine
 * exclusively through pending decision frames answered by a
 * principal-disciplined {@link Ws60Pilot}.</p>
 */
final class Ws60Driver {

    record SeatDeck(List<String> commanders, List<String> mainboard) {
    }

    /** Omniscient completion predicate (test level, not pilot level). */
    interface Completion {
        boolean isComplete(Ws52Harness harness);
    }

    /** Test-level mid-run observation hook (checkpoints, cast-time snapshots). */
    interface Checkpoint {
        void onFrame(JsonObject frame, Ws52Harness harness, int seq);
    }

    record FrameRecord(JsonObject projection, boolean critical, JsonObject verbatim) {
    }

    record RunResult(String scenarioId, long seed, List<FrameRecord> frames,
            JsonArray eventTape, List<JsonObject> terminalViews,
            long rulesSeed, boolean rulesSeedExplicit, long rulesRandomCalls,
            int decisionsAnswered, String projectionDigest, boolean completed,
            String stoppedReason) {
    }

    private Ws60Driver() {
    }

    static RunResult run(String scenarioId, List<SeatDeck> seats, long seed,
            Ws60Pilot pilot, Completion completion, List<Checkpoint> checkpoints,
            int decisionBound) {
        if (seats.size() != 4) {
            throw new IllegalArgumentException("WS60 requires exactly 4 seats");
        }
        List<List<String>> mainboards = new ArrayList<>();
        List<List<String>> commanders = new ArrayList<>();
        for (SeatDeck seat : seats) {
            mainboards.add(seat.mainboard());
            commanders.add(seat.commanders());
        }
        List<FrameRecord> frames = new ArrayList<>();
        String chain = "GENESIS";
        int answered = 0;
        boolean completed = false;
        String stoppedReason = "bound";
        try (Ws52Harness harness = new Ws52Harness(
                "ws60-" + scenarioId.toLowerCase(Locale.ROOT),
                mainboards, commanders, seed, Ws52.STARTING_LIFE)) {
            Ws60EventTape tape = new Ws60EventTape();
            tape.arm(harness.game);
            harness.game.getState().addWatcher(tape);
            harness.start(0);
            for (int step = 0; step < decisionBound; step++) {
                Ws52Harness.SlotDecision slot;
                try {
                    slot = harness.awaitDecision();
                } catch (RuntimeException | AssertionError exc) {
                    // Engine parked nowhere (terminal/failed). The live state
                    // is quiescent now, so a final completion check is exact.
                    try {
                        if (completion.isComplete(harness)) {
                            completed = true;
                            stoppedReason = "complete-at-terminal";
                        } else {
                            stoppedReason = "await-failed: " + exc.getMessage();
                        }
                    } catch (RuntimeException inner) {
                        stoppedReason = "await-failed: " + exc.getMessage();
                    }
                    break;
                }
                // Completion is evaluated on the quiescent parked state (the
                // engine thread is blocked on this decision), never
                // mid-resolution after a submit. A positive is settle-verified
                // on the next parked frame (state-based actions and other
                // end-of-resolution bookkeeping must have applied); a negative
                // re-verification resumes normal driving.
                boolean completeNow = false;
                try {
                    completeNow = completion.isComplete(harness);
                } catch (RuntimeException exc) {
                    stoppedReason = "completion-check-failed: " + exc.getMessage();
                    break;
                }
                if (completeNow) {
                    JsonObject frame = slot.pending();
                    JsonObject projection = project(frame);
                    chain = sha256Hex(chain + "|" + projection);
                    projection.addProperty("log_seq", frames.size());
                    projection.addProperty("chain", chain);
                    boolean critical = pilot.isCritical(frame);
                    frames.add(new FrameRecord(projection, critical,
                            critical ? frame.deepCopy() : new JsonObject()));
                    for (Checkpoint checkpoint : checkpoints) {
                        try {
                            checkpoint.onFrame(frame, harness, frames.size() - 1);
                        } catch (RuntimeException exc) {
                            stoppedReason = "checkpoint-failed: " + exc.getMessage();
                            break;
                        }
                    }
                    if (stoppedReason.startsWith("checkpoint-failed")) {
                        break;
                    }
                    Ws60Pilot.PilotAction settleAction;
                    try {
                        settleAction = decideOpening(frame, pilot);
                    } catch (Ws60Pilot.PilotGapException gap) {
                        stoppedReason = "pilot-gap: " + gap.getMessage();
                        break;
                    }
                    try {
                        harness.submit(frame, settleAction.optionIds(), settleAction.numeric());
                    } catch (RuntimeException | AssertionError exc) {
                        stoppedReason = "submit-failed: " + exc.getMessage();
                        break;
                    }
                    answered++;
                    projection.add("selected", selectedLabels(frame, settleAction));
                    if (settleAction.numeric() != null) {
                        projection.addProperty("numeric", settleAction.numeric());
                    }
                    chain = sha256Hex(chain + "|" + projection.get("selected").toString()
                            + (settleAction.numeric() == null ? ""
                                    : settleAction.numeric().toString()));
                    projection.addProperty("chain", chain);
                    Ws52Harness.SlotDecision settled;
                    try {
                        settled = harness.awaitDecision();
                    } catch (RuntimeException | AssertionError exc) {
                        // No further frame (game ended at completion): accept.
                        completed = true;
                        stoppedReason = "complete-at-terminal";
                        break;
                    }
                    boolean stillComplete;
                    try {
                        stillComplete = completion.isComplete(harness);
                    } catch (RuntimeException exc) {
                        stoppedReason = "completion-check-failed: " + exc.getMessage();
                        break;
                    }
                    if (stillComplete) {
                        completed = true;
                        stoppedReason = "complete";
                        break;
                    }
                    // Transient positive (unsettled state): drive the settled
                    // frame normally and continue.
                    slot = settled;
                }
                JsonObject frame = slot.pending();
                JsonObject projection = project(frame);
                chain = sha256Hex(chain + "|" + projection);
                projection.addProperty("log_seq", frames.size());
                projection.addProperty("chain", chain);
                boolean critical = pilot.isCritical(frame);
                frames.add(new FrameRecord(projection, critical,
                        critical ? frame.deepCopy() : new JsonObject()));
                for (Checkpoint checkpoint : checkpoints) {
                    try {
                        checkpoint.onFrame(frame, harness, frames.size() - 1);
                    } catch (RuntimeException exc) {
                        stoppedReason = "checkpoint-failed: " + exc.getMessage();
                        break;
                    }
                }
                if (stoppedReason.startsWith("checkpoint-failed")) {
                    break;
                }
                Ws60Pilot.PilotAction action;
                try {
                    action = decideOpening(frame, pilot);
                } catch (Ws60Pilot.PilotGapException gap) {
                    stoppedReason = "pilot-gap: " + gap.getMessage();
                    break;
                }
                try {
                    harness.submit(frame, action.optionIds(), action.numeric());
                } catch (RuntimeException | AssertionError exc) {
                    stoppedReason = "submit-failed: " + exc.getMessage();
                    break;
                }
                answered++;
                // Record the externally selected option (labels resolved from
                // the offered set; numeric choices recorded verbatim).
                projection.add("selected", selectedLabels(frame, action));
                if (action.numeric() != null) {
                    projection.addProperty("numeric", action.numeric());
                }
                chain = sha256Hex(chain + "|" + projection.get("selected").toString()
                        + (action.numeric() == null ? "" : action.numeric().toString()));
                projection.addProperty("chain", chain);
            }
            List<JsonObject> terminalViews = new ArrayList<>();
            for (int seat = 0; seat < 4; seat++) {
                try {
                    terminalViews.add(XmageFullGameStateRedactor.actorView(
                            harness.game, harness.players().get(seat)));
                } catch (RuntimeException exc) {
                    terminalViews.add(new JsonObject());
                }
            }
            JsonArray tapeExport = tape.export();
            long rulesSeed;
            boolean explicit;
            long calls;
            try {
                rulesSeed = harness.game.getRulesSeed();
                explicit = harness.game.isRulesSeedExplicit();
                calls = harness.game.getRulesRandomCalls();
            } catch (RuntimeException exc) {
                rulesSeed = seed;
                explicit = false;
                calls = -1L;
            }
            return new RunResult(scenarioId, seed, frames, tapeExport, terminalViews,
                    rulesSeed, explicit, calls, answered, chain, completed, stoppedReason);
        }
    }

    /**
     * Generic opening prelude (mirrors Ws52.pilotOpening): install Seat 1
     * (RQ-P0) as the starting player, then delegate everything else
     * (including London mulligans) to the scenario pilot.
     */
    private static Ws60Pilot.PilotAction decideOpening(JsonObject frame, Ws60Pilot pilot) {
        if (Ws60Pilot.frameClass(frame).equals("choose_object")
                && Ws60Pilot.contextString(frame, "target_description")
                        .equals("target starting player")) {
            for (JsonElement element : frame.getAsJsonArray("legal_options")) {
                JsonObject option = element.getAsJsonObject();
                if (Ws60Pilot.label(option).endsWith("Seat 1")) {
                    return new Ws60Pilot.PilotAction(
                            List.of(Ws60Pilot.optionId(option)), null);
                }
            }
            throw new Ws60Pilot.PilotGapException("starting-player frame without Seat 1");
        }
        return pilot.decide(frame);
    }

    // ------------------------------------------------------------------
    // Twin-stable projection: human-semantic fields only; every UUID-valued
    // metadata key is stripped so equal histories hash equal across runs.
    // ------------------------------------------------------------------

    static JsonObject project(JsonObject frame) {
        JsonObject out = new JsonObject();
        out.addProperty("class", str(frame, "decision_class"));
        out.addProperty("seat", intOr(frame, "seat", -1));
        out.addProperty("subject_seat", intOr(frame, "decision_subject_seat", -1));
        out.addProperty("prompt", sanitize(str(frame, "prompt")));
        out.addProperty("min", intOr(frame, "minimum_selections", -1));
        out.addProperty("max", intOr(frame, "maximum_selections", -1));
        out.add("context", projectContext(frame));
        if (frame.has("source_object") && frame.get("source_object").isJsonObject()) {
            JsonObject source = frame.getAsJsonObject("source_object");
            out.addProperty("source", source.has("source_name") && !source.get("source_name").isJsonNull()
                    ? source.get("source_name").getAsString() : "");
        }
        JsonArray options = new JsonArray();
        if (frame.has("legal_options") && frame.get("legal_options").isJsonArray()) {
            List<JsonObject> sorted = new ArrayList<>();
            for (JsonElement element : frame.getAsJsonArray("legal_options")) {
                sorted.add(projectOption(element.getAsJsonObject()));
            }
            // Twin-stable: engine emits options in native-UUID order (random
            // per game). The offered SET is the semantic content; order is
            // normalized here (verbatim order preserved in critical frames).
            sorted.sort((left, right) -> {
                int byType = left.get("type").getAsString()
                        .compareTo(right.get("type").getAsString());
                if (byType != 0) {
                    return byType;
                }
                int byLabel = left.get("label").getAsString()
                        .compareTo(right.get("label").getAsString());
                if (byLabel != 0) {
                    return byLabel;
                }
                return left.get("meta").toString().compareTo(right.get("meta").toString());
            });
            sorted.forEach(options::add);
        }
        out.add("options", options);
        out.add("state", projectPilotState(frame));
        return out;
    }

    private static JsonObject projectPilotState(JsonObject frame) {
        JsonObject out = new JsonObject();
        if (!frame.has("pilot_state") || !frame.get("pilot_state").isJsonObject()) {
            return out;
        }
        JsonObject state = frame.getAsJsonObject("pilot_state");
        if (state.has("turn_number")) {
            out.addProperty("turn", state.get("turn_number").getAsInt());
        }
        if (state.has("phase") && !state.get("phase").isJsonNull()) {
            out.addProperty("phase", state.get("phase").getAsString());
        }
        if (state.has("step") && !state.get("step").isJsonNull()) {
            out.addProperty("step", state.get("step").getAsString());
        }
        if (state.has("stack") && state.get("stack").isJsonArray()) {
            JsonArray names = new JsonArray();
            for (JsonElement element : state.getAsJsonArray("stack")) {
                names.add(element.getAsJsonObject().get("name").getAsString());
            }
            out.add("stack", names);
        }
        if (state.has("players") && state.get("players").isJsonArray()) {
            JsonArray seats = new JsonArray();
            for (JsonElement element : state.getAsJsonArray("players")) {
                JsonObject player = element.getAsJsonObject();
                JsonObject row = new JsonObject();
                row.addProperty("seat", player.get("seat").getAsInt());
                row.addProperty("life", player.get("life").getAsInt());
                row.addProperty("hand", player.get("hand_count").getAsInt());
                row.addProperty("library", player.get("library_count").getAsInt());
                row.addProperty("lands", battlefieldCount(player, "battlefield"));
                seats.add(row);
            }
            out.add("seats", seats);
        }
        return out;
    }

    private static int battlefieldCount(JsonObject player, String key) {
        return player.has(key) && player.get(key).isJsonArray()
                ? player.getAsJsonArray(key).size() : -1;
    }

    private static JsonObject projectContext(JsonObject frame) {
        JsonObject out = new JsonObject();
        if (!frame.has("context") || !frame.get("context").isJsonObject()) {
            return out;
        }
        JsonObject context = frame.getAsJsonObject("context");
        for (String key : new String[]{"numeric_min", "numeric_max", "amount_remaining",
                "target_description", "target_name", "outcome", "unpaid_mana",
                "choice_domain", "required", "targeted"}) {
            if (context.has(key) && !context.get(key).isJsonNull()) {
                try {
                    out.addProperty(key, context.get(key).getAsString());
                } catch (RuntimeException ignored) {
                    // Non-scalar context values are omitted from the projection.
                }
            }
        }
        return out;
    }

    private static JsonObject projectOption(JsonObject option) {
        JsonObject out = new JsonObject();
        out.addProperty("label", sanitize(Ws60Pilot.label(option)));
        out.addProperty("type", Ws60Pilot.optionType(option));
        JsonObject meta = Ws60Pilot.metadata(option);
        JsonObject kept = new JsonObject();
        for (Map.Entry<String, JsonElement> entry : meta.entrySet()) {
            String key = entry.getKey();
            String folded = key.toLowerCase(Locale.ROOT);
            if (folded.contains("id") || folded.contains("uuid") || folded.contains("digest")
                    || folded.contains("hash") || folded.endsWith("_ref") || folded.equals("ref")
                    || folded.equals("xmage_key") || folded.contains("native")) {
                continue;
            }
            try {
                if (entry.getValue().isJsonPrimitive()) {
                    kept.addProperty(key, entry.getValue().getAsString());
                }
            } catch (RuntimeException ignored) {
                // Skip non-scalar metadata in the projection.
            }
        }
        out.add("meta", kept);
        return out;
    }

    private static String str(JsonObject object, String key) {
        return object.has(key) && !object.get(key).isJsonNull()
                ? sanitize(object.get(key).getAsString()) : "";
    }

    /**
     * Twin-stable sanitizer: engine-rendered prompts and labels embed native
     * UUIDs (object_id attributes) and short id refs ([b3b]-style), which are
     * random per game. They carry no semantic content beyond the surrounding
     * names, so they are folded to stable tokens for cross-run comparison.
     */
    static String sanitize(String text) {
        if (text == null) {
            return "";
        }
        String out = text.replaceAll(
                "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                "#");
        out = out.replaceAll("\\[[0-9a-fA-F]{3}\\]", "[]");
        return out;
    }

    private static int intOr(JsonObject object, String key, int fallback) {
        try {
            return object.has(key) && !object.get(key).isJsonNull()
                    ? object.get(key).getAsInt() : fallback;
        } catch (RuntimeException ignored) {
            return fallback;
        }
    }

    private static JsonArray selectedLabels(JsonObject frame, Ws60Pilot.PilotAction action) {
        JsonArray out = new JsonArray();
        if (!frame.has("legal_options") || !frame.get("legal_options").isJsonArray()) {
            return out;
        }
        for (String id : action.optionIds()) {
            String found = null;
            for (JsonElement element : frame.getAsJsonArray("legal_options")) {
                JsonObject option = element.getAsJsonObject();
                if (id.equals(Ws60Pilot.optionId(option))) {
                    found = sanitize(Ws60Pilot.label(option));
                    break;
                }
            }
            out.add(found == null ? ("UNKNOWN:" + id) : found);
        }
        return out;
    }

    static String sha256Hex(String text) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(
                    digest.digest(text.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception exc) {
            throw new IllegalStateException(exc);
        }
    }
}

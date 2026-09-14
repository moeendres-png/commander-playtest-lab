package org.commanderlab.xmage;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.game.CommanderFreeForAll;

import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * WS205 qualification-only First-Wave slot executor (fresh JVM per game).
 *
 * <p>Drives ONE isolated full-game session exclusively through the WS204
 * decision-scoped generic boundary:
 * {@link XmageFullGameSession#legalActionsPayload()} plus
 * {@link XmageFullGameSession#submitAction(JsonObject)}.
 * Every selection is an XMage-offered native option; XMage executes natively.
 * No legality is computed here; no outcome is written directly.</p>
 *
 * <p>Pilot policy {@code ws207-setup-v1}: deterministic offered-only (setup-state machine; behavior sequencing is successor scope)
 * selection with per-slot wish-list matching (substring over offered display
 * label plus metadata, never requested-result filtering), neutral fallbacks
 * (pass / hold / empty blockers / lexicographic smallest / schema-minimum
 * numerics), fail-closed unknown classes.</p>
 *
 * <p>Modes: {@code run} (primary), {@code twin} (follow a recorded stream),
 * {@code probe} (print early decisions for calibration),
 * {@code probe-deck} (deck import validation only).</p>
 */
public final class Ws207SetupDriver {

    private static final String POLICY_VERSION = "ws207-setup-v1";
    private static final String ENGINE_PIN = "cfc36f445f917f101fa2ed588770e043f53bc44c";

    /** Offered-order index of the last matcher pick (-1 when unmatched). */
    private static int lastMatchIndex = -1;

    private Ws207SetupDriver() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> argv = parseArgs(args);
        String mode = required(argv, "mode");
        switch (mode) {
            case "probe-deck" -> runProbeDeck(argv);
            case "probe" -> runProbe(argv);
            case "run" -> runGame(argv, false);
            case "twin" -> runGame(argv, true);
            default -> throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    // ------------------------------------------------------------------
    // probe-deck: validate crafted deck imports against the pinned engine.
    // ------------------------------------------------------------------

    private static void runProbeDeck(Map<String, String> argv) throws Exception {
        Path decksFile = Path.of(required(argv, "decks"));
        JsonObject decks = JsonParser.parseString(
                Files.readString(decksFile, StandardCharsets.UTF_8)).getAsJsonObject();
        XmageDeckImporter importer = new XmageDeckImporter();
        JsonObject out = new JsonObject();
        out.addProperty("engine_pin", ENGINE_PIN);
        JsonArray seats = new JsonArray();
        for (int seat = 0; seat < 4; seat++) {
            JsonObject spec = decks.getAsJsonObject("seat" + seat);
            List<String> mainboard = strings(spec.getAsJsonArray("mainboard"));
            List<String> commanders = strings(spec.getAsJsonArray("commanders"));
            JsonObject row = new JsonObject();
            row.addProperty("seat", seat);
            try {
                XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                        spec.get("deck_id").getAsString(),
                        spec.get("deck_hash").getAsString(),
                        mainboard, commanders);
                row.addProperty("ok", true);
                row.addProperty("deck_handle", imported.deckHandle());
                row.addProperty("mainboard_count", imported.mainboardCount());
                row.addProperty("commander_count", imported.commanderCount());
            } catch (RuntimeException exc) {
                row.addProperty("ok", false);
                row.addProperty("error", exc.getMessage());
            }
            seats.add(row);
        }
        out.add("seats", seats);
        System.out.println(new Gson().toJson(out));
    }

    // ------------------------------------------------------------------
    // probe: print the first N pending decisions (calibration only).
    // ------------------------------------------------------------------

    private static void runProbe(Map<String, String> argv) throws Exception {
        Path decksFile = Path.of(required(argv, "decks"));
        long seed = Long.parseLong(required(argv, "seed"));
        int limit = Integer.parseInt(argv.getOrDefault("probe-limit", "12"));
        SessionHandles handles = startSession("ws207-probe", decksFile, 0, seed);
        JsonArray decisions = new JsonArray();
        for (int step = 0; step < limit; step++) {
            JsonObject payload = handles.session.pendingDecisionPayload();
            JsonObject pending = optObject(payload, "decision");
            if (pending == null) {
                break;
            }
            decisions.add(summarizePending(pending, true));
            JsonObject legal = handles.session.legalActionsPayload();
            JsonObject proposal = neutralProposal(legal, pending, new JsonObject());
            if (proposal == null) {
                JsonObject stop = new JsonObject();
                stop.addProperty("stopped", "neutral_proposal_null");
                stop.addProperty(
                        "decision_class", pending.get("decision_class").getAsString());
                decisions.add(stop);
                break;
            }
            handles.session.submitAction(proposal);
        }
        JsonObject out = new JsonObject();
        out.addProperty("engine_pin", ENGINE_PIN);
        out.addProperty("seed", seed);
        out.add("decisions", decisions);
        System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(out));
        System.exit(0);
    }

    // ------------------------------------------------------------------
    // run / twin: full slot execution with evidence.
    // ------------------------------------------------------------------

    private static void runGame(Map<String, String> argv, boolean twin) throws Exception {
        String slot = required(argv, "slot");
        String subcase = argv.getOrDefault("case", "");
        Path decksFile = Path.of(required(argv, "decks"));
        Path prefsFile = Path.of(required(argv, "prefs"));
        long seed = Long.parseLong(required(argv, "seed"));
        int budget = Integer.parseInt(argv.getOrDefault("budget", "400"));
        Path outFile = Path.of(required(argv, "out"));
        JsonObject prefs = JsonParser.parseString(
                Files.readString(prefsFile, StandardCharsets.UTF_8)).getAsJsonObject();
        List<StreamEntry> stream = null;
        if (twin) {
            Path streamFile = Path.of(required(argv, "stream"));
            stream = readStream(streamFile);
        }

        SessionHandles handles = startSession(
                "ws207-" + slot + (subcase.isEmpty() ? "" : "-" + subcase)
                        + (twin ? "-twin" : ""),
                decksFile,
                (int) (Math.floorMod(seed, 4)),
                seed);

        List<JsonObject> decisionStream = new ArrayList<>();
        Map<String, Integer> classCounts = new LinkedHashMap<>();
        Set<String> observedClasses = new LinkedHashSet<>();
        JsonObject negativeControls = new JsonObject();
        String stoppedBy = "budget";
        String stopDetail = "";
        int answered = 0;
        int streamCursor = 0;
        boolean streamDiverged = false;
        String streamDivergenceDetail = "";
        Map<Integer, Integer> landsPlayed = new LinkedHashMap<>();
        boolean probesDone = false;

        for (int step = 0; step < budget; step++) {
            JsonObject payload;
            try {
                payload = handles.session.pendingDecisionPayload();
            } catch (RuntimeException exc) {
                stoppedBy = "pending_failed";
                stopDetail = exc.getMessage();
                break;
            }
            JsonObject pending = optObject(payload, "decision");
            if (pending == null) {
                stoppedBy = "terminal";
                break;
            }
            String decisionClass = pending.get("decision_class").getAsString();
            int seat = pending.get("seat").getAsInt();
            long offset = pending.get("decision_offset").getAsLong();
            observedClasses.add(decisionClass);
            classCounts.merge(decisionClass, 1, Integer::sum);

            JsonObject legal;
            try {
                legal = handles.session.legalActionsPayload();
            } catch (RuntimeException exc) {
                stoppedBy = "legal_actions_failed:" + decisionClass;
                stopDetail = exc.getMessage();
                break;
            }
            if (!legal.get("decision_id").getAsString()
                    .equals(pending.get("decision_id").getAsString())) {
                stoppedBy = "projection_mismatch:" + decisionClass;
                stopDetail = "decision identity drift between pending and legal payload";
                break;
            }

            // Per-slot negative probes at the 2nd pending decision.
            if (!probesDone && !"false".equals(argv.getOrDefault("probes", "true"))) {
                probesDone = true;
                negativeControls = runNegativeProbes(handles, legal, pending);
            }

            JsonObject proposal;
            String selectionBasis;
            lastMatchIndex = -1;
            if (twin && stream != null) {
                TwinPick pick = pickTwinAction(legal, pending, stream, streamCursor);
                if (pick == null || pick.diverged) {
                    streamDiverged = true;
                    streamDivergenceDetail = pick == null
                            ? "stream exhausted at offset " + offset
                            : pick.detail;
                    stoppedBy = "twin_diverged";
                    stopDetail = streamDivergenceDetail;
                    break;
                }
                proposal = pick.proposal;
                selectionBasis = "twin_stream:" + pick.matchedLabel;
                streamCursor++;
            } else {
                WishPick pick = pickWishAction(legal, pending, prefs, landsPlayed);
                if (pick == null) {
                    stoppedBy = "unhandled_decision_class:" + decisionClass;
                    stopDetail = "no wish match and no neutral fallback";
                    break;
                }
                proposal = pick.proposal;
                selectionBasis = pick.basis;
            }
            String submittedActionId = proposal.has("legal_action_id")
                    && !proposal.get("legal_action_id").isJsonNull()
                    ? proposal.get("legal_action_id").getAsString() : "<empty-selection>";
            // Stable semantic label from the NATIVE pending option (labels are
            // engine-stable across JVMs; action metadata embeds process UUIDs).
            String submittedLabel = pendingLabelForAction(pending, submittedActionId);
            Integer submittedNumeric = proposal.has("choices")
                    && proposal.getAsJsonObject("choices").has("numeric_choice")
                    ? proposal.getAsJsonObject("choices").get("numeric_choice").getAsInt()
                    : null;
            try {
                handles.session.submitAction(proposal);
            } catch (RuntimeException exc) {
                stoppedBy = "submit_rejected:" + decisionClass;
                stopDetail = exc.getMessage();
                break;
            }
            if ("priority".equals(decisionClass) && submittedLabel != null
                    && submittedLabel.contains("Play ")) {
                landsPlayed.merge(seat, 1, Integer::sum);
            }
            answered++;
            JsonObject record = new JsonObject();
            record.addProperty("offset", offset);
            record.addProperty("class", decisionClass);
            record.addProperty("actor_seat", seat);
            record.addProperty(
                    "offered_count", pending.getAsJsonArray("legal_options").size());
            record.add("offered_types", typeHistogram(pending));
            record.addProperty("selected_label", submittedLabel == null ? "" : submittedLabel);
            record.addProperty("selected_index", lastMatchIndex);
            record.addProperty("label_ambiguous",
                    countLabelMatches(pending, submittedLabel) > 1);
            if (submittedNumeric != null) {
                record.addProperty("numeric_choice", submittedNumeric);
            }
            record.addProperty("selection_basis", selectionBasis);
            record.addProperty("advanced", true);
            decisionStream.add(record);
        }

        JsonObject evidence = new JsonObject();
        evidence.addProperty("schema", "ws207.setup-evidence.v1");
        evidence.addProperty("slot", slot);
        evidence.addProperty("subcase", subcase);
        evidence.addProperty("engine_pin", ENGINE_PIN);
        evidence.addProperty("seed", seed);
        evidence.addProperty("rules_seed", handles.rulesSeed);
        evidence.addProperty("rules_seed_bound_before_start", true);
        evidence.addProperty("rules_seed_explicit", handles.rulesSeedExplicit);
        evidence.addProperty("seed_binding_model",
                "EXPLICIT_RULES_SEED (setRulesSeed + requireExplicitSeed before start/init)");
        evidence.addProperty("candidate_head", argv.getOrDefault("head", "unknown"));
        evidence.addProperty("decision_policy_version", POLICY_VERSION);
        evidence.addProperty("setup_boundary", argv.getOrDefault("setup", "unknown"));
        evidence.addProperty("authority_hash", argv.getOrDefault("authority-hash", ""));
        evidence.addProperty("twin_run", twin);
        evidence.addProperty("stopped_by", stoppedBy);
        evidence.addProperty("stop_detail", stopDetail);
        evidence.addProperty("decisions_answered", answered);
        JsonArray classes = new JsonArray();
        observedClasses.forEach(classes::add);
        evidence.add("observed_decision_classes", classes);
        JsonObject counts = new JsonObject();
        classCounts.forEach(counts::addProperty);
        evidence.add("observed_decision_counts", counts);
        evidence.add("negative_controls", negativeControls);
        JsonArray streamJson = new JsonArray();
        decisionStream.forEach(streamJson::add);
        evidence.add("decision_stream", streamJson);
        if (twin) {
            evidence.addProperty("semantic_replay_match", false);
            evidence.addProperty("stream_diverged", streamDiverged);
            evidence.addProperty("stream_divergence_detail", streamDivergenceDetail);
            evidence.addProperty("stream_entries_followed", streamCursor);
        }
        // QUALIFICATION_ASSERTION_ONLY privileged state (never pilot input).
        try {
            evidence.add("assertion_state", captureAssertionState(handles));
        } catch (Exception exc) {
            JsonObject failed = new JsonObject();
            failed.addProperty("capture_failed", String.valueOf(exc.getMessage()));
            evidence.add("assertion_state", failed);
        }
        try {
            XmageFullGameDecisionController controller =
                    field(handles.session, "controller", XmageFullGameDecisionController.class);
            evidence.add("native_transcript", controller.transcript());
            evidence.addProperty("native_decision_count", controller.decisionCount());
        } catch (Exception exc) {
            evidence.addProperty("transcript_capture_failed", String.valueOf(exc.getMessage()));
        }
        evidence.addProperty("deck_id", handles.deckId);
        evidence.add("deck_handles", handles.handlesJson());
        Files.writeString(outFile, new GsonBuilder().setPrettyPrinting().create().toJson(evidence),
                StandardCharsets.UTF_8);
        System.out.println("WS207_EVIDENCE_WRITTEN " + outFile + " answered=" + answered
                + " stopped_by=" + stoppedBy);
        System.exit(0);
    }

    // ------------------------------------------------------------------
    // Negative probes: wrong-actor + unknown-option must fail closed.
    // ------------------------------------------------------------------

    private static JsonObject runNegativeProbes(
            SessionHandles handles, JsonObject legal, JsonObject pending) {
        JsonObject out = new JsonObject();
        String decisionId = legal.get("decision_id").getAsString();
        String actorId = legal.get("actor_id").getAsString();
        String actionType = "structural_decision";
        JsonArray actions = legal.getAsJsonArray("actions");
        if (actions.size() > 0) {
            actionType = actions.get(0).getAsJsonObject().get("action_type").getAsString();
        }
        String probeAction = actions.size() > 0
                ? actions.get(0).getAsJsonObject().get("action_id").getAsString()
                : decisionId + ":probe";
        // Wrong actor.
        try {
            JsonObject wrong = baseProposal("ws207-probe-wrong-actor", "intruder-actor",
                    probeAction, actionType, pending);
            handles.session.submitAction(wrong);
            out.addProperty("wrong_actor", "NOT_REJECTED");
        } catch (RuntimeException exc) {
            out.addProperty("wrong_actor", "REJECTED:" + exc.getMessage());
        }
        // Unknown option.
        try {
            JsonObject unknown = baseProposal("ws207-probe-unknown", actorId,
                    decisionId + ":ghost-option-ws207", actionType, pending);
            handles.session.submitAction(unknown);
            out.addProperty("unknown_action", "NOT_REJECTED");
        } catch (RuntimeException exc) {
            out.addProperty("unknown_action", "REJECTED:" + exc.getMessage());
        }
        // Advancement check: the pending decision must be unchanged.
        try {
            JsonObject again = handles.session.legalActionsPayload();
            out.addProperty("unadvanced",
                    decisionId.equals(again.get("decision_id").getAsString()));
        } catch (RuntimeException exc) {
            out.addProperty("unadvanced", false);
        }
        return out;
    }

    // ------------------------------------------------------------------
    // Setup-state machine ws207-setup-v1 (setup permanents only; behavior cards held).
    // ------------------------------------------------------------------

    private record WishPick(JsonObject proposal, String basis) {
    }

    private record TwinPick(JsonObject proposal, String matchedLabel,
                            boolean diverged, String detail) {
    }

    private record StreamEntry(long offset, String decisionClass,
                               String selectedLabel, Integer numericChoice) {
    }

    private static WishPick pickWishAction(
            JsonObject legal, JsonObject pending, JsonObject prefs,
            Map<Integer, Integer> landsPlayed) {
        String decisionClass = pending.get("decision_class").getAsString();
        int seat = pending.get("seat").getAsInt();
        String actorId = legal.get("actor_id").getAsString();
        JsonObject classPrefs = prefs.has(decisionClass) && prefs.get(decisionClass).isJsonObject()
                ? prefs.getAsJsonObject(decisionClass) : new JsonObject();
        List<String> wishes = stringsOrEmpty(classPrefs, String.valueOf(seat));
        if (wishes.isEmpty()) {
            wishes = stringsOrEmpty(classPrefs, "ALL");
        }
        // 1. Wish-list match over NATIVE offered labels only.
        for (String wish : wishes) {
            JsonObject hit = matchWish(legal, pending, wish);
            if (hit != null) {
                JsonObject proposal = toProposal(legal, pending, hit, POLICY_VERSION);
                if (proposal == null) {
                    continue;
                }
                applyNumericPref(proposal, pending, prefs, decisionClass, seat, false);
                if (!validateNumeric(proposal, pending)) {
                    continue;
                }
                return new WishPick(proposal, "wish:" + wish);
            }
        }
        // Strict wish classes: if wishes exist for this seat/class and none
        // matched, fall back to neutral (recorded) rather than forcing.
        // 2. Neutral fallbacks.
        JsonObject fallback = neutralProposal(legal, pending, prefs);
        if (fallback == null) {
            return null;
        }
        lastMatchIndex = indexOfAction(legal, pending,
                fallback.has("legal_action_id") && !fallback.get("legal_action_id").isJsonNull()
                        ? fallback.get("legal_action_id").getAsString() : "");
        applyNumericPref(fallback, pending, prefs, decisionClass, seat, true);
        if (!validateNumeric(fallback, pending)) {
            return null;
        }
        // Count land plays for the play-land cap.
        return new WishPick(fallback, "neutral");
    }

    private static JsonObject neutralProposal(
            JsonObject legal, JsonObject pending, JsonObject prefs) {
        String decisionClass = pending.get("decision_class").getAsString();
        int seat = pending.get("seat").getAsInt();
        JsonArray actions = legal.getAsJsonArray("actions");
        return switch (decisionClass) {
            case "mulligan" -> {
                JsonObject keep = actionOfOptionType(legal, "keep");
                yield keep == null ? null
                        : baseProposal("ws207-mulligan-keep", legal.get("actor_id").getAsString(),
                                keep.get("action_id").getAsString(),
                                keep.get("action_type").getAsString(), pending);
            }
            case "priority" -> {
                int cap = prefs.has("play_land_max") ? prefs.get("play_land_max").getAsInt() : 10;
                // Wish-driven casts already tried; neutral plays a land or passes.
                JsonObject chosen = null;
                JsonObject land = matchWish(legal, pending, "Play ");
                if (land != null && "true".equals(
                        prefs.has("neutral_play_land")
                                ? prefs.get("neutral_play_land").getAsString() : "true")) {
                    chosen = land;
                } else {
                    chosen = actionOfOptionType(legal, "pass_priority");
                    if (chosen == null) {
                        chosen = smallestAction(legal);
                    }
                }
                if (chosen == null) {
                    yield null;
                }
                yield baseProposal("ws207-priority", legal.get("actor_id").getAsString(),
                        chosen.get("action_id").getAsString(),
                        chosen.get("action_type").getAsString(), pending);
            }
            case "declare_attacker" -> {
                JsonObject attack = actionOfOptionType(legal, "declare_attacker");
                JsonObject hold = actionOfOptionType(legal, "hold_attacker");
                JsonObject chosen = hold != null ? hold : attack;
                if (chosen == null) {
                    chosen = smallestAction(legal);
                }
                yield chosen == null ? null
                        : baseProposal("ws207-attacker", legal.get("actor_id").getAsString(),
                                chosen.get("action_id").getAsString(),
                                chosen.get("action_type").getAsString(), pending);
            }
            case "declare_blocker" -> {
                // Empty selection (no blockers) via structural proposal.
                JsonObject empty = new JsonObject();
                empty.addProperty("proposal_id", "ws207-block-empty");
                empty.addProperty("actor_id", legal.get("actor_id").getAsString());
                empty.add(JsonNull.INSTANCE == null ? "x" : "legal_action_id", JsonNull.INSTANCE);
                empty.addProperty("action_type", "structural_decision");
                empty.add("target_ids", new JsonArray());
                empty.add("selected_modes", new JsonArray());
                JsonObject choices = new JsonObject();
                choices.addProperty("decision_id", pending.get("decision_id").getAsString());
                choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
                choices.add("ordering", new JsonArray());
                empty.add("choices", choices);
                yield empty;
            }
            case "mana_payment" -> {
                JsonObject chosen = smallestNonCancelManaAction(legal);
                yield chosen == null ? null
                        : baseProposal("ws207-mana", legal.get("actor_id").getAsString(),
                                chosen.get("action_id").getAsString(),
                                chosen.get("action_type").getAsString(), pending);
            }
            case "choose_object", "target", "target_amount", "choose_use", "choice",
                    "pile", "replacement_effect", "trigger_order", "mode" -> {
                JsonObject first = smallestAction(legal);
                yield first == null ? null
                        : withNumericDefault(baseProposal("ws207-" + decisionClass,
                                legal.get("actor_id").getAsString(),
                                first.get("action_id").getAsString(),
                                first.get("action_type").getAsString(), pending), pending);
            }
            case "announce_x", "amount", "multi_amount" -> {
                if (actions.size() != 1) {
                    yield null;
                }
                JsonObject numeric = actions.get(0).getAsJsonObject();
                yield withNumericDefault(baseProposal("ws207-numeric",
                        legal.get("actor_id").getAsString(),
                        numeric.get("action_id").getAsString(),
                        numeric.get("action_type").getAsString(), pending), pending);
            }
            default -> null;
        };
    }

    private static void applyNumericPref(
            JsonObject proposal, JsonObject pending, JsonObject prefs,
            String decisionClass, int seat, boolean neutral) {
        if (!proposal.has("choices")) {
            return;
        }
        JsonObject context = pending.has("context") && pending.get("context").isJsonObject()
                ? pending.getAsJsonObject("context") : new JsonObject();
        boolean needsNumeric = context.has("numeric_min") && !context.get("numeric_min").isJsonNull();
        if (!needsNumeric && !"announce_x".equals(decisionClass)
                && !"amount".equals(decisionClass) && !"multi_amount".equals(decisionClass)
                && !"target_amount".equals(decisionClass)) {
            return;
        }
        int min = context.has("numeric_min") && !context.get("numeric_min").isJsonNull()
                ? context.get("numeric_min").getAsInt() : 0;
        int max = context.has("numeric_max") && !context.get("numeric_max").isJsonNull()
                ? context.get("numeric_max").getAsInt() : min;
        int want = min;
        JsonObject xPrefs = prefs.has("numeric") && prefs.get("numeric").isJsonObject()
                ? prefs.getAsJsonObject("numeric") : new JsonObject();
        String seatKey = String.valueOf(seat);
        if (xPrefs.has(seatKey) && !xPrefs.get(seatKey).isJsonNull()) {
            try {
                want = xPrefs.get(seatKey).getAsInt();
            } catch (RuntimeException ignored) {
                want = min;
            }
        } else if (xPrefs.has("ALL") && !xPrefs.get("ALL").isJsonNull()) {
            try {
                want = xPrefs.get("ALL").getAsInt();
            } catch (RuntimeException ignored) {
                want = min;
            }
        }
        int clamped = Math.max(min, Math.min(max, want));
        proposal.getAsJsonObject("choices").addProperty("numeric_choice", clamped);
    }

    private static boolean validateNumeric(JsonObject proposal, JsonObject pending) {
        if (!proposal.has("choices") || !proposal.getAsJsonObject("choices").has("numeric_choice")) {
            return true;
        }
        JsonObject context = pending.has("context") && pending.get("context").isJsonObject()
                ? pending.getAsJsonObject("context") : null;
        if (context == null || !context.has("numeric_min") || !context.has("numeric_max")) {
            return false;
        }
        int value = proposal.getAsJsonObject("choices").get("numeric_choice").getAsInt();
        return value >= context.get("numeric_min").getAsInt()
                && value <= context.get("numeric_max").getAsInt();
    }

    private static JsonObject toProposal(
            JsonObject legal, JsonObject pending, JsonObject action, String policy) {
        JsonObject proposal = baseProposal(policy, legal.get("actor_id").getAsString(),
                action.get("action_id").getAsString(),
                action.get("action_type").getAsString(), pending);
        return withNumericDefault(proposal, pending);
    }

    private static JsonObject withNumericDefault(JsonObject proposal, JsonObject pending) {
        JsonObject context = pending.has("context") && pending.get("context").isJsonObject()
                ? pending.getAsJsonObject("context") : new JsonObject();
        if (context.has("numeric_min") && !context.get("numeric_min").isJsonNull()
                && !proposal.getAsJsonObject("choices").has("numeric_choice")) {
            // Only auto-fill when exactly one numeric action exists; callers
            // prefer explicit scenario values via applyNumericPref.
            proposal.getAsJsonObject("choices").addProperty(
                    "numeric_choice", context.get("numeric_min").getAsInt());
        }
        return proposal;
    }

    private static TwinPick pickTwinAction(
            JsonObject legal, JsonObject pending, List<StreamEntry> stream, int cursor) {
        if (cursor >= stream.size()) {
            return new TwinPick(null, "", true, "stream exhausted");
        }
        StreamEntry entry = stream.get(cursor);
        long offset = pending.get("decision_offset").getAsLong();
        String decisionClass = pending.get("decision_class").getAsString();
        if (entry.offset != offset || !entry.decisionClass.equals(decisionClass)) {
            return new TwinPick(null, "", true,
                    "stream mismatch at cursor " + cursor + ": expected offset "
                            + entry.offset + "/" + entry.decisionClass + " observed "
                            + offset + "/" + decisionClass);
        }
        JsonObject hit = matchLabel(legal, pending, entry.selectedLabel);
        if (hit == null && entry.selectedLabel.isEmpty()) {
            // Empty-selection frames (e.g. zero blockers): rebuild structurally.
            JsonObject rebuilt = neutralProposal(legal, pending, new JsonObject());
            if (rebuilt != null) {
                return new TwinPick(rebuilt, "<empty-selection>", false, "");
            }
            return new TwinPick(null, "", true,
                    "empty-selection frame not reproducible at offset " + offset);
        }
        if (hit == null) {
            return new TwinPick(null, "", true,
                    "offered label '" + entry.selectedLabel + "' absent at offset " + offset);
        }
        JsonObject proposal = toProposal(legal, pending, hit, POLICY_VERSION + "-twin");
        if (entry.numericChoice != null) {
            if (!proposal.has("choices")) {
                return new TwinPick(null, "", true,
                        "numeric replay unsupported at offset " + offset);
            }
            proposal.getAsJsonObject("choices").addProperty(
                    "numeric_choice", entry.numericChoice);
            if (!validateNumeric(proposal, pending)) {
                return new TwinPick(null, "", true,
                        "recorded numeric out of range at offset " + offset);
            }
        }
        return new TwinPick(proposal, entry.selectedLabel, false, "");
    }

    // ------------------------------------------------------------------
    // Matching helpers (native offered labels only; actions are mapped by
    // decision-bound action_id suffix, never invented).
    // ------------------------------------------------------------------

    /** Substring wish match over native offered labels (deterministic). */
    private static JsonObject matchWish(
            JsonObject legal, JsonObject pending, String wish) {
        String needle = wish.toLowerCase(Locale.ROOT).trim();
        if (needle.isEmpty()) {
            return null;
        }
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject best = null;
        int bestIndex = -1;
        int index = -1;
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            index++;
            JsonObject option = element.getAsJsonObject();
            String label = option.has("label") && !option.get("label").isJsonNull()
                    ? option.get("label").getAsString() : "";
            if (!label.toLowerCase(Locale.ROOT).contains(needle)) {
                continue;
            }
            String optionId = option.has("option_id") && !option.get("option_id").isJsonNull()
                    ? option.get("option_id").getAsString() : null;
            if (optionId == null) {
                continue;
            }
            JsonObject action = actionForOption(legal, decisionId, optionId);
            if (action == null) {
                continue;
            }
            // Tie-break by offered order (engine enumeration position), never
            // by UUID-bearing action_id: action_ids differ across JVMs, so a
            // UUID tie-break would inject harness nondeterminism into twins.
            if (best == null) {
                best = action;
                bestIndex = index;
            }
        }
        lastMatchIndex = bestIndex;
        return best;
    }

    /** Exact label match over native offered labels (twin replay). */
    private static JsonObject matchLabel(
            JsonObject legal, JsonObject pending, String label) {
        if (label == null || label.isEmpty()) {
            return null;
        }
        String decisionId = pending.get("decision_id").getAsString();
        JsonObject best = null;
        int bestIndex = -1;
        int index = -1;
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            index++;
            JsonObject option = element.getAsJsonObject();
            String offered = option.has("label") && !option.get("label").isJsonNull()
                    ? option.get("label").getAsString() : "";
            if (!label.equals(offered)) {
                continue;
            }
            String optionId = option.has("option_id") && !option.get("option_id").isJsonNull()
                    ? option.get("option_id").getAsString() : null;
            if (optionId == null) {
                continue;
            }
            JsonObject action = actionForOption(legal, decisionId, optionId);
            if (action == null) {
                continue;
            }
            // Same offered-order tie-break as the primary (see matchWish).
            if (best == null) {
                best = action;
                bestIndex = index;
            }
        }
        lastMatchIndex = bestIndex;
        return best;
    }

    private static JsonObject actionForOption(
            JsonObject legal, String decisionId, String optionId) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if ((decisionId + ":" + optionId)
                    .equals(action.get("action_id").getAsString())) {
                return action;
            }
        }
        return null;
    }

    /** Offered-order index backing an action (-1 when unmapped/empty). */
    private static int indexOfAction(
            JsonObject legal, JsonObject pending, String actionId) {
        if (actionId == null || !actionId.contains(":")) {
            return -1;
        }
        String suffix = actionId.substring(actionId.indexOf(':') + 1);
        int index = -1;
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            index++;
            JsonObject option = element.getAsJsonObject();
            String optionId = option.has("option_id") && !option.get("option_id").isJsonNull()
                    ? option.get("option_id").getAsString() : "";
            if (suffix.equals(optionId)) {
                return index;
            }
        }
        return -1;
    }

    /** Native pending label for a submitted action (stable across JVMs). */
    private static String pendingLabelForAction(JsonObject pending, String actionId) {
        if (actionId == null || !actionId.contains(":")) {
            return "";
        }
        String suffix = actionId.substring(actionId.indexOf(':') + 1);
        if ("numeric".equals(suffix)) {
            return "";
        }
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            String optionId = option.has("option_id") && !option.get("option_id").isJsonNull()
                    ? option.get("option_id").getAsString() : "";
            if (suffix.equals(optionId)) {
                return option.has("label") && !option.get("label").isJsonNull()
                        ? option.get("label").getAsString() : "";
            }
        }
        return "";
    }

    private static int countLabelMatches(JsonObject pending, String label) {
        if (label == null || label.isEmpty()) {
            return 0;
        }
        int count = 0;
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            String offered = option.has("label") && !option.get("label").isJsonNull()
                    ? option.get("label").getAsString() : "";
            if (label.equals(offered)) {
                count++;
            }
        }
        return count;
    }

    private static JsonObject smallestAction(JsonObject legal) {
        JsonObject best = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject candidate = element.getAsJsonObject();
            if (best == null || candidate.get("action_id").getAsString()
                    .compareTo(best.get("action_id").getAsString()) < 0) {
                best = candidate;
            }
        }
        return best;
    }

    private static JsonObject actionOfOptionType(JsonObject legal, String optionType) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.has("metadata") && action.get("metadata").isJsonObject()
                    ? action.getAsJsonObject("metadata") : new JsonObject();
            String actual = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (optionType.equals(actual)) {
                return action;
            }
        }
        return null;
    }

    private static JsonObject smallestNonCancelManaAction(JsonObject legal) {
        JsonObject best = null;
        JsonObject cancel = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.has("metadata") && action.get("metadata").isJsonObject()
                    ? action.getAsJsonObject("metadata") : new JsonObject();
            String optionType = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if ("cancel_mana_payment".equals(optionType)) {
                cancel = action;
                continue;
            }
            if (best == null || action.get("action_id").getAsString()
                    .compareTo(best.get("action_id").getAsString()) < 0) {
                best = action;
            }
        }
        return best != null ? best : cancel;
    }

    private static String actionLabelById(JsonObject legal, String actionId) {
        // Legacy metadata fallback (unstable across JVMs; pending labels are
        // authoritative). Kept only for diagnostics, never for twin matching.
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (actionId.equals(action.get("action_id").getAsString())) {
                if (action.has("label") && !action.get("label").isJsonNull()) {
                    return action.get("label").getAsString();
                }
                return action.getAsJsonObject("metadata").toString();
            }
        }
        return null;
    }

    private static JsonObject baseProposal(
            String proposalId, String actorId, String actionId,
            String actionType, JsonObject pending) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", actionId);
        proposal.addProperty("action_type", actionType);
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", pending.get("decision_id").getAsString());
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        // NOTE: selected_option_ids intentionally omitted: the projection
        // derives the single selection from legal_action_id (WS204 shape).
        // Present-but-empty selected_option_ids with a non-blank
        // legal_action_id is rejected by the projection.
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", POLICY_VERSION);
        return proposal;
    }

    // ------------------------------------------------------------------
    // Session bootstrap + assertion capture.
    // ------------------------------------------------------------------

    private record SessionHandles(XmageFullGameSession session, String deckId,
                                  List<String> handles, long rulesSeed,
                                  boolean rulesSeedExplicit) {
        JsonArray handlesJson() {
            JsonArray out = new JsonArray();
            handles.forEach(out::add);
            return out;
        }
    }

    private static SessionHandles startSession(
            String gameId, Path decksFile, int startingSeat, long seed) throws Exception {
        JsonObject decks = JsonParser.parseString(
                Files.readString(decksFile, StandardCharsets.UTF_8)).getAsJsonObject();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = new ArrayList<>(4);
        String deckId = "";
        for (int seat = 0; seat < 4; seat++) {
            JsonObject spec = decks.getAsJsonObject("seat" + seat);
            deckId = spec.get("deck_id").getAsString();
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    spec.get("deck_id").getAsString(),
                    spec.get("deck_hash").getAsString(),
                    strings(spec.getAsJsonArray("mainboard")),
                    strings(spec.getAsJsonArray("commanders")));
            handles.add(imported.deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                gameId, handles, startingSeat, 40, seed, importer);
        // WS208/WS212 IMPACT BINDING (qualification-only): bind the per-game
        // Rules RNG explicitly BEFORE game.start/init via the pinned engine's
        // public Game contract. No production code is touched; the hook is
        // reflective setup control inside this qualification-only driver.
        // RandomUtil-only runs are NOT reproducible setup evidence.
        CommanderFreeForAll rulesGame = field(session, "game", CommanderFreeForAll.class);
        rulesGame.setRulesSeed(seed);
        rulesGame.setRequireExplicitSeed(true);
        boolean rulesSeedExplicit = rulesGame.isRulesSeedExplicit();
        long boundRulesSeed = rulesGame.getRulesSeed();
        if (!rulesSeedExplicit || boundRulesSeed != seed) {
            throw new IllegalStateException(
                    "WS207_RULES_SEED_BINDING_FAILED: explicit=" + rulesSeedExplicit
                            + " rulesSeed=" + boundRulesSeed + " want=" + seed);
        }
        session.start();
        return new SessionHandles(session, deckId, handles, boundRulesSeed, rulesSeedExplicit);
    }

    /** QUALIFICATION_ASSERTION_ONLY: privileged terminal state, never pilot input. */
    private static JsonObject captureAssertionState(SessionHandles handles) throws Exception {
        CommanderFreeForAll game = field(handles.session, "game", CommanderFreeForAll.class);
        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> players =
                (List<XmageFullGamePlayer>) field(handles.session, "players", List.class);
        Map<String, Integer> controllerToSeat = new LinkedHashMap<>();
        JsonArray seatStates = new JsonArray();
        for (int index = 0; index < players.size(); index++) {
            XmageFullGamePlayer player = players.get(index);
            controllerToSeat.put(player.getId().toString(), index);
            JsonObject row = new JsonObject();
            row.addProperty("seat", index);
            try {
                row.addProperty("life", player.getLife());
            } catch (RuntimeException exc) {
                row.addProperty("life", -999);
            }
            try {
                row.addProperty("hand_size", player.getHand().size());
            } catch (RuntimeException exc) {
                row.addProperty("hand_size", -1);
            }
            try {
                row.addProperty("library_size", player.getLibrary().size());
            } catch (RuntimeException exc) {
                row.addProperty("library_size", -1);
            }
            try {
                JsonArray grave = new JsonArray();
                for (mage.cards.Card card
                        : player.getGraveyard().getCards(game)) {
                    try {
                        grave.add(card.getName());
                    } catch (RuntimeException ignored) {
                        grave.add("<unknown>");
                    }
                }
                row.add("graveyard", grave);
            } catch (RuntimeException exc) {
                row.add("graveyard", new JsonArray());
            }
            seatStates.add(row);
        }
        JsonArray permanents = new JsonArray();
        try {
            game.getBattlefield().getAllPermanents().forEach(permanent -> {
                JsonObject row = new JsonObject();
                try {
                    row.addProperty("name", permanent.getName());
                } catch (RuntimeException exc) {
                    row.addProperty("name", "<unknown>");
                }
                try {
                    Integer seat = controllerToSeat.get(
                            permanent.getControllerId().toString());
                    row.addProperty("controller_seat", seat == null ? -1 : seat);
                } catch (RuntimeException exc) {
                    row.addProperty("controller_seat", -1);
                }
                try {
                    row.addProperty("power", permanent.getPower().getValue());
                    row.addProperty("toughness", permanent.getToughness().getValue());
                } catch (RuntimeException exc) {
                    row.addProperty("power", -999);
                    row.addProperty("toughness", -999);
                }
                try {
                    row.addProperty("is_copy", permanent.isCopy());
                } catch (RuntimeException | LinkageError exc) {
                    row.addProperty("is_copy", false);
                }
                try {
                    row.addProperty("abilities", permanent.getAbilities(game).size());
                } catch (RuntimeException exc) {
                    row.addProperty("abilities", -1);
                }
                permanents.add(row);
            });
        } catch (RuntimeException exc) {
            JsonObject failed = new JsonObject();
            failed.addProperty("battlefield_failed", String.valueOf(exc.getMessage()));
            permanents.add(failed);
        }
        JsonObject out = new JsonObject();
        out.add("seats", seatStates);
        out.add("battlefield", permanents);
        return out;
    }

    // ------------------------------------------------------------------
    // Small utilities.
    // ------------------------------------------------------------------

    private static JsonObject summarizePending(JsonObject pending, boolean withOptions) {
        JsonObject out = new JsonObject();
        out.addProperty("offset", pending.get("decision_offset").getAsLong());
        out.addProperty("class", pending.get("decision_class").getAsString());
        out.addProperty("actor_seat", pending.get("seat").getAsInt());
        out.addProperty("prompt", pending.get("prompt").getAsString());
        out.addProperty("offered_count", pending.getAsJsonArray("legal_options").size());
        out.add("offered_types", typeHistogram(pending));
        if (withOptions) {
            JsonArray labels = new JsonArray();
            for (JsonElement element : pending.getAsJsonArray("legal_options")) {
                JsonObject option = element.getAsJsonObject();
                labels.add(option.has("label") && !option.get("label").isJsonNull()
                        ? option.get("label").getAsString()
                        : option.toString());
            }
            out.add("offered_labels", labels);
            JsonObject context = pending.has("context") && pending.get("context").isJsonObject()
                    ? pending.getAsJsonObject("context") : new JsonObject();
            out.add("context", context);
        }
        return out;
    }

    private static JsonArray typeHistogram(JsonObject pending) {
        Map<String, Integer> histogram = new LinkedHashMap<>();
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            String type = option.has("option_type") && !option.get("option_type").isJsonNull()
                    ? option.get("option_type").getAsString() : "generic";
            histogram.merge(type, 1, Integer::sum);
        }
        JsonArray out = new JsonArray();
        histogram.forEach((key, value) -> {
            JsonObject row = new JsonObject();
            row.addProperty("type", key);
            row.addProperty("count", value);
            out.add(row);
        });
        return out;
    }

    private static List<StreamEntry> readStream(Path streamFile) throws Exception {
        JsonObject root = JsonParser.parseString(
                Files.readString(streamFile, StandardCharsets.UTF_8)).getAsJsonObject();
        List<StreamEntry> out = new ArrayList<>();
        for (JsonElement element : root.getAsJsonArray("decision_stream")) {
            JsonObject row = element.getAsJsonObject();
            out.add(new StreamEntry(row.get("offset").getAsLong(),
                    row.get("class").getAsString(),
                    row.has("selected_label") && !row.get("selected_label").isJsonNull()
                            ? row.get("selected_label").getAsString() : "",
                    row.has("numeric_choice") && !row.get("numeric_choice").isJsonNull()
                            ? row.get("numeric_choice").getAsInt() : null));
        }
        return out;
    }

    private static List<String> strings(JsonArray array) {
        List<String> out = new ArrayList<>(array.size());
        for (JsonElement element : array) {
            out.add(element.getAsString());
        }
        return out;
    }

    private static List<String> stringsOrEmpty(JsonObject prefs, String key) {
        if (!prefs.has(key) || !prefs.get(key).isJsonArray()) {
            return List.of();
        }
        return strings(prefs.getAsJsonArray(key));
    }

    private static JsonObject optObject(JsonObject parent, String key) {
        if (!parent.has(key) || parent.get(key).isJsonNull()
                || !parent.get(key).isJsonObject()) {
            return null;
        }
        return parent.getAsJsonObject(key);
    }

    @SuppressWarnings("unchecked")
    private static <T> T field(Object target, String name, Class<T> type)
            throws ReflectiveOperationException {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return (T) field.get(target);
    }

    private static Map<String, String> parseArgs(String[] args) {
        Map<String, String> out = new LinkedHashMap<>();
        for (String arg : args) {
            if (arg.startsWith("--") && arg.contains("=")) {
                out.put(arg.substring(2, arg.indexOf('=')),
                        arg.substring(arg.indexOf('=') + 1));
            }
        }
        return out;
    }

    private static String required(Map<String, String> argv, String key) {
        String value = argv.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("missing required arg --" + key);
        }
        return value;
    }
}

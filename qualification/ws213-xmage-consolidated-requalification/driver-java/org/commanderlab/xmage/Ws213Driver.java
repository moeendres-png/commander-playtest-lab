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
 * WS213 qualification-only consolidated slot executor (fresh JVM per game).
 *
 * <p>Adapted from the sealed WS205 First-Wave driver (provenance:
 * qualification/ws205-xmage-ws90-first-wave/driver-java/.../Ws205FirstWaveDriver.java
 * at audit base 17ddab61; that file is untouched). Drives ONE isolated
 * full-game session exclusively through the WS204 decision-scoped generic
 * boundary plus the WS213 authoritative concede boundary. Every selection is
 * an XMage-offered native option; XMage executes natively. No legality is
 * computed here; no outcome is written directly.</p>
 *
 * <p>WS213 differences: production Rules-seed binding is owned by
 * XmageFullGameSession (no reflective hook); ENGINE_PIN is the WS212
 * production candidate; per-row hidden-information verdicts (structural plus
 * test-oracle UUID scan); optional concede interrogation from prefs
 * ({@code _concede}); live binding snapshot in the envelope; an
 * {@code opening-hand} mode for D5 fresh-process twin evidence.</p>
 *
 * <p>Pilot policy {@code ws213-pilot-v1}: deterministic offered-only
 * selection with per-slot wish-list matching (substring over offered display
 * label plus metadata, never requested-result filtering), neutral fallbacks
 * (pass / hold / empty blockers / lexicographic smallest / schema-minimum
 * numerics), fail-closed unknown classes.</p>
 *
 * <p>Modes: {@code run} (primary), {@code twin} (follow a recorded stream),
 * {@code probe} (print early decisions for calibration),
 * {@code probe-deck} (deck import validation only),
 * {@code opening-hand} (pregame opening recording for twin evidence).</p>
 */
public final class Ws213Driver {

    private static final String POLICY_VERSION = "ws213-pilot-v1";
    private static final String ENGINE_PIN = "db134b9737e951367d65ef5806ad986319cc73ab";

    /** Offered-order index of the last matcher pick (-1 when unmatched). */
    private static int lastMatchIndex = -1;

    private Ws213Driver() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> argv = parseArgs(args);
        String mode = required(argv, "mode");
        switch (mode) {
            case "probe-deck" -> runProbeDeck(argv);
            case "probe" -> runProbe(argv);
            case "run" -> runGame(argv, false);
            case "twin" -> runGame(argv, true);
            case "opening-hand" -> runOpeningHand(argv);
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
        SessionHandles handles = startSession("ws213-probe", decksFile, 0, seed);
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
    // opening-hand: pregame opening recording for D5 twin evidence.
    // ------------------------------------------------------------------

    /**
     * Records the dealt opening (per-seat hand names/library sizes in seat
     * order plus the first pending decision) after at most 12 pregame answers
     * (starting-player select, mulligan keep). Production session binds the
     * Rules seed natively; the binding snapshot is recorded. Hand contents
     * are QUALIFICATION_ASSERTION_ONLY, never pilot input.
     */
    private static void runOpeningHand(Map<String, String> argv) throws Exception {
        Path decksFile = Path.of(required(argv, "decks"));
        long seed = Long.parseLong(required(argv, "seed"));
        Path outFile = Path.of(required(argv, "out"));
        int startingSeat = Integer.parseInt(
                argv.getOrDefault("starting-seat",
                        Integer.toString((int) Math.floorMod(seed, 4))));
        SessionHandles handles = startSession(
                "ws213-opening-" + seed, decksFile, startingSeat, seed);
        JsonArray steps = new JsonArray();
        String stop = "dealt";
        for (int step = 0; step < 12; step++) {
            JsonObject payload = handles.session.pendingDecisionPayload();
            JsonObject pending = optObject(payload, "decision");
            if (pending == null) {
                stop = "terminal";
                break;
            }
            if (openingDealt(handles)) {
                JsonObject first = new JsonObject();
                first.addProperty("class", pending.get("decision_class").getAsString());
                first.addProperty("seat", pending.get("seat").getAsInt());
                first.addProperty("prompt", pending.get("prompt").getAsString());
                JsonObject out = new JsonObject();
                out.addProperty("schema", "ws213.opening-hand.v1");
                out.addProperty("engine_pin", ENGINE_PIN);
                out.addProperty("seed", seed);
                out.addProperty("starting_seat", startingSeat);
                out.add("pregame_steps", steps);
                out.addProperty("pregame_stop", stop);
                out.add("opening", captureOpening(handles));
                out.add("first_decision", first);
                try {
                    out.add("rules_seed_binding",
                            handles.session.rulesSeedBindingPayload());
                } catch (RuntimeException exc) {
                    out.addProperty("binding_capture_failed",
                            String.valueOf(exc.getMessage()));
                }
                Files.writeString(outFile,
                        new GsonBuilder().setPrettyPrinting().create().toJson(out),
                        StandardCharsets.UTF_8);
                System.out.println("WS213_OPENING_WRITTEN " + outFile);
                System.exit(0);
            }
            String decisionClass = pending.get("decision_class").getAsString();
            String prompt = pending.get("prompt").getAsString();
            JsonObject legal = handles.session.legalActionsPayload();
            JsonObject proposal = null;
            if ("choose_object".equals(decisionClass)
                    && prompt.contains("Select a starting player")) {
                proposal = startingPlayerProposal(legal, startingSeat,
                        "ws213-opening-starter");
            } else if ("mulligan".equals(decisionClass)) {
                proposal = keepProposal(legal, "ws213-opening-keep");
            }
            JsonObject stepRow = new JsonObject();
            stepRow.addProperty("class", decisionClass);
            if (proposal == null) {
                stepRow.addProperty("basis", "unexpected-pregame-class");
                steps.add(stepRow);
                stop = "unexpected-pregame-class:" + decisionClass;
                break;
            }
            stepRow.addProperty("basis", "neutral-pregame");
            steps.add(stepRow);
            handles.session.submitAction(proposal);
        }
        JsonObject out = new JsonObject();
        out.addProperty("schema", "ws213.opening-hand.v1");
        out.addProperty("engine_pin", ENGINE_PIN);
        out.addProperty("seed", seed);
        out.addProperty("starting_seat", startingSeat);
        out.add("pregame_steps", steps);
        out.addProperty("pregame_stop", stop);
        Files.writeString(outFile,
                new GsonBuilder().setPrettyPrinting().create().toJson(out),
                StandardCharsets.UTF_8);
        System.out.println("WS213_OPENING_WRITTEN " + outFile);
        System.exit(0);
    }

    private static boolean openingDealt(SessionHandles handles) throws Exception {
        CommanderFreeForAll game = field(handles.session, "game", CommanderFreeForAll.class);
        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> players =
                (List<XmageFullGamePlayer>) field(handles.session, "players", List.class);
        for (XmageFullGamePlayer player : players) {
            if (player.getLibrary().size() < 99) {
                return true;
            }
        }
        return false;
    }

    private static JsonArray captureOpening(SessionHandles handles) throws Exception {
        CommanderFreeForAll game = field(handles.session, "game", CommanderFreeForAll.class);
        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> players =
                (List<XmageFullGamePlayer>) field(handles.session, "players", List.class);
        JsonArray seats = new JsonArray();
        for (int index = 0; index < players.size(); index++) {
            XmageFullGamePlayer player = players.get(index);
            JsonObject row = new JsonObject();
            row.addProperty("seat", index);
            JsonArray hand = new JsonArray();
            for (mage.cards.Card card : player.getHand().getCards(game)) {
                hand.add(card.getName());
            }
            row.add("hand_names", hand);
            row.addProperty("hand_size", player.getHand().size());
            row.addProperty("library_size", player.getLibrary().size());
            seats.add(row);
        }
        return seats;
    }

    private static JsonObject firstActionProposal(JsonObject legal, String proposalId) {
        JsonArray actions = legal.getAsJsonArray("actions");
        if (actions.size() == 0) {
            return null;
        }
        JsonObject first = actions.get(0).getAsJsonObject();
        return baseProposal(proposalId, legal.get("actor_id").getAsString(),
                first.get("action_id").getAsString(),
                first.get("action_type").getAsString(), legal);
    }

    /**
     * Starting-player select: the native options are labelled
     * "Full Game Seat N". Prefer the requested seat for determinism; fall
     * back to the lexicographically smallest offered action (still
     * deterministic across same-seed twins).
     */
    private static JsonObject startingPlayerProposal(
            JsonObject legal, int startingSeat, String proposalId) {
        JsonArray actions = legal.getAsJsonArray("actions");
        if (actions.size() == 0) {
            return null;
        }
        String want = "Seat " + (startingSeat + 1);
        JsonObject chosen = null;
        for (JsonElement element : actions) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String label = metadata.has("label") && !metadata.get("label").isJsonNull()
                    ? metadata.get("label").getAsString() : "";
            if (label.contains(want)) {
                chosen = action;
                break;
            }
            if (chosen == null || action.get("action_id").getAsString()
                    .compareTo(chosen.get("action_id").getAsString()) < 0) {
                chosen = action;
            }
        }
        return baseProposal(proposalId, legal.get("actor_id").getAsString(),
                chosen.get("action_id").getAsString(),
                chosen.get("action_type").getAsString(), legal);
    }

    private static JsonObject keepProposal(JsonObject legal, String proposalId) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if ("mulligan".equals(action.get("action_type").getAsString())
                    && "keep".equals(action.getAsJsonObject("metadata")
                            .get("option_type").getAsString())) {
                return baseProposal(proposalId, legal.get("actor_id").getAsString(),
                        action.get("action_id").getAsString(),
                        action.get("action_type").getAsString(), legal);
            }
        }
        return null;
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
                "ws213-" + slot + (subcase.isEmpty() ? "" : "-" + subcase)
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
        boolean damageSpoiled = false;
        JsonObject concedeRecord = null;
        int hiddenRows = 0;
        int hiddenViolations = 0;
        List<String> hiddenViolationDetail = new ArrayList<>();

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

            // WS213 per-row hidden-information verdict (test-only oracle;
            // never pilot input). Computed pre-submit at park time.
            JsonObject hiddenVerdict = hiddenInfoVerdict(handles, pending);
            hiddenRows++;
            if (!hiddenVerdict.get("ok").getAsBoolean()) {
                hiddenViolations++;
                if (hiddenViolationDetail.size() < 8) {
                    hiddenViolationDetail.add("offset=" + offset + " class=" + decisionClass
                            + " " + hiddenVerdict.get("detail").getAsString());
                }
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
            // WS213 one-shot damage-spoil (combat scan only, never twins):
            // answer the first multi_amount frame with the schema maximum to
            // exercise the native WS206 legality validation + bounded
            // re-request path. The twin replays the recorded value exactly.
            if (!twin && !damageSpoiled && "multi_amount".equals(decisionClass)
                    && prefs.has("_spoil_damage_once")
                    && prefs.get("_spoil_damage_once").getAsBoolean()) {
                JsonObject context = pending.getAsJsonObject("context");
                if (context.has("numeric_max") && !context.get("numeric_max").isJsonNull()
                        && proposal.has("choices")
                        && proposal.getAsJsonObject("choices").isJsonObject()) {
                    proposal.getAsJsonObject("choices").addProperty(
                            "numeric_choice", context.get("numeric_max").getAsInt());
                    damageSpoiled = true;
                    selectionBasis = selectionBasis + "+spoil_damage";
                }
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
            JsonObject pendingContext = pending.has("context")
                    && pending.get("context").isJsonObject()
                    ? pending.getAsJsonObject("context") : new JsonObject();
            if (pendingContext.has("numeric_min")
                    && !pendingContext.get("numeric_min").isJsonNull()) {
                record.addProperty("numeric_min",
                        pendingContext.get("numeric_min").getAsInt());
            }
            if (pendingContext.has("numeric_max")
                    && !pendingContext.get("numeric_max").isJsonNull()) {
                record.addProperty("numeric_max",
                        pendingContext.get("numeric_max").getAsInt());
            }
            record.addProperty("selection_basis", selectionBasis);
            record.addProperty("advanced", true);
            record.add("hidden_info", hiddenVerdict);
            decisionStream.add(record);
            // WS213 concede interrogation from prefs ({_concede:
            // {after_decisions, seat}}). Executes once, then play continues.
            if (concedeRecord == null) {
                concedeRecord = maybeConcede(handles, prefs, answered);
            }
        }

        JsonObject evidence = new JsonObject();
        evidence.addProperty("schema", "ws213.slot-evidence.v1");
        evidence.addProperty("slot", slot);
        evidence.addProperty("subcase", subcase);
        evidence.addProperty("engine_pin", ENGINE_PIN);
        evidence.addProperty("seed", seed);
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
        // WS213 live binding snapshot (production-owned proof). All WS213
        // envelope additions land BEFORE serialization.
        try {
            evidence.add("rules_seed_binding", handles.session.rulesSeedBindingPayload());
        } catch (RuntimeException exc) {
            evidence.addProperty("binding_capture_failed", String.valueOf(exc.getMessage()));
        }
        if (concedeRecord != null) {
            evidence.add("concede_record", concedeRecord);
        }
        evidence.addProperty("hidden_info_rows_scanned", hiddenRows);
        evidence.addProperty("hidden_info_violations", hiddenViolations);
        evidence.addProperty("damage_spoiled", damageSpoiled);
        JsonArray hiddenDetail = new JsonArray();
        hiddenViolationDetail.forEach(hiddenDetail::add);
        evidence.add("hidden_info_violation_detail", hiddenDetail);
        Files.writeString(outFile, new GsonBuilder().setPrettyPrinting().create().toJson(evidence),
                StandardCharsets.UTF_8);
        System.out.println("WS213_EVIDENCE_WRITTEN " + outFile + " answered=" + answered
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
            JsonObject wrong = baseProposal("ws213-probe-wrong-actor", "intruder-actor",
                    probeAction, actionType, pending);
            handles.session.submitAction(wrong);
            out.addProperty("wrong_actor", "NOT_REJECTED");
        } catch (RuntimeException exc) {
            out.addProperty("wrong_actor", "REJECTED:" + exc.getMessage());
        }
        // Unknown option.
        try {
            JsonObject unknown = baseProposal("ws213-probe-unknown", actorId,
                    decisionId + ":ghost-option-ws213", actionType, pending);
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
    // WS213 hidden-information verdict + concede interrogation.
    // ------------------------------------------------------------------

    /**
     * Test-only principal-scoping verdict for one parked decision. Structural:
     * non-actor entries must carry no hand/mana_pool keys. Oracle: opponent
     * hand/library card UUIDs (read reflectively, never pilot input) must
     * appear nowhere in the actor's serialized view.
     */
    private static JsonObject hiddenInfoVerdict(
            SessionHandles handles, JsonObject pending) {
        JsonObject verdict = new JsonObject();
        verdict.addProperty("ok", true);
        verdict.addProperty("detail", "");
        try {
            JsonObject pilotState = pending.getAsJsonObject("pilot_state");
            String actorId = pending.get("actor_id").getAsString();
            for (JsonElement element : pilotState.getAsJsonArray("players")) {
                JsonObject entry = element.getAsJsonObject();
                boolean isActor = entry.get("is_actor").getAsBoolean();
                if (!isActor && (entry.has("hand") || entry.has("mana_pool"))) {
                    return failVerdict("structural: non-actor private zone present");
                }
            }
            CommanderFreeForAll game =
                    field(handles.session, "game", CommanderFreeForAll.class);
            Set<String> hidden = new java.util.HashSet<>();
            for (mage.players.Player player : game.getPlayers().values()) {
                if (player.getId().toString().equals(actorId)) {
                    continue;
                }
                for (mage.cards.Card card : player.getHand().getCards(game)) {
                    hidden.add(card.getId().toString());
                }
                for (mage.cards.Card card : player.getLibrary().getCards(game)) {
                    hidden.add(card.getId().toString());
                }
            }
            verdict.addProperty("oracle_ids_checked", hidden.size());
            String serialized = pilotState.toString();
            for (String id : hidden) {
                if (serialized.contains(id)) {
                    return failVerdict("oracle: hidden card identity present");
                }
            }
        } catch (RuntimeException exc) {
            return failVerdict("oracle_error: " + exc.getMessage());
        } catch (Exception exc) {
            return failVerdict("oracle_error: " + exc.getMessage());
        }
        return verdict;
    }

    private static JsonObject failVerdict(String detail) {
        JsonObject verdict = new JsonObject();
        verdict.addProperty("ok", false);
        verdict.addProperty("detail", detail);
        return verdict;
    }

    /**
     * Optional concede interrogation. Prefs {@code _concede} carries
     * {@code after_decisions} (answered count) and {@code seat}. When the
     * answered count reaches the mark, the driver offers and submits a native
     * concession for that seat's exact principal, then play continues. The
     * offer/submit path is the production session boundary; availability and
     * execution stay engine-owned.
     */
    private static JsonObject maybeConcede(
            SessionHandles handles, JsonObject prefs, int answered) {
        if (!prefs.has("_concede") || !prefs.get("_concede").isJsonObject()) {
            return null;
        }
        JsonObject spec = prefs.getAsJsonObject("_concede");
        int after = spec.has("after_decisions") ? spec.get("after_decisions").getAsInt() : -1;
        int seat = spec.has("seat") ? spec.get("seat").getAsInt() : -1;
        if (after < 0 || seat < 0 || answered != after) {
            return null;
        }
        JsonObject record = new JsonObject();
        record.addProperty("seat", seat);
        record.addProperty("after_decisions", answered);
        try {
            String principal = principalForSeat(handles, seat);
            record.addProperty("principal", principal);
            JsonObject offer = handles.session.concedeOfferPayload(principal);
            record.addProperty("offered", offer.get("concede_available").getAsBoolean());
            if (!offer.get("concede_available").getAsBoolean()) {
                record.addProperty("executed", false);
                record.addProperty("note", "not offered by engine");
                return record;
            }
            JsonObject proposal = new JsonObject();
            proposal.addProperty("proposal_id", "ws213-concede-interrogation");
            proposal.addProperty("actor_id", principal);
            proposal.addProperty("player_id", principal);
            JsonObject result = handles.session.submitConcede(proposal);
            record.addProperty("executed", true);
            record.addProperty("conceded_actor_id",
                    result.get("conceded_actor_id").getAsString());
        } catch (RuntimeException exc) {
            record.addProperty("executed", false);
            record.addProperty("error", exc.getMessage());
        }
        return record;
    }

    private static String principalForSeat(SessionHandles handles, int seat) {
        JsonObject payload = handles.session.pendingDecisionPayload();
        JsonArray outcomes = payload.getAsJsonArray("outcomes");
        if (seat < 0 || seat >= outcomes.size()) {
            throw new IllegalStateException("no principal at seat " + seat);
        }
        return outcomes.get(seat).getAsJsonObject().get("player_id").getAsString();
    }

    // ------------------------------------------------------------------
    // Pilot ws213-pilot-v1.
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
                        : baseProposal("ws213-mulligan-keep", legal.get("actor_id").getAsString(),
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
                yield baseProposal("ws213-priority", legal.get("actor_id").getAsString(),
                        chosen.get("action_id").getAsString(),
                        chosen.get("action_type").getAsString(), pending);
            }
            case "declare_attacker" -> {
                JsonObject attack = actionOfOptionType(legal, "declare_attacker");
                JsonObject hold = actionOfOptionType(legal, "hold_attacker");
                // WS213 combat scan: prefs _attack_all lists seats that press
                // every offered attack (offered-only); default holds.
                boolean pressAttack = hasSeat(prefs, "_attack_all", seat);
                JsonObject chosen = pressAttack
                        ? (attack != null ? attack : hold)
                        : (hold != null ? hold : attack);
                if (chosen == null) {
                    chosen = smallestAction(legal);
                }
                yield chosen == null ? null
                        : baseProposal("ws213-attacker", legal.get("actor_id").getAsString(),
                                chosen.get("action_id").getAsString(),
                                chosen.get("action_type").getAsString(), pending);
            }
            case "declare_blocker" -> {
                // WS213 combat scan: prefs _block_all lists seats that declare
                // every offered block (offered-only multi-select); default is
                // the empty selection (no blockers) via structural proposal.
                if (hasSeat(prefs, "_block_all", seat)) {
                    JsonObject all = blockAllProposal(legal, pending);
                    if (all != null) {
                        yield all;
                    }
                }
                JsonObject empty = new JsonObject();
                empty.addProperty("proposal_id", "ws213-block-empty");
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
                        : baseProposal("ws213-mana", legal.get("actor_id").getAsString(),
                                chosen.get("action_id").getAsString(),
                                chosen.get("action_type").getAsString(), pending);
            }
            case "choose_object", "target", "target_amount", "choose_use", "choice",
                    "pile", "replacement_effect", "trigger_order", "mode" -> {
                JsonObject first = smallestAction(legal);
                yield first == null ? null
                        : withNumericDefault(baseProposal("ws213-" + decisionClass,
                                legal.get("actor_id").getAsString(),
                                first.get("action_id").getAsString(),
                                first.get("action_type").getAsString(), pending), pending);
            }
            case "announce_x", "amount", "multi_amount" -> {
                if (actions.size() != 1) {
                    yield null;
                }
                JsonObject numeric = actions.get(0).getAsJsonObject();
                yield withNumericDefault(baseProposal("ws213-numeric",
                        legal.get("actor_id").getAsString(),
                        numeric.get("action_id").getAsString(),
                        numeric.get("action_type").getAsString(), pending), pending);
            }
            default -> null;
        };
    }

    private static boolean hasSeat(JsonObject prefs, String key, int seat) {
        if (prefs == null || !prefs.has(key) || !prefs.get(key).isJsonArray()) {
            return false;
        }
        for (JsonElement element : prefs.getAsJsonArray(key)) {
            try {
                if (element.getAsInt() == seat) {
                    return true;
                }
            } catch (RuntimeException ignored) {
                // Non-integer entries never match; selection stays offered-only.
            }
        }
        return false;
    }

    /**
     * Offered-only block-all proposal: every offered block option selected.
     * Membership, bounds and actor/revision checks stay projection-owned; a
     * rejection fails the run closed (submit_rejected) with full evidence.
     */
    private static JsonObject blockAllProposal(JsonObject legal, JsonObject pending) {
        JsonArray options = pending.getAsJsonArray("legal_options");
        if (options.size() == 0) {
            return null;
        }
        String decisionId = pending.get("decision_id").getAsString();
        String firstAction = null;
        JsonArray selected = new JsonArray();
        for (JsonElement element : options) {
            JsonObject option = element.getAsJsonObject();
            if (!option.has("option_id") || option.get("option_id").isJsonNull()) {
                return null;
            }
            String optionId = option.get("option_id").getAsString();
            selected.add(optionId);
            if (firstAction == null) {
                firstAction = decisionId + ":" + optionId;
            }
        }
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "ws213-block-all");
        proposal.addProperty("actor_id", legal.get("actor_id").getAsString());
        proposal.addProperty("legal_action_id", firstAction);
        proposal.addProperty("action_type", "declare_blockers");
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.addProperty("decision_id", decisionId);
        choices.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        choices.add("selected_option_ids", selected);
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", POLICY_VERSION);
        return proposal;
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
            // Empty-selection frames (e.g. zero blockers, numeric-only
            // announce_x/amount/multi_amount): rebuild structurally, then
            // replay the recorded numeric (WS213 harness fidelity fix: the
            // WS205 predecessor answered schema-minimum here, diverging from
            // the primary on non-minimum numerics without engine cause).
            JsonObject rebuilt = neutralProposal(legal, pending, new JsonObject());
            if (rebuilt != null) {
                if (entry.numericChoice != null) {
                    if (!rebuilt.has("choices")) {
                        return new TwinPick(null, "", true,
                                "numeric replay unsupported at offset " + offset);
                    }
                    rebuilt.getAsJsonObject("choices").addProperty(
                            "numeric_choice", entry.numericChoice);
                    if (!validateNumeric(rebuilt, pending)) {
                        return new TwinPick(null, "", true,
                                "recorded numeric out of range at offset " + offset);
                    }
                }
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
                                  List<String> handles) {
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
        session.start();
        return new SessionHandles(session, deckId, handles);
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

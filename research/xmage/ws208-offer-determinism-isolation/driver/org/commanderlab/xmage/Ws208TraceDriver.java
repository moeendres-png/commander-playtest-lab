package org.commanderlab.xmage;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.MageObject;
import mage.cards.Card;
import mage.constants.ManaType;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;

import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * WS208 layered-capture tracer (research-only, diagnostics).
 *
 * <p>Re-runs a WS205 construction EXACTLY (same decks file, same prefs file,
 * same seed, same starting-seat rule, same ws205-pilot-v1 selection semantics
 * ported verbatim) in a fresh JVM, capturing per decision:</p>
 * <ul>
 *   <li>native pre-projection option SET + order ({@code decision.legal_options});</li>
 *   <li>projected post-projection SET + order ({@code actions});</li>
 *   <li>semantic state fingerprint (turn/phase/step, active player, life,
 *       battlefield, stack, mana, command/exile zones, prior selections);</li>
 *   <li>DIAGNOSTIC-ONLY hidden-state capture (hand name multisets, library
 *       order hash): recorded to the trace file, NEVER supplied to the pilot.
 *       The pilot reads only {@code legal}/{@code pending}, exactly as WS205.</li>
 * </ul>
 *
 * <p>Capture order per iteration is proposal-FIRST, fingerprint-AFTER, so the
 * fingerprint code provably cannot influence selection. All fingerprint access
 * is read-only against a quiescent engine thread (blocked awaiting response).</p>
 */
public final class Ws208TraceDriver {

    private static final String PILOT_POLICY = "ws205-pilot-v1";
    private static final String DRIVER_VERSION = "ws208-trace-v1";

    private static int lastMatchIndex = -1;

    private Ws208TraceDriver() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> argv = parseArgs(args);
        String decksFile = required(argv, "decks");
        String prefsFile = required(argv, "prefs");
        long seed = Long.parseLong(required(argv, "seed"));
        int budget = Integer.parseInt(argv.getOrDefault("budget", "500"));
        Path outFile = Path.of(required(argv, "out"));
        String construction = argv.getOrDefault("construction", "unknown");

        JsonObject prefs = JsonParser.parseString(
                Files.readString(Path.of(prefsFile), StandardCharsets.UTF_8)).getAsJsonObject();
        boolean twin = "twin".equals(argv.getOrDefault("mode", "wish"));
        List<StreamEntry> stream = null;
        if (twin) {
            stream = readStream(Path.of(required(argv, "stream")));
        }

        SessionHandles handles = startSession(
                "ws208-" + construction + "-rep" + argv.getOrDefault("rep", "0"),
                Path.of(decksFile),
                (int) (Math.floorMod(seed, 4)),
                seed,
                probeShuffle());

        CommanderFreeForAll game = field(handles.session, "game", CommanderFreeForAll.class);
        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> players =
                (List<XmageFullGamePlayer>) field(handles.session, "players", List.class);

        List<JsonObject> records = new ArrayList<>();
        Map<String, Integer> classCounts = new LinkedHashMap<>();
        String stoppedBy = "budget";
        String stopDetail = "";
        int answered = 0;
        int streamCursor = 0;
        boolean streamDiverged = false;
        String streamDivergenceDetail = "";
        Map<Integer, Integer> landsPlayed = new LinkedHashMap<>();

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

            // 1. Selection FIRST (pilot sees only legal/pending — identical to WS205).
            lastMatchIndex = -1;
            JsonObject proposal;
            String selectionBasis;
            if (twin && stream != null) {
                TwinPick twinPick = pickTwinAction(legal, pending, stream, streamCursor);
                if (twinPick == null || twinPick.diverged) {
                    streamDiverged = true;
                    streamDivergenceDetail = twinPick == null
                            ? "stream exhausted at offset " + offset
                            : twinPick.detail;
                    stoppedBy = "twin_diverged";
                    stopDetail = streamDivergenceDetail;
                    // Record the divergent decision itself (offers + state) before stopping.
                    JsonObject divRecord = new JsonObject();
                    divRecord.addProperty("offset", offset);
                    divRecord.addProperty("class", decisionClass);
                    divRecord.addProperty("actor_seat", seat);
                    divRecord.addProperty("prompt", pending.has("prompt") && !pending.get("prompt").isJsonNull()
                            ? pending.get("prompt").getAsString() : "");
                    divRecord.add("native_options", summarizeNative(pending));
                    divRecord.add("projected_actions", summarizeProjected(legal));
                    divRecord.add("state", captureFingerprint(game, players));
                    divRecord.addProperty("selected_label", "");
                    divRecord.addProperty("selection_basis", "twin_diverged");
                    divRecord.addProperty("expected_label",
                            streamCursor < stream.size() ? stream.get(streamCursor).selectedLabel : "");
                    records.add(divRecord);
                    break;
                }
                proposal = twinPick.proposal;
                selectionBasis = "twin_stream:" + twinPick.matchedLabel;
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
            String submittedLabel = pendingLabelForAction(pending, submittedActionId);

            // 2. Fingerprint AFTER selection, BEFORE submit (engine quiescent).
            JsonObject fingerprint = captureFingerprint(game, players);

            // 3. Submit (native execution).
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
            record.addProperty("prompt", pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    ? pending.get("prompt").getAsString() : "");
            record.add("native_options", summarizeNative(pending));
            record.add("projected_actions", summarizeProjected(legal));
            record.add("state", fingerprint);
            record.addProperty("selected_label", submittedLabel == null ? "" : submittedLabel);
            record.addProperty("selection_basis", selectionBasis);
            if (proposal.has("choices") && proposal.getAsJsonObject("choices").has("numeric_choice")
                    && !proposal.getAsJsonObject("choices").get("numeric_choice").isJsonNull()) {
                record.addProperty("numeric_choice",
                        proposal.getAsJsonObject("choices").get("numeric_choice").getAsInt());
            }
            records.add(record);
        }

        JsonObject out = new JsonObject();
        out.addProperty("schema", "ws208.layered-trace.v1");
        out.addProperty("construction", construction);
        out.addProperty("driver_version", DRIVER_VERSION);
        out.addProperty("pilot_policy", twin ? PILOT_POLICY + "-twin" : PILOT_POLICY);
        out.addProperty("seed", seed);
        out.addProperty("starting_seat", (int) (Math.floorMod(seed, 4)));
        out.addProperty("budget", budget);
        out.addProperty("stopped_by", stoppedBy);
        out.addProperty("stop_detail", stopDetail);
        out.addProperty("decisions_answered", answered);
        out.addProperty("stream_diverged", streamDiverged);
        out.addProperty("stream_divergence_detail", streamDivergenceDetail);
        out.addProperty("stream_entries_followed", streamCursor);
        out.add("rng_probes", handles.rngProbes);
        JsonObject counts = new JsonObject();
        classCounts.forEach(counts::addProperty);
        out.add("observed_decision_counts", counts);
        JsonArray trace = new JsonArray();
        records.forEach(trace::add);
        out.add("decisions", trace);
        try {
            out.add("terminal_state", captureFingerprint(game, players));
        } catch (Exception exc) {
            out.addProperty("terminal_state_failed", String.valueOf(exc.getMessage()));
        }
        Files.writeString(outFile,
                new GsonBuilder().setPrettyPrinting().create().toJson(out),
                StandardCharsets.UTF_8);
        System.out.println("WS208_TRACE_WRITTEN " + outFile + " answered=" + answered
                + " stopped_by=" + stoppedBy);
        System.exit(0);
    }

    // ------------------------------------------------------------------
    // Layered capture.
    // ------------------------------------------------------------------

    /** Native pre-projection options: label + type + source + exact order. */
    private static JsonArray summarizeNative(JsonObject pending) {
        JsonArray out = new JsonArray();
        JsonArray options = pending.has("legal_options") && pending.get("legal_options").isJsonArray()
                ? pending.getAsJsonArray("legal_options") : new JsonArray();
        int index = 0;
        for (JsonElement element : options) {
            JsonObject option = element.getAsJsonObject();
            JsonObject row = new JsonObject();
            row.addProperty("order", index++);
            row.addProperty("label", option.has("label") && !option.get("label").isJsonNull()
                    ? option.get("label").getAsString() : "");
            row.addProperty("option_type", option.has("option_type") && !option.get("option_type").isJsonNull()
                    ? option.get("option_type").getAsString() : "generic");
            JsonObject metadata = option.has("metadata") && option.get("metadata").isJsonObject()
                    ? option.getAsJsonObject("metadata") : new JsonObject();
            String sourceName = metadata.has("source_name") && !metadata.get("source_name").isJsonNull()
                    ? metadata.get("source_name").getAsString() : "";
            row.addProperty("source_name", sourceName);
            String abilityType = metadata.has("ability_type") && !metadata.get("ability_type").isJsonNull()
                    ? metadata.get("ability_type").getAsString() : "";
            row.addProperty("ability_type", abilityType);
            out.add(row);
        }
        return out;
    }

    /** Projected post-projection actions: label + type + exact order. */
    private static JsonArray summarizeProjected(JsonObject legal) {
        JsonArray out = new JsonArray();
        JsonArray actions = legal.has("actions") && legal.get("actions").isJsonArray()
                ? legal.getAsJsonArray("actions") : new JsonArray();
        int index = 0;
        for (JsonElement element : actions) {
            JsonObject action = element.getAsJsonObject();
            JsonObject row = new JsonObject();
            row.addProperty("order", index++);
            row.addProperty("action_type", action.has("action_type") && !action.get("action_type").isJsonNull()
                    ? action.get("action_type").getAsString() : "");
            JsonObject metadata = action.has("metadata") && action.get("metadata").isJsonObject()
                    ? action.getAsJsonObject("metadata") : new JsonObject();
            row.addProperty("label", metadata.has("label") && !metadata.get("label").isJsonNull()
                    ? metadata.get("label").getAsString() : "");
            row.addProperty("option_type", metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "");
            out.add(row);
        }
        return out;
    }

    /**
     * Semantic state fingerprint + DIAGNOSTIC-ONLY hidden-state capture.
     * Hand name multisets and the library order hash are recorded for
     * causality analysis only and are never supplied to the pilot.
     */
    private static JsonObject captureFingerprint(Game game, List<XmageFullGamePlayer> players) {
        JsonObject fp = new JsonObject();
        try {
            fp.addProperty("turn", game.getTurnNum());
        } catch (RuntimeException exc) {
            fp.addProperty("turn", -1);
        }
        try {
            fp.addProperty("phase", game.getPhase() == null || game.getPhase().getType() == null
                    ? "<null>" : game.getPhase().getType().name());
        } catch (RuntimeException exc) {
            fp.addProperty("phase", "<failed>");
        }
        try {
            fp.addProperty("step", game.getStep() == null || game.getStep().getType() == null
                    ? "<null>" : game.getStep().getType().name());
        } catch (RuntimeException exc) {
            fp.addProperty("step", "<failed>");
        }
        Map<String, Integer> controllerToSeat = new LinkedHashMap<>();
        for (int index = 0; index < players.size(); index++) {
            controllerToSeat.put(players.get(index).getId().toString(), index);
        }
        try {
            String activeId = game.getActivePlayerId() == null
                    ? "" : game.getActivePlayerId().toString();
            fp.addProperty("active_seat",
                    controllerToSeat.getOrDefault(activeId, -1));
        } catch (RuntimeException exc) {
            fp.addProperty("active_seat", -999);
        }

        JsonArray seats = new JsonArray();
        for (int index = 0; index < players.size(); index++) {
            XmageFullGamePlayer player = players.get(index);
            JsonObject row = new JsonObject();
            row.addProperty("seat", index);
            try {
                row.addProperty("life", player.getLife());
            } catch (RuntimeException exc) {
                row.addProperty("life", -999);
            }
            try {
                List<String> hand = new ArrayList<>();
                for (Card card : player.getHand().getCards(game)) {
                    hand.add(card == null ? "<null>" : card.getName());
                }
                hand.sort(String::compareTo);
                JsonArray handJson = new JsonArray();
                hand.forEach(handJson::add);
                // DIAGNOSTIC ONLY — never pilot input.
                row.add("diagnostic_hand_names", handJson);
                row.addProperty("hand_size", player.getHand().size());
            } catch (RuntimeException exc) {
                row.addProperty("hand_failed", String.valueOf(exc.getMessage()));
            }
            try {
                row.addProperty("library_size", player.getLibrary().size());
                List<String> libOrder = new ArrayList<>();
                for (java.util.UUID cardId : player.getLibrary().getCardList()) {
                    Card card = game.getCard(cardId);
                    libOrder.add(card == null ? "<null>" : card.getName());
                }
                // DIAGNOSTIC ONLY — library order hash, names only, no ids.
                row.addProperty("diagnostic_library_order_hash", sha256(String.join("\n", libOrder)));
                row.addProperty("diagnostic_library_top3",
                        String.join("|", libOrder.subList(0, Math.min(3, libOrder.size()))));
            } catch (RuntimeException exc) {
                row.addProperty("library_failed", String.valueOf(exc.getMessage()));
            }
            try {
                List<String> grave = new ArrayList<>();
                for (Card card : player.getGraveyard().getCards(game)) {
                    grave.add(card == null ? "<null>" : card.getName());
                }
                grave.sort(String::compareTo);
                JsonArray graveJson = new JsonArray();
                grave.forEach(graveJson::add);
                row.add("graveyard_names", graveJson);
            } catch (RuntimeException exc) {
                row.addProperty("graveyard_failed", String.valueOf(exc.getMessage()));
            }
            try {
                JsonObject mana = new JsonObject();
                for (ManaType type : ManaType.getTrueManaTypes()) {
                    mana.addProperty(type.name(), player.getManaPool().get(type));
                }
                row.add("mana_pool", mana);
            } catch (RuntimeException exc) {
                row.addProperty("mana_failed", String.valueOf(exc.getMessage()));
            }
            seats.add(row);
        }
        fp.add("seats", seats);

        try {
            List<JsonObject> permanents = new ArrayList<>();
            for (Permanent permanent : game.getBattlefield().getAllPermanents()) {
                JsonObject row = new JsonObject();
                try {
                    row.addProperty("name", permanent.getName());
                } catch (RuntimeException exc) {
                    row.addProperty("name", "<unknown>");
                }
                try {
                    Integer seat = controllerToSeat.get(permanent.getControllerId().toString());
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
            }
            permanents.sort((a, b) -> {
                int c = a.get("name").getAsString().compareTo(b.get("name").getAsString());
                if (c != 0) {
                    return c;
                }
                c = Integer.compare(a.get("controller_seat").getAsInt(),
                        b.get("controller_seat").getAsInt());
                if (c != 0) {
                    return c;
                }
                c = Integer.compare(a.get("power").getAsInt(), b.get("power").getAsInt());
                if (c != 0) {
                    return c;
                }
                return Integer.compare(a.get("toughness").getAsInt(), b.get("toughness").getAsInt());
            });
            JsonArray board = new JsonArray();
            permanents.forEach(board::add);
            fp.add("battlefield", board);
        } catch (RuntimeException exc) {
            fp.addProperty("battlefield_failed", String.valueOf(exc.getMessage()));
        }

        try {
            JsonArray stack = new JsonArray();
            for (StackObject object : game.getStack()) {
                JsonObject row = new JsonObject();
                try {
                    row.addProperty("name", object.getName());
                } catch (RuntimeException exc) {
                    row.addProperty("name", "<unknown>");
                }
                try {
                    Integer seat = controllerToSeat.get(object.getControllerId().toString());
                    row.addProperty("controller_seat", seat == null ? -1 : seat);
                } catch (RuntimeException exc) {
                    row.addProperty("controller_seat", -1);
                }
                stack.add(row);
            }
            fp.add("stack", stack);
        } catch (RuntimeException exc) {
            fp.addProperty("stack_failed", String.valueOf(exc.getMessage()));
        }

        try {
            List<String> command = new ArrayList<>();
            for (Object object : game.getState().getCommand()) {
                if (object instanceof MageObject mageObject) {
                    command.add(mageObject.getName());
                } else if (object != null) {
                    command.add(object.getClass().getSimpleName());
                }
            }
            command.sort(String::compareTo);
            JsonArray commandJson = new JsonArray();
            command.forEach(commandJson::add);
            fp.add("command_zone", commandJson);
        } catch (RuntimeException exc) {
            fp.addProperty("command_failed", String.valueOf(exc.getMessage()));
        }

        try {
            List<String> exile = new ArrayList<>();
            for (Card card : game.getExile().getAllCards(game)) {
                exile.add(card == null ? "<null>" : card.getName());
            }
            exile.sort(String::compareTo);
            JsonArray exileJson = new JsonArray();
            exile.forEach(exileJson::add);
            fp.add("exile_names", exileJson);
        } catch (RuntimeException exc) {
            fp.addProperty("exile_failed", String.valueOf(exc.getMessage()));
        }
        return fp;
    }

    private static String sha256(String text) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            digest.update(text.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest.digest());
        } catch (java.security.NoSuchAlgorithmException exc) {
            throw new IllegalStateException("SHA-256 unavailable", exc);
        }
    }

    // ------------------------------------------------------------------
    // Session bootstrap (mirrors WS205: deck import, seed, starting seat).
    // ------------------------------------------------------------------

    private record SessionHandles(XmageFullGameSession session, String deckId,
                                  List<String> handles, JsonObject rngProbes) {
    }

    /**
     * RNG/input-order discriminating probes (diagnostics-only, identical code in
     * every run so cross-JVM comparison stays valid; probe consumption itself is
     * deterministic and equal in all runs).
     *
     * <p>P0: reference shuffle before session construction (pre-seed stream).
     * P1: reference shuffle after construction = after RandomUtil.setSeed plus
     * deck import/game construction. Deck/library input order captured before
     * start. P2: reference shuffle after start() returns (setup consumption
     * complete, engine quiescent at first decision).</p>
     */
    private static String probeShuffle() {
        List<Integer> ints = new ArrayList<>(100);
        for (int i = 0; i < 100; i++) {
            ints.add(i);
        }
        java.util.Collections.shuffle(ints, mage.util.RandomUtil.getRandom());
        return sha256(ints.toString());
    }

    private static JsonObject captureDeckOrder(XmageDeckImporter importer, List<String> handles) {
        JsonObject out = new JsonObject();
        for (int seat = 0; seat < handles.size(); seat++) {
            try {
                List<String> names = new ArrayList<>();
                for (Card card : importer.requireDeck(handles.get(seat)).getCards()) {
                    names.add(card == null ? "<null>" : card.getName());
                }
                out.addProperty("seat" + seat + "_deck_set_order_hash",
                        sha256(String.join("\n", names)));
                out.addProperty("seat" + seat + "_deck_set_size", names.size());
            } catch (RuntimeException exc) {
                out.addProperty("seat" + seat + "_deck_failed", String.valueOf(exc.getMessage()));
            }
        }
        return out;
    }

    private static JsonObject capturePreStartLibraries(
            CommanderFreeForAll game, List<XmageFullGamePlayer> players) {
        JsonObject out = new JsonObject();
        for (int index = 0; index < players.size(); index++) {
            try {
                List<String> names = new ArrayList<>();
                for (java.util.UUID cardId : players.get(index).getLibrary().getCardList()) {
                    Card card = game.getCard(cardId);
                    names.add(card == null ? "<null>" : card.getName());
                }
                out.addProperty("seat" + index + "_pre_start_library_hash",
                        sha256(String.join("\n", names)));
                out.addProperty("seat" + index + "_pre_start_library_size", names.size());
            } catch (RuntimeException exc) {
                out.addProperty("seat" + index + "_pre_start_library_failed",
                        String.valueOf(exc.getMessage()));
            }
        }
        return out;
    }

    private static SessionHandles startSession(
            String gameId, Path decksFile, int startingSeat, long seed,
            String p0Probe) throws Exception {
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
        JsonObject probes = new JsonObject();
        probes.addProperty("P0_pre_construction", p0Probe);
        // P0 already captured by caller pre-construction; P1 post-seed/construction.
        probes.addProperty("P1_post_construction", probeShuffle());
        try {
            CommanderFreeForAll preGame = field(session, "game", CommanderFreeForAll.class);
            @SuppressWarnings("unchecked")
            List<XmageFullGamePlayer> prePlayers =
                    (List<XmageFullGamePlayer>) field(session, "players", List.class);
            probes.add("deck_set_order", captureDeckOrder(importer, handles));
            probes.add("pre_start_libraries", capturePreStartLibraries(preGame, prePlayers));
        } catch (Exception exc) {
            probes.addProperty("pre_start_capture_failed", String.valueOf(exc.getMessage()));
        }
        session.start();
        probes.addProperty("P2_post_start", probeShuffle());
        return new SessionHandles(session, deckId, handles, probes);
    }

    // ------------------------------------------------------------------
    // Pilot ws205-pilot-v1 (verbatim port of WS205 selection semantics).
    // ------------------------------------------------------------------

    private record WishPick(JsonObject proposal, String basis) {
    }

    private record TwinPick(JsonObject proposal, String matchedLabel,
                            boolean diverged, String detail) {
    }

    private record StreamEntry(long offset, String decisionClass,
                               String selectedLabel, Integer numericChoice) {
    }

    /** Exact-label twin replay (verbatim WS205 semantics). */
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
        JsonObject proposal = toProposal(legal, pending, hit, PILOT_POLICY + "-twin");
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
            if (best == null) {
                best = action;
                bestIndex = index;
            }
        }
        lastMatchIndex = bestIndex;
        return best;
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

    private static WishPick pickWishAction(
            JsonObject legal, JsonObject pending, JsonObject prefs,
            Map<Integer, Integer> landsPlayed) {
        String decisionClass = pending.get("decision_class").getAsString();
        int seat = pending.get("seat").getAsInt();
        JsonObject classPrefs = prefs.has(decisionClass) && prefs.get(decisionClass).isJsonObject()
                ? prefs.getAsJsonObject(decisionClass) : new JsonObject();
        List<String> wishes = stringsOrEmpty(classPrefs, String.valueOf(seat));
        if (wishes.isEmpty()) {
            wishes = stringsOrEmpty(classPrefs, "ALL");
        }
        for (String wish : wishes) {
            JsonObject hit = matchWish(legal, pending, wish);
            if (hit != null) {
                JsonObject proposal = toProposal(legal, pending, hit, PILOT_POLICY);
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
        return new WishPick(fallback, "neutral");
    }

    private static JsonObject neutralProposal(
            JsonObject legal, JsonObject pending, JsonObject prefs) {
        String decisionClass = pending.get("decision_class").getAsString();
        JsonArray actions = legal.getAsJsonArray("actions");
        return switch (decisionClass) {
            case "mulligan" -> {
                JsonObject keep = actionOfOptionType(legal, "keep");
                yield keep == null ? null
                        : baseProposal("ws205-mulligan-keep", legal.get("actor_id").getAsString(),
                                keep.get("action_id").getAsString(),
                                keep.get("action_type").getAsString(), pending);
            }
            case "priority" -> {
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
                yield baseProposal("ws205-priority", legal.get("actor_id").getAsString(),
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
                        : baseProposal("ws205-attacker", legal.get("actor_id").getAsString(),
                                chosen.get("action_id").getAsString(),
                                chosen.get("action_type").getAsString(), pending);
            }
            case "declare_blocker" -> {
                JsonObject empty = new JsonObject();
                empty.addProperty("proposal_id", "ws205-block-empty");
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
                        : baseProposal("ws205-mana", legal.get("actor_id").getAsString(),
                                chosen.get("action_id").getAsString(),
                                chosen.get("action_type").getAsString(), pending);
            }
            case "choose_object", "target", "target_amount", "choose_use", "choice",
                    "pile", "replacement_effect", "trigger_order", "mode" -> {
                JsonObject first = smallestAction(legal);
                yield first == null ? null
                        : withNumericDefault(baseProposal("ws205-" + decisionClass,
                                legal.get("actor_id").getAsString(),
                                first.get("action_id").getAsString(),
                                first.get("action_type").getAsString(), pending), pending);
            }
            case "announce_x", "amount", "multi_amount" -> {
                if (actions.size() != 1) {
                    yield null;
                }
                JsonObject numeric = actions.get(0).getAsJsonObject();
                yield withNumericDefault(baseProposal("ws205-numeric",
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
            proposal.getAsJsonObject("choices").addProperty(
                    "numeric_choice", context.get("numeric_min").getAsInt());
        }
        return proposal;
    }

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
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", PILOT_POLICY);
        return proposal;
    }

    // ------------------------------------------------------------------
    // Small utilities.
    // ------------------------------------------------------------------

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

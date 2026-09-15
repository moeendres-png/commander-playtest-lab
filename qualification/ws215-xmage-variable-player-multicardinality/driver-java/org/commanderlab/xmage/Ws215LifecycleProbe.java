package org.commanderlab.xmage;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * WS215 bounded-lifecycle probe (qualification-only, fresh JVM per run).
 *
 * <p>Drives the production {@code XmageFullGameSession} for N players through
 * a bounded native lifecycle with neutral/press answers issued only through
 * the production generic boundary, then emits a JSON summary: cardinality,
 * seed binding, decision classes/actors, defender partition, hidden-info
 * structural verdicts, turn progression, and a stable decision-row transcript
 * hash (no native UUIDs or free text) for fresh-process twin comparison.</p>
 */
public final class Ws215LifecycleProbe {

    private static final List<JsonObject> MANA_DEBUG_SAMPLES = new ArrayList<>();
    private static final Map<String, Integer> MULLIGANS_TAKEN = new HashMap<>();
    private static final Set<String> BASIC_LANDS = Set.of(
            "Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
            "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
            "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes");
    private static String lastSubmission = "";

    private Ws215LifecycleProbe() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> options = parseArgs(args);
        int players = Integer.parseInt(require(options, "players"));
        long seed = Long.parseLong(require(options, "seed"));
        int budget = Integer.parseInt(options.getOrDefault("budget", "150"));
        String mode = options.getOrDefault("mode", "neutral");
        String repoRoot = require(options, "repoRoot");
        String out = require(options, "out");
        String deckName = options.getOrDefault("deck", "rogshai");

        XmageDeckImporter importer = new XmageDeckImporter();
        RuntimeDeck deck = "lions".equals(deckName)
                ? loadLionsTechnicalDeck(repoRoot)
                : loadRogShaiRuntimeDeck(repoRoot);
        List<String> handles = new ArrayList<>(players);
        for (int copy = 0; copy < players; copy++) {
            handles.add(importer.importCommanderDeck(
                    deck.deckId(), deck.deckHash(), deck.mainboard(), deck.commanders()
            ).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                "ws215-probe-" + players + "p-" + seed + "-" + mode,
                handles,
                (int) Math.floorMod(seed, players),
                40,
                seed,
                importer
        );
        session.start();

        Set<String> classes = new TreeSet<>();
        Map<String, Integer> classCounts = new LinkedHashMap<>();
        Set<String> priorityActors = new TreeSet<>();
        Set<String> allActors = new TreeSet<>();
        Set<String> defenders = new TreeSet<>();
        Map<String, Integer> defenderAttackFrames = new LinkedHashMap<>();
        boolean triggerOrderSeen = false;
        boolean extraTurnSignalSeen = false;
        int mulligans = 0;
        int maxTurn = 1;
        int hiddenViolations = 0;
        int decisions = 0;
        int startingSeat = -1;
        int outcomeCount = -1;
        String failure = null;
        List<String> firstClasses = new ArrayList<>();

        for (int step = 0; step < budget; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (!payload.get("failure").isJsonNull()) {
                failure = payload.get("failure").toString();
                break;
            }
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            String decisionClass = pending.get("decision_class").getAsString();
            String actor = pending.get("actor_id").getAsString();
            classes.add(decisionClass);
            classCounts.merge(decisionClass, 1, Integer::sum);
            allActors.add(actor);
            if (firstClasses.size() < 12) {
                firstClasses.add(decisionClass + ":" + pending.get("decision_offset").getAsLong());
            }
            if ("priority".equals(decisionClass)) {
                priorityActors.add(actor);
            }
            if ("mulligan".equals(decisionClass)) {
                mulligans++;
            }
            if ("trigger_order".equals(decisionClass)) {
                triggerOrderSeen = true;
            }
            if ("declare_attacker".equals(decisionClass)) {
                collectDefenders(pending, defenders, defenderAttackFrames);
            }
            String prompt = pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    ? pending.get("prompt").getAsString().toLowerCase() : "";
            if (prompt.contains("extra turn") || prompt.contains("take an additional turn")
                    || prompt.contains("additional turn")) {
                extraTurnSignalSeen = true;
            }
            startingSeat = payload.get("starting_player_seat").getAsInt();
            outcomeCount = payload.getAsJsonArray("outcomes").size();
            maxTurn = Math.max(maxTurn, payload.get("turn_number").getAsInt());
            hiddenViolations += checkActorScoping(pending);
            answer(session, pending, mode);
            decisions++;
        }

        JsonObject binding = session.rulesSeedBindingPayload();
        JsonObject tail = session.pendingDecisionPayload();
        if (!tail.get("failure").isJsonNull()) {
            failure = tail.get("failure").toString();
        }
        JsonObject resultLike = session.resultPayload();
        String transcriptHash = stableTranscriptHash(resultLike.getAsJsonArray("transcript"));
        Files.writeString(
                Path.of(out).resolveSibling("transcript_canonical.txt"),
                stableTranscriptCanonical(resultLike.getAsJsonArray("transcript"), true),
                StandardCharsets.UTF_8);

        JsonObject summary = new JsonObject();
        summary.addProperty("probe", "ws215-lifecycle-probe-1.0.0");
        summary.addProperty("players", players);
        summary.addProperty("seed", seed);
        summary.addProperty("mode", mode);
        summary.addProperty("budget", budget);
        summary.addProperty("player_count", tail.get("player_count").getAsInt());
        summary.addProperty("starting_player_seat", startingSeat);
        summary.addProperty("expected_starting_seat", Math.floorMod(seed, players));
        summary.addProperty("decisions", decisions);
        JsonArray classArray = new JsonArray();
        classes.forEach(classArray::add);
        summary.add("decision_classes", classArray);
        JsonObject counts = new JsonObject();
        classCounts.forEach(counts::addProperty);
        summary.add("decision_class_counts", counts);
        JsonArray actorArray = new JsonArray();
        allActors.forEach(actorArray::add);
        summary.add("distinct_actors", actorArray);
        JsonArray prioArray = new JsonArray();
        priorityActors.forEach(prioArray::add);
        summary.add("priority_actors", prioArray);
        JsonArray defenderArray = new JsonArray();
        defenders.forEach(defenderArray::add);
        summary.add("distinct_defenders", defenderArray);
        JsonObject defenderFrames = new JsonObject();
        defenderAttackFrames.forEach(defenderFrames::addProperty);
        summary.add("defender_attack_frames", defenderFrames);
        JsonArray manaDebug = new JsonArray();
        MANA_DEBUG_SAMPLES.forEach(manaDebug::add);
        summary.add("mana_debug", manaDebug);
        summary.addProperty("last_submission", lastSubmission);
        summary.addProperty("trigger_order_seen", triggerOrderSeen);
        summary.addProperty("extra_turn_signal_seen", extraTurnSignalSeen);
        summary.addProperty("mulligans_answered", mulligans);
        summary.addProperty("max_turn", maxTurn);
        summary.add("rules_seed_binding", binding);
        summary.addProperty("outcome_count", outcomeCount);
        summary.addProperty("hidden_violations", hiddenViolations);
        summary.addProperty("transcript_hash", transcriptHash);
        JsonArray firstArray = new JsonArray();
        firstClasses.forEach(firstArray::add);
        summary.add("first_decision_frames", firstArray);
        summary.addProperty("failed", failure != null);
        summary.addProperty("failure_message", failure == null ? "" : failure);

        Gson gson = new GsonBuilder().setPrettyPrinting().create();
        Files.writeString(Path.of(out), gson.toJson(summary), StandardCharsets.UTF_8);
        System.out.println("WS215_PROBE players=" + players + " seed=" + seed + " mode=" + mode
                + " decisions=" + decisions + " hash=" + transcriptHash);
    }

    private static void collectDefenders(
            JsonObject pending, Set<String> defenders, Map<String, Integer> frames) {
        JsonElement options = pending.get("legal_options");
        if (options == null || !options.isJsonArray()) {
            return;
        }
        for (JsonElement element : options.getAsJsonArray()) {
            JsonObject option = element.getAsJsonObject();
            if (!"declare_attacker".equals(option.get("option_type").getAsString())) {
                continue;
            }
            JsonObject metadata = option.getAsJsonObject("metadata");
            if (metadata != null && metadata.has("defender_id")
                    && !metadata.get("defender_id").isJsonNull()) {
                String defender = metadata.get("defender_id").getAsString();
                defenders.add(defender);
                frames.merge(defender, 1, Integer::sum);
            }
        }
    }

    private static int checkActorScoping(JsonObject pending) {
        int violations = 0;
        JsonObject pilotState = pending.getAsJsonObject("pilot_state");
        String actorId = pending.get("actor_id").getAsString();
        for (JsonElement element : pilotState.getAsJsonArray("players")) {
            JsonObject entry = element.getAsJsonObject();
            boolean isActor = entry.get("is_actor").getAsBoolean();
            if (isActor) {
                if (!actorId.equals(entry.get("player_id").getAsString())) {
                    violations++;
                }
                if (!entry.has("hand") || !entry.has("mana_pool")) {
                    violations++;
                }
            } else if (entry.has("hand") || entry.has("mana_pool")) {
                violations++;
            }
        }
        return violations;
    }

    private static void answer(
            XmageFullGameSession session, JsonObject pending, String mode) {
        String decisionClass = pending.get("decision_class").getAsString();
        JsonObject legal = session.legalActionsPayload();
        String actor = legal.get("actor_id").getAsString();
        JsonArray actions = legal.getAsJsonArray("actions");
        if (actions.size() == 0) {
            return;
        }
        if ("mulligan".equals(decisionClass)) {
            // Develop mulligan discipline (deterministic, content-based): take
            // exactly one mulligan on an extreme opener (no lands or all
            // lands), then keep. This exercises the London bottom flow and the
            // free-first-mulligan path natively. Neutral mode always keeps.
            if ("develop".equals(mode)) {
                int taken = MULLIGANS_TAKEN.getOrDefault(actor, 0);
                if (taken == 0 && isExtremeOpener(pending)) {
                    for (JsonElement element : actions) {
                        JsonObject action = element.getAsJsonObject();
                        if ("mulligan".equals(action.getAsJsonObject("metadata")
                                .get("option_type").getAsString())) {
                            MULLIGANS_TAKEN.put(actor, 1);
                            submitTracked(session, genericProposal(
                                    "ws215-probe", actor,
                                    action.get("action_id").getAsString(), "mulligan"));
                            return;
                        }
                    }
                }
            }
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                if ("keep".equals(action.getAsJsonObject("metadata")
                        .get("option_type").getAsString())) {
                    submitTracked(session, genericProposal(
                            "ws215-probe", actor,
                            action.get("action_id").getAsString(), "mulligan"));
                    return;
                }
            }
        }
        if ("choose_object".equals(decisionClass) && isLondonBottom(pending)) {
            // London mulligan bottom-N: deterministic stable-content choice of
            // exactly the required number of OFFERED option ids.
            int need = pending.has("minimum_selections")
                    && !pending.get("minimum_selections").isJsonNull()
                    ? pending.get("minimum_selections").getAsInt() : 0;
            List<JsonObject> ranked = new ArrayList<>();
            for (JsonElement element : actions) {
                ranked.add(element.getAsJsonObject());
            }
            ranked.sort(Comparator.comparing(Ws215LifecycleProbe::stableActionKey));
            JsonArray selected = new JsonArray();
            for (int index = 0; index < Math.min(need, ranked.size()); index++) {
                JsonObject meta = ranked.get(index).getAsJsonObject("metadata");
                if (meta != null && meta.has("option_id") && !meta.get("option_id").isJsonNull()) {
                    selected.add(meta.get("option_id").getAsString());
                }
            }
            JsonObject proposal = genericProposal(
                    "ws215-probe", actor, "", "structural_decision");
            if (selected.size() > 0) {
                String wanted = selected.get(0).getAsString();
                for (JsonObject candidate : ranked) {
                    JsonObject meta = candidate.getAsJsonObject("metadata");
                    if (meta != null && meta.has("option_id")
                            && !meta.get("option_id").isJsonNull()
                            && wanted.equals(meta.get("option_id").getAsString())) {
                        proposal.addProperty(
                                "legal_action_id", candidate.get("action_id").getAsString());
                        proposal.addProperty(
                                "action_type", candidate.get("action_type").getAsString());
                        break;
                    }
                }
            }
            JsonObject choices = new JsonObject();
            choices.add("ordering", new JsonArray());
            choices.add("selected_option_ids", selected);
            proposal.add("choices", choices);
            submitTracked(session, proposal);
            return;
        }
        if ("priority".equals(decisionClass)) {
            if ("develop".equals(mode)) {
                // Land-first development: land drops are unconditionally
                // legal; only then consider target-free, mode-free casts.
                JsonObject land = null;
                String landKey = null;
                for (JsonElement element : actions) {
                    JsonObject action = element.getAsJsonObject();
                    if (!"play_land".equals(action.get("action_type").getAsString())) {
                        continue;
                    }
                    String key = stableActionKey(action);
                    if (land == null || key.compareTo(landKey) < 0) {
                        land = action;
                        landKey = key;
                    }
                }
                if (land != null) {
                    submitTracked(session, genericProposal(
                            "ws215-probe", actor,
                            land.get("action_id").getAsString(),
                            land.get("action_type").getAsString()));
                    return;
                }
                JsonObject cast = null;
                String castKey = null;
                for (JsonElement element : actions) {
                    JsonObject action = element.getAsJsonObject();
                    if ("pass_priority".equals(action.get("action_type").getAsString())) {
                        continue;
                    }
                    JsonObject meta = action.getAsJsonObject("metadata");
                    String optionType = meta != null && meta.has("option_type")
                            && !meta.get("option_type").isJsonNull()
                            ? meta.get("option_type").getAsString() : "";
                    if ("mana_ability".equals(optionType)) {
                        continue;
                    }
                    // Develop casts only target-free, mode-free spells: the
                    // harness cannot author legal targets/modes, and executing
                    // a spell that needs them would fail natively. Engine
                    // offers only mana-validated casts, so the rest execute.
                    if (!action.getAsJsonArray("allowed_target_ids").isEmpty()
                            || !action.getAsJsonArray("modes").isEmpty()) {
                        continue;
                    }
                    String key = stableActionKey(action);
                    if (cast == null || key.compareTo(castKey) < 0) {
                        cast = action;
                        castKey = key;
                    }
                }
                if (cast != null) {
                    submitTracked(session,genericProposal(
                            "ws215-probe", actor,
                            cast.get("action_id").getAsString(),
                            cast.get("action_type").getAsString()));
                    return;
                }
            }
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                if ("pass_priority".equals(action.get("action_type").getAsString())) {
                    submitTracked(session,genericProposal(
                            "ws215-probe", actor,
                            action.get("action_id").getAsString(), "pass_priority"));
                    return;
                }
            }
        }
        if ("mana_payment".equals(decisionClass)) {
            {
                JsonObject sample = new JsonObject();
                sample.addProperty("offset", pending.get("decision_offset").getAsLong());
                JsonObject context = pending.getAsJsonObject("context");
                sample.addProperty("unpaid",
                        context != null && context.has("unpaid_mana")
                                && !context.get("unpaid_mana").isJsonNull()
                                ? context.get("unpaid_mana").getAsString() : "<none>");
                JsonArray offered = new JsonArray();
                JsonElement legalOptions = pending.get("legal_options");
                if (legalOptions != null && legalOptions.isJsonArray()) {
                    for (JsonElement element : legalOptions.getAsJsonArray()) {
                        JsonObject option = element.getAsJsonObject();
                        offered.add(option.get("option_type").getAsString() + ":"
                                + option.get("label").getAsString());
                    }
                }
                sample.add("offered", offered);
                MANA_DEBUG_SAMPLES.add(sample);
                while (MANA_DEBUG_SAMPLES.size() > 6) {
                    MANA_DEBUG_SAMPLES.remove(0);
                }
            }
            // Pool-aware deterministic mana with the WS215 liveness guard:
            // pool mana matching no unpaid colored requirement can never
            // satisfy the payment (spending it loops natively). Generic-only
            // costs take any pool mana; colored costs take an exact match;
            // otherwise tap a mana ability, else cancel cleanly.
            String unpaid = "";
            JsonObject context = pending.getAsJsonObject("context");
            if (context != null && context.has("unpaid_mana")
                    && !context.get("unpaid_mana").isJsonNull()) {
                unpaid = context.get("unpaid_mana").getAsString().toLowerCase();
            }
            boolean genericOnly = true;
            for (String symbol : new String[]{"{w}", "{u}", "{b}", "{r}", "{g}"}) {
                if (unpaid.contains(symbol)) {
                    genericOnly = false;
                }
            }
            JsonObject poolPick = null;
            String poolKey = null;
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                JsonObject meta = action.getAsJsonObject("metadata");
                if (meta == null || !meta.has("option_type")
                        || meta.get("option_type").isJsonNull()
                        || !"mana_pool".equals(meta.get("option_type").getAsString())) {
                    continue;
                }
                JsonObject optionMeta = meta.has("xmage_option_metadata")
                        && meta.get("xmage_option_metadata").isJsonObject()
                        ? meta.getAsJsonObject("xmage_option_metadata") : new JsonObject();
                String manaType = optionMeta.has("mana_type")
                        && !optionMeta.get("mana_type").isJsonNull()
                        ? optionMeta.get("mana_type").getAsString().toLowerCase() : "";
                String symbol = switch (manaType) {
                    case "white" -> "w";
                    case "blue" -> "u";
                    case "black" -> "b";
                    case "red" -> "r";
                    case "green" -> "g";
                    case "colorless" -> "c";
                    default -> "";
                };
                int exact = (!symbol.isEmpty() && unpaid.contains("{" + symbol + "}")) ? 1 : 0;
                if (!genericOnly && exact == 0) {
                    continue;
                }
                String key = exact + "|" + manaType + "|" + meta.get("label").getAsString();
                if (poolPick == null || key.compareTo(poolKey) > 0) {
                    poolPick = action;
                    poolKey = key;
                }
            }
            if (poolPick != null) {
                submitTracked(session,genericProposal(
                        "ws215-probe", actor,
                        poolPick.get("action_id").getAsString(),
                        poolPick.get("action_type").getAsString()));
                return;
            }
            JsonObject abilityPick = null;
            String abilityKey = null;
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                JsonObject meta = action.getAsJsonObject("metadata");
                if (meta == null || !meta.has("option_type")
                        || meta.get("option_type").isJsonNull()
                        || !"mana_ability".equals(meta.get("option_type").getAsString())) {
                    continue;
                }
                String key = stableActionKey(action);
                if (abilityPick == null || key.compareTo(abilityKey) < 0) {
                    abilityPick = action;
                    abilityKey = key;
                }
            }
            if (abilityPick != null) {
                submitTracked(session,genericProposal(
                        "ws215-probe", actor,
                        abilityPick.get("action_id").getAsString(),
                        abilityPick.get("action_type").getAsString()));
                return;
            }
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                JsonObject meta = action.getAsJsonObject("metadata");
                if (meta != null && meta.has("option_type")
                        && !meta.get("option_type").isJsonNull()
                        && "cancel_mana_payment".equals(
                                meta.get("option_type").getAsString())) {
                    submitTracked(session,genericProposal(
                            "ws215-probe", actor,
                            action.get("action_id").getAsString(),
                            action.get("action_type").getAsString()));
                    return;
                }
            }
        }
        if ("declare_attacker".equals(decisionClass) && ("press".equals(mode) || "develop".equals(mode))) {
            JsonObject attack = null;
            String attackKey = null;
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                JsonObject meta = action.getAsJsonObject("metadata");
                if ("declare_attackers".equals(action.get("action_type").getAsString())
                        && meta != null
                        && "declare_attacker".equals(meta.get("option_type").getAsString())) {
                    String key = stableActionKey(action);
                    if (attack == null || key.compareTo(attackKey) < 0) {
                        attack = action;
                        attackKey = key;
                    }
                }
            }
            if (attack != null) {
                submitTracked(session,genericProposal(
                        "ws215-probe", actor,
                        attack.get("action_id").getAsString(), "declare_attackers"));
                return;
            }
        }
        if ("declare_blocker".equals(decisionClass) && "develop".equals(mode)) {
            JsonObject block = null;
            String blockKey = null;
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                JsonObject meta = action.getAsJsonObject("metadata");
                if ("declare_blockers".equals(action.get("action_type").getAsString())
                        && meta != null
                        && "declare_blocker".equals(meta.get("option_type").getAsString())) {
                    String key = stableActionKey(action);
                    if (block == null || key.compareTo(blockKey) < 0) {
                        block = action;
                        blockKey = key;
                    }
                }
            }
            if (block != null) {
                submitTracked(session,genericProposal(
                        "ws215-probe", actor,
                        block.get("action_id").getAsString(), "declare_blockers"));
                return;
            }
        }
        if ("declare_attacker".equals(decisionClass)) {
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                if ("hold_attacker".equals(action.getAsJsonObject("metadata")
                        .get("option_type").getAsString())) {
                    submitTracked(session,genericProposal(
                            "ws215-probe", actor,
                            action.get("action_id").getAsString(), "declare_attackers"));
                    return;
                }
            }
        }
        // Deterministic harness fallback (reachability only): rank by stable
        // Rules-visible content (action type, label, option type, UUID-redacted
        // option metadata). Never by raw action id: it embeds per-process
        // native UUIDs, so UUID-order selection would make same-seed twins
        // diverge. Residual ties among truly identical options are harmless
        // (indistinguishable game impact).
        JsonObject first = actions.get(0).getAsJsonObject();
        String firstKey = stableActionKey(first);
        for (JsonElement element : actions) {
            JsonObject candidate = element.getAsJsonObject();
            String key = stableActionKey(candidate);
            if (key.compareTo(firstKey) < 0) {
                first = candidate;
                firstKey = key;
            }
        }
        JsonObject proposal = genericProposal(
                "ws215-probe", actor,
                first.get("action_id").getAsString(),
                first.get("action_type").getAsString());
        JsonObject context = pending.getAsJsonObject("context");
        if (context != null && context.has("numeric_min") && !context.get("numeric_min").isJsonNull()
                && ("announce_x".equals(decisionClass) || "amount".equals(decisionClass)
                        || "multi_amount".equals(decisionClass))) {
            proposal.getAsJsonObject("choices").addProperty(
                    "numeric_choice", context.get("numeric_min").getAsInt());
        }
        submitTracked(session,proposal);
    }

    private static String stableTranscriptHash(JsonArray transcript) throws Exception {
        String canonical = stableTranscriptCanonical(transcript, false);
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] hash = digest.digest(canonical.getBytes(StandardCharsets.UTF_8));
        StringBuilder hex = new StringBuilder();
        for (byte octet : hash) {
            hex.append(String.format("%02x", octet));
        }
        return hex.toString();
    }

    private static String stableTranscriptCanonical(JsonArray transcript, boolean labels) {
        StringBuilder canonical = new StringBuilder();
        if (transcript != null) {
            for (JsonElement element : transcript) {
                JsonObject event = element.getAsJsonObject();
                JsonElement kind = event.get("kind");
                if (kind == null || kind.isJsonNull()
                        || !"decision_accepted".equals(kind.getAsString())) {
                    continue;
                }
                canonical.append(event.get("sequence").getAsLong()).append('|');
                canonical.append(event.get("decision_class").getAsString()).append('|');
                canonical.append(event.get("actor_seat").getAsInt()).append('|');
                JsonElement types = event.get("selected_option_types");
                canonical.append(types == null || types.isJsonNull() ? "-" : types.toString());
                canonical.append('|');
                JsonElement numeric = event.get("numeric_choice");
                canonical.append(numeric == null || numeric.isJsonNull()
                        ? "-" : numeric.toString());
                if (labels) {
                    canonical.append('|');
                    JsonElement accepted = event.get("selected_option_labels");
                    canonical.append(accepted == null || accepted.isJsonNull()
                            ? "-" : accepted.toString());
                }
                canonical.append('\n');
            }
        }
        return canonical.toString();
    }

    private static boolean isExtremeOpener(JsonObject pending) {
        JsonObject pilotState = pending.getAsJsonObject("pilot_state");
        if (pilotState == null) {
            return false;
        }
        String actorId = pending.get("actor_id").getAsString();
        for (JsonElement element : pilotState.getAsJsonArray("players")) {
            JsonObject entry = element.getAsJsonObject();
            if (!actorId.equals(entry.get("player_id").getAsString())) {
                continue;
            }
            JsonElement hand = entry.get("hand");
            if (hand == null || !hand.isJsonArray() || hand.getAsJsonArray().size() == 0) {
                return false;
            }
            int lands = 0;
            int total = 0;
            for (JsonElement card : hand.getAsJsonArray()) {
                JsonObject item = card.getAsJsonObject();
                if (!item.has("name") || item.get("name").isJsonNull()) {
                    continue;
                }
                total++;
                if (BASIC_LANDS.contains(item.get("name").getAsString())) {
                    lands++;
                }
            }
            return total > 0 && (lands == 0 || lands == total);
        }
        return false;
    }

    private static boolean isLondonBottom(JsonObject pending) {
        JsonElement prompt = pending.get("prompt");
        if (prompt == null || !prompt.isJsonPrimitive()) {
            return false;
        }
        String text = prompt.getAsString().toLowerCase();
        return text.contains("bottom") && text.contains("library");
    }

    private static String stableActionKey(JsonObject action) {
        JsonObject meta = action.getAsJsonObject("metadata");
        String optionType = meta != null && meta.has("option_type")
                && !meta.get("option_type").isJsonNull()
                ? meta.get("option_type").getAsString() : "";
        String label = meta != null && meta.has("label") && !meta.get("label").isJsonNull()
                ? meta.get("label").getAsString() : action.get("action_id").getAsString();
        String optionMeta = meta != null && meta.has("xmage_option_metadata")
                && meta.get("xmage_option_metadata").isJsonObject()
                ? meta.getAsJsonObject("xmage_option_metadata").toString() : "";
        String key = action.get("action_type").getAsString() + "|"
                + label + "|" + optionType + "|" + optionMeta;
        return key.replaceAll(
                "(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                "#");
    }

    private static void submitTracked(XmageFullGameSession session, JsonObject proposal) {
        lastSubmission = proposal.get("action_type").getAsString() + ":"
                + proposal.get("legal_action_id").getAsString();
        session.submitAction(proposal);
    }

    private static JsonObject genericProposal(
            String proposalId, String actorId, String actionId, String actionType) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", actorId);
        proposal.addProperty("legal_action_id", actionId);
        proposal.addProperty("action_type", actionType);
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        return proposal;
    }

    private static RuntimeDeck loadLionsTechnicalDeck(String repoRoot) throws Exception {
        JsonObject root = JsonParser.parseString(
                Files.readString(
                        Path.of(repoRoot,
                                "qualification/ws215-xmage-variable-player-multicardinality/decks/ws215_lions.json")
                                .normalize(),
                        StandardCharsets.UTF_8
                )
        ).getAsJsonObject();
        return readDeckFile(root, "ws215-lions-technical");
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck(String repoRoot) throws Exception {
        JsonObject root = JsonParser.parseString(
                Files.readString(
                        Path.of(repoRoot, "data", "decks", "rogshai_current.json").normalize(),
                        StandardCharsets.UTF_8
                )
        ).getAsJsonObject();
        return readDeckFile(root, null);
    }

    private static RuntimeDeck readDeckFile(JsonObject root, String fallbackId) {
        List<String> mainboard = new ArrayList<>();
        List<String> commanders = new ArrayList<>();
        root.getAsJsonArray("cards").forEach(element -> {
            JsonObject card = element.getAsJsonObject();
            String name = card.get("oracle_name").getAsString();
            int quantity = card.get("quantity").getAsInt();
            String zone = card.get("zone").getAsString();
            List<String> target;
            if ("main".equals(zone)) {
                target = mainboard;
            } else if ("commander".equals(zone)) {
                target = commanders;
            } else {
                throw new IllegalStateException("Unexpected zone: " + zone);
            }
            for (int copy = 0; copy < quantity; copy++) {
                target.add(name);
            }
        });
        String deckId = root.has("deck_id") && !root.get("deck_id").isJsonNull()
                ? root.get("deck_id").getAsString() : fallbackId;
        String deckHash = root.has("deck_hash") && !root.get("deck_hash").isJsonNull()
                ? root.get("deck_hash").getAsString()
                : "2766b3c0e508350b33979fb8d9cef1c3d108d5217a248025cba790f9cd793e98";
        return new RuntimeDeck(deckId, deckHash, List.copyOf(mainboard), List.copyOf(commanders));
    }

    private static Map<String, String> parseArgs(String[] args) {
        Map<String, String> options = new HashMap<>();
        for (String arg : args) {
            if (arg.startsWith("--")) {
                int equals = arg.indexOf('=');
                if (equals > 2) {
                    options.put(arg.substring(2, equals), arg.substring(equals + 1));
                }
            }
        }
        return options;
    }

    private static String require(Map<String, String> options, String key) {
        String value = options.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("missing required argument: --" + key);
        }
        return value;
    }

    private record RuntimeDeck(
            String deckId,
            String deckHash,
            List<String> mainboard,
            List<String> commanders
    ) {
    }
}

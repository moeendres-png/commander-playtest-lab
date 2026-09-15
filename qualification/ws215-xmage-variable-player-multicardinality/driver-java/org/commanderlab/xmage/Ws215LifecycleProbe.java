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
    private static int oracleErrors = 0;
    private static final Map<String, Integer> MULLIGANS_TAKEN = new HashMap<>();
    private static int zoneChoiceCount = 0;
    private static final List<JsonObject> MULLIGAN_FRAMES = new ArrayList<>();
    private static boolean forceMulligan = false;
    private static String forcedMulliganActor = null;
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
        forceMulligan = Boolean.parseBoolean(options.getOrDefault("force_mulligan", "false"));

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
        Map<String, Integer> blockPairs = new LinkedHashMap<>();
        boolean triggerOrderSeen = false;
        boolean extraTurnSignalSeen = false;
        int mulligans = 0;
        int mulligansTaken = 0;
        int londonBottoms = 0;
        int maxTurn = 1;
        int maxStack = 0;
        int hiddenViolations = 0;
        int oracleFrames = 0;
        int oracleViolations = 0;
        int decisions = 0;
        int startingSeat = -1;
        int outcomeCount = -1;
        String failure = null;
        List<String> firstClasses = new ArrayList<>();
        List<JsonObject> handTraceSamples = new ArrayList<>();
        Map<String, Integer> commandZoneStart = new LinkedHashMap<>();
        Map<String, Integer> commanderCastCounts = new LinkedHashMap<>();
        Map<String, Integer> commanderDamageMax = new LinkedHashMap<>();
        JsonArray commanderFinal = new JsonArray();
        List<String> zoneChoiceFrames = new ArrayList<>();

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
                if (MULLIGAN_FRAMES.size() < 8) {
                    JsonObject frame = new JsonObject();
                    frame.addProperty("offset", pending.get("decision_offset").getAsLong());
                    JsonArray types = new JsonArray();
                    JsonElement legalOptions = pending.get("legal_options");
                    if (legalOptions != null && legalOptions.isJsonArray()) {
                        for (JsonElement element : legalOptions.getAsJsonArray()) {
                            JsonObject option = element.getAsJsonObject();
                            types.add(option.has("option_type")
                                    && !option.get("option_type").isJsonNull()
                                    ? option.get("option_type").getAsString() : "?");
                        }
                    }
                    frame.add("option_types", types);
                    frame.addProperty("min", pending.has("minimum_selections")
                            && !pending.get("minimum_selections").isJsonNull()
                            ? pending.get("minimum_selections").getAsInt() : -1);
                    frame.addProperty("max", pending.has("maximum_selections")
                            && !pending.get("maximum_selections").isJsonNull()
                            ? pending.get("maximum_selections").getAsInt() : -1);
                    MULLIGAN_FRAMES.add(frame);
                }
            }
            if ("trigger_order".equals(decisionClass)) {
                triggerOrderSeen = true;
            }
            if ("declare_attacker".equals(decisionClass)) {
                collectDefenders(pending, defenders, defenderAttackFrames);
            }
            if ("declare_blocker".equals(decisionClass)) {
                collectBlocks(pending, blockPairs);
            }
            String prompt = pending.has("prompt") && !pending.get("prompt").isJsonNull()
                    ? pending.get("prompt").getAsString().toLowerCase() : "";
            if (prompt.contains("extra turn") || prompt.contains("take an additional turn")
                    || prompt.contains("additional turn")) {
                extraTurnSignalSeen = true;
            }
            if (prompt.contains("command zone")) {
                zoneChoiceFrames.add(decisionClass + ":"
                        + pending.get("decision_offset").getAsLong() + ":" + prompt);
            }
            if (isLondonBottom(pending)) {
                londonBottoms++;
            }
            JsonObject pilotState = pending.getAsJsonObject("pilot_state");
            JsonArray stack = pilotState.has("stack") && pilotState.get("stack").isJsonArray()
                    ? pilotState.getAsJsonArray("stack") : new JsonArray();
            maxStack = Math.max(maxStack, stack.size());
            if (handTraceSamples.size() < 60) {
                handTraceSamples.add(handTraceRow(payload, pending));
            }
            if (commandZoneStart.isEmpty()) {
                snapshotCommandZone(pending, commandZoneStart);
            }
            tallyCommanderCast(pending, commanderCastCounts);
            trackCommanderDamage(pending, commanderDamageMax);
            commanderFinal = snapshotCommanderStatus(pending);
            oracleViolations += oracleScan(session, pending);
            oracleFrames++;
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
        mulligansTaken =
                MULLIGANS_TAKEN.values().stream().mapToInt(Integer::intValue).sum();
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
        JsonObject blocks = new JsonObject();
        blockPairs.forEach(blocks::addProperty);
        summary.add("block_assignments", blocks);
        JsonArray manaDebug = new JsonArray();
        MANA_DEBUG_SAMPLES.forEach(manaDebug::add);
        summary.add("mana_debug", manaDebug);
        summary.addProperty("last_submission", lastSubmission);
        summary.addProperty("trigger_order_seen", triggerOrderSeen);
        summary.addProperty("extra_turn_signal_seen", extraTurnSignalSeen);
        summary.addProperty("mulligans_answered", mulligans);
        summary.addProperty("mulligans_taken", mulligansTaken);
        summary.addProperty("london_bottom_frames", londonBottoms);
        JsonArray mulliganFrames = new JsonArray();
        MULLIGAN_FRAMES.forEach(mulliganFrames::add);
        summary.add("mulligan_frames", mulliganFrames);
        summary.addProperty("max_turn", maxTurn);
        JsonArray handTrace = new JsonArray();
        handTraceSamples.forEach(handTrace::add);
        summary.add("hand_trace", handTrace);
        JsonObject commandZone = new JsonObject();
        commandZoneStart.forEach(commandZone::addProperty);
        summary.add("command_zone_start", commandZone);
        JsonObject commanderCasts = new JsonObject();
        commanderCastCounts.forEach(commanderCasts::addProperty);
        summary.add("commander_casts", commanderCasts);
        JsonObject commanderDamage = new JsonObject();
        commanderDamageMax.forEach(commanderDamage::addProperty);
        summary.add("commander_damage_max", commanderDamage);
        summary.add("commander_final", commanderFinal);
        JsonArray zoneChoices = new JsonArray();
        zoneChoiceFrames.forEach(zoneChoices::add);
        summary.add("command_zone_choice_frames", zoneChoices);
        summary.addProperty("max_stack_observed", maxStack);
        summary.addProperty("oracle_frames_checked", oracleFrames);
        summary.addProperty("oracle_violations", oracleViolations);
        summary.addProperty("oracle_errors", oracleErrors);
        summary.add("rules_seed_binding", binding);
        summary.addProperty("outcome_count", outcomeCount);
        summary.addProperty("hidden_violations", hiddenViolations);
        summary.addProperty("transcript_hash", transcriptHash);
        JsonArray firstArray = new JsonArray();
        firstClasses.forEach(firstArray::add);
        summary.add("first_decision_frames", firstArray);
        summary.addProperty("failed", failure != null);
        summary.addProperty("failure_message", failure == null ? "" : failure);
        summary.addProperty("terminal", tail.get("terminal").getAsBoolean());
        JsonArray outcomeArray = new JsonArray();
        for (JsonElement element : tail.getAsJsonArray("outcomes")) {
            JsonObject item = element.getAsJsonObject();
            JsonObject row = new JsonObject();
            row.addProperty("seat", item.get("seat").getAsInt());
            row.addProperty("life", item.get("life").getAsInt());
            row.addProperty("won", item.get("won").getAsBoolean());
            row.addProperty("lost", item.get("lost").getAsBoolean());
            row.addProperty("left", item.get("left").getAsBoolean());
            outcomeArray.add(row);
        }
        summary.add("outcomes", outcomeArray);

        Gson gson = new GsonBuilder().setPrettyPrinting().create();
        Files.writeString(Path.of(out), gson.toJson(summary), StandardCharsets.UTF_8);
        System.out.println("WS215_PROBE players=" + players + " seed=" + seed + " mode=" + mode
                + " decisions=" + decisions + " hash=" + transcriptHash);
    }

    private static void collectBlocks(JsonObject pending, Map<String, Integer> blockPairs) {
        JsonElement options = pending.get("legal_options");
        if (options == null || !options.isJsonArray()) {
            return;
        }
        // Blocker/defender partition is observed structurally: every offered
        // block names its defender-side blocker and the attacker it answers.
        // UUIDs are process-local, so only counts and partitions are sealed
        // (counts of distinct blockers/attackers and pair multiplicities as
        // opaque tallies, never identities).
        Set<String> blockers = new java.util.HashSet<>();
        Set<String> attackers = new java.util.HashSet<>();
        int pairs = 0;
        for (JsonElement element : options.getAsJsonArray()) {
            JsonObject option = element.getAsJsonObject();
            if (!"declare_blocker".equals(option.get("option_type").getAsString())) {
                continue;
            }
            JsonObject metadata = option.getAsJsonObject("metadata");
            if (metadata == null) {
                continue;
            }
            if (metadata.has("blocker_id") && !metadata.get("blocker_id").isJsonNull()) {
                blockers.add(metadata.get("blocker_id").getAsString());
            }
            if (metadata.has("attacker_id") && !metadata.get("attacker_id").isJsonNull()) {
                attackers.add(metadata.get("attacker_id").getAsString());
            }
            pairs++;
        }
        if (pairs > 0) {
            blockPairs.merge("frames", 1, Integer::sum);
            blockPairs.merge("pairs_offered", pairs, Integer::sum);
            blockPairs.merge("max_blockers_in_frame", blockers.size(), Math::max);
            blockPairs.merge("max_attackers_in_frame", attackers.size(), Math::max);
        }
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

    private static JsonObject handTraceRow(JsonObject payload, JsonObject pending) {
        JsonObject row = new JsonObject();
        row.addProperty("turn", payload.get("turn_number").getAsInt());
        row.addProperty("offset", pending.get("decision_offset").getAsLong());
        row.addProperty("class", pending.get("decision_class").getAsString());
        JsonObject pilotState = pending.getAsJsonObject("pilot_state");
        String actorId = pending.get("actor_id").getAsString();
        for (JsonElement element : pilotState.getAsJsonArray("players")) {
            JsonObject entry = element.getAsJsonObject();
            JsonObject seat = new JsonObject();
            seat.addProperty("hand_count", entry.get("hand_count").getAsInt());
            seat.addProperty("library_count", entry.get("library_count").getAsInt());
            seat.addProperty("life", entry.get("life").getAsInt());
            seat.addProperty("is_actor", entry.get("is_actor").getAsBoolean());
            row.add("seat_" + entry.get("seat").getAsInt(), seat);
        }
        row.addProperty("starting_seat", payload.get("starting_player_seat").getAsInt());
        JsonArray commanders = new JsonArray();
        JsonElement status = pilotState.get("commander_status");
        if (status != null && status.isJsonArray()) {
            for (JsonElement element : status.getAsJsonArray()) {
                JsonObject entry = element.getAsJsonObject();
                JsonObject row2 = new JsonObject();
                row2.addProperty("name",
                        entry.has("name") && !entry.get("name").isJsonNull()
                                ? entry.get("name").getAsString() : "?");
                JsonElement casts = entry.get("casts_from_command");
                String castsText = casts == null || casts.isJsonNull() ? "-" : casts.toString();
                row2.addProperty("casts", castsText.replaceAll(
                        "(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                        "#"));
                int damage = 0;
                JsonElement damageArray = entry.get("commander_damage_to_player");
                if (damageArray != null && damageArray.isJsonArray()) {
                    for (JsonElement dealt : damageArray.getAsJsonArray()) {
                        JsonObject deal = dealt.getAsJsonObject();
                        for (Map.Entry<String, JsonElement> field : deal.entrySet()) {
                            if (field.getValue().isJsonPrimitive()
                                    && field.getValue().getAsJsonPrimitive().isNumber()) {
                                damage += field.getValue().getAsInt();
                            }
                        }
                    }
                }
                row2.addProperty("damage_dealt", damage);
                commanders.add(row2);
            }
        }
        row.add("commander_status", commanders);
        return row;
    }

    private static void snapshotCommandZone(
            JsonObject pending, Map<String, Integer> commandZoneStart) {
        JsonObject pilotState = pending.getAsJsonObject("pilot_state");
        for (JsonElement element : pilotState.getAsJsonArray("players")) {
            JsonObject entry = element.getAsJsonObject();
            JsonElement command = entry.get("command");
            int count = command != null && command.isJsonArray()
                    ? command.getAsJsonArray().size() : 0;
            commandZoneStart.put("seat_" + entry.get("seat").getAsInt(), count);
        }
    }

    private static void trackCommanderDamage(
            JsonObject pending, Map<String, Integer> commanderDamageMax) {
        JsonObject pilotState = pending.getAsJsonObject("pilot_state");
        JsonElement status = pilotState.get("commander_status");
        if (status == null || !status.isJsonArray()) {
            return;
        }
        for (JsonElement element : status.getAsJsonArray()) {
            JsonObject entry = element.getAsJsonObject();
            String name = entry.has("name") && !entry.get("name").isJsonNull()
                    ? entry.get("name").getAsString() : "?";
            int damage = sumDamage(entry.get("commander_damage_to_player"));
            commanderDamageMax.merge(name, damage, Math::max);
        }
    }

    private static JsonArray snapshotCommanderStatus(JsonObject pending) {
        JsonArray result = new JsonArray();
        JsonObject pilotState = pending.getAsJsonObject("pilot_state");
        JsonElement status = pilotState.get("commander_status");
        if (status == null || !status.isJsonArray()) {
            return result;
        }
        for (JsonElement element : status.getAsJsonArray()) {
            JsonObject entry = element.getAsJsonObject();
            JsonObject row = new JsonObject();
            row.addProperty("name",
                    entry.has("name") && !entry.get("name").isJsonNull()
                            ? entry.get("name").getAsString() : "?");
            JsonElement casts = entry.get("casts_from_command");
            String castsText = casts == null || casts.isJsonNull() ? "-" : casts.toString();
            row.addProperty("casts", castsText.replaceAll(
                    "(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                    "#"));
            row.addProperty("damage_dealt", sumDamage(entry.get("commander_damage_to_player")));
            result.add(row);
        }
        return result;
    }

    private static int sumDamage(JsonElement damageArray) {
        int damage = 0;
        if (damageArray != null && damageArray.isJsonArray()) {
            for (JsonElement dealt : damageArray.getAsJsonArray()) {
                JsonObject deal = dealt.getAsJsonObject();
                for (Map.Entry<String, JsonElement> field : deal.entrySet()) {
                    if (field.getValue().isJsonPrimitive()
                            && field.getValue().getAsJsonPrimitive().isNumber()) {
                        damage += field.getValue().getAsInt();
                    }
                }
            }
        }
        return damage;
    }

    private static void tallyCommanderCast(
            JsonObject pending, Map<String, Integer> commanderCastCounts) {
        if (!"priority".equals(pending.get("decision_class").getAsString())) {
            return;
        }
        JsonElement options = pending.get("legal_options");
        if (options == null || !options.isJsonArray()) {
            return;
        }
        // Commander casts are identified structurally: the offer is a cast
        // whose source object sits in a command zone (never by card name).
        JsonObject pilotState = pending.getAsJsonObject("pilot_state");
        Set<String> commandIds = new java.util.HashSet<>();
        for (JsonElement element : pilotState.getAsJsonArray("players")) {
            JsonObject entry = element.getAsJsonObject();
            JsonElement command = entry.get("command");
            if (command == null || !command.isJsonArray()) {
                continue;
            }
            for (JsonElement card : command.getAsJsonArray()) {
                JsonObject item = card.getAsJsonObject();
                if (item.has("object_id") && !item.get("object_id").isJsonNull()) {
                    commandIds.add(item.get("object_id").getAsString());
                }
            }
        }
        for (JsonElement element : options.getAsJsonArray()) {
            JsonObject option = element.getAsJsonObject();
            JsonObject metadata = option.getAsJsonObject("metadata");
            if (metadata == null || !metadata.has("source_object_id")
                    || metadata.get("source_object_id").isJsonNull()) {
                continue;
            }
            if (commandIds.contains(metadata.get("source_object_id").getAsString())) {
                String label = option.has("label") && !option.get("label").isJsonNull()
                        ? option.get("label").getAsString() : "commander-cast";
                commanderCastCounts.merge(label, 1, Integer::sum);
            }
        }
    }

    /**
     * Test-oracle hidden-information scan (never pilot input): native opponent
     * hand/library card identities must appear nowhere in the serialized actor
     * view, except inside a live grant-scoped window. Returns violations.
     */
    private static int oracleScan(XmageFullGameSession session, JsonObject pending) {
        try {
            java.lang.reflect.Field gameField =
                    XmageFullGameSession.class.getDeclaredField("game");
            gameField.setAccessible(true);
            Object game = gameField.get(session);
            java.lang.reflect.Method getPlayer =
                    game.getClass().getMethod("getPlayer", java.util.UUID.class);
            JsonObject pilotState = pending.getAsJsonObject("pilot_state");
            String actorId = pending.get("actor_id").getAsString();
            Set<String> granted = new java.util.HashSet<>();
            for (JsonElement element : pilotState.getAsJsonArray("players")) {
                JsonObject entry = element.getAsJsonObject();
                JsonElement grant = entry.get("granted_library");
                if (grant != null && grant.isJsonArray()) {
                    for (JsonElement card : grant.getAsJsonArray()) {
                        JsonObject item = card.getAsJsonObject();
                        if (item.has("object_id") && !item.get("object_id").isJsonNull()) {
                            granted.add(item.get("object_id").getAsString());
                        }
                    }
                }
            }
            Set<String> hidden = new java.util.HashSet<>();
            for (JsonElement element : pilotState.getAsJsonArray("players")) {
                JsonObject entry = element.getAsJsonObject();
                if (actorId.equals(entry.get("player_id").getAsString())) {
                    continue;
                }
                Object player = getPlayer.invoke(
                        game, java.util.UUID.fromString(entry.get("player_id").getAsString()));
                if (player == null) {
                    continue;
                }
                java.lang.reflect.Method getHand = player.getClass().getMethod("getHand");
                java.lang.reflect.Method getLibrary = player.getClass().getMethod("getLibrary");
                Object hand = getHand.invoke(player);
                Object library = getLibrary.invoke(player);
                // Zone card identities via getCards(game) reflect the Rules
                // truth at scan time; any appearance in the actor view leaks.
                // Hand and library are distinct classes: resolve per object.
                java.lang.reflect.Method handCards = findMethod(
                        hand.getClass(), "getCards", 1);
                java.lang.reflect.Method libraryCards = findMethod(
                        library.getClass(), "getCards", 1);
                if (handCards != null) {
                    collectIds(handCards.invoke(hand, game), hidden);
                }
                if (libraryCards != null) {
                    collectIds(libraryCards.invoke(library, game), hidden);
                }
            }
            hidden.removeAll(granted);
            if (hidden.isEmpty()) {
                return 0;
            }
            String serialized = pilotState.toString();
            int violations = 0;
            for (String id : hidden) {
                if (serialized.contains(id)) {
                    violations++;
                }
            }
            return violations;
        } catch (Exception exc) {
            // Oracle introspection must never wedge qualification nor fake a
            // pass: count the miss distinctly for adjudication.
            oracleErrors++;
            if (oracleErrors <= 2) {
                exc.printStackTrace();
            }
            return 0;
        }
    }

    private static java.lang.reflect.Method findMethod(
            Class<?> type, String name, int parameters) {
        for (java.lang.reflect.Method method : type.getMethods()) {
            if (method.getName().equals(name) && method.getParameterCount() == parameters) {
                return method;
            }
        }
        return null;
    }

    private static void collectIds(Object cards, Set<String> hidden) throws Exception {
        if (cards == null) {
            return;
        }
        if (cards instanceof java.util.Collection<?> collection) {
            for (Object card : collection) {
                java.lang.reflect.Method getId = card.getClass().getMethod("getId");
                Object id = getId.invoke(card);
                if (id != null) {
                    hidden.add(id.toString());
                }
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
            // Forced mulligan (qualification exercise): the first actor to
            // face a mulligan decision takes twice, exercising the free-first
            // London path and then the paid London bottom-target flow
            // natively. All other actors keep.
            if (forceMulligan
                    && (forcedMulliganActor == null || forcedMulliganActor.equals(actor))
                    && MULLIGANS_TAKEN.getOrDefault(actor, 0) < 2) {
                for (JsonElement element : actions) {
                    JsonObject action = element.getAsJsonObject();
                    if ("mulligan".equals(action.getAsJsonObject("metadata")
                            .get("option_type").getAsString())) {
                        forcedMulliganActor = actor;
                        MULLIGANS_TAKEN.merge(actor, 1, Integer::sum);
                        submitTracked(session, genericProposal(
                                "ws215-probe", actor,
                                action.get("action_id").getAsString(), "mulligan"));
                        return;
                    }
                }
            }
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
        // Commander zone-choice alternation (deterministic harness coverage):
        // game-wide alternating NO/YES across occurrences so both native
        // branches are exercised; the engine owns all consequences (zone
        // movement, tax on recast).
        JsonElement zonePrompt = pending.get("prompt");
        String zoneText = zonePrompt != null && zonePrompt.isJsonPrimitive()
                ? zonePrompt.getAsString().toLowerCase() : "";
        if ("choose_use".equals(decisionClass) && zoneText.contains("command zone")) {
            boolean takeYes = zoneChoiceCount % 2 == 1;
            zoneChoiceCount++;
            JsonObject pick = null;
            String pickKey = null;
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                String key = stableActionKey(action);
                if (pick == null
                        || (!takeYes ? key.compareTo(pickKey) < 0
                                : key.compareTo(pickKey) > 0)) {
                    pick = action;
                    pickKey = key;
                }
            }
            if (pick != null) {
                submitTracked(session, genericProposal(
                        "ws215-probe", actor,
                        pick.get("action_id").getAsString(),
                        pick.get("action_type").getAsString()));
                return;
            }
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
        // London paid-mulligan bottoming arrives as a hand-target choice
        // ("... to put on the bottom of your library"), never as a
        // choose_object: prompt-based detection across classes.
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

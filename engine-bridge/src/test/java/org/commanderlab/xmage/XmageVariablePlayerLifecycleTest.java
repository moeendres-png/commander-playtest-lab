package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS215 variable-player lifecycle: every supported count (2..5) runs a real
 * bounded native lifecycle far enough to prove construction, registration,
 * starting player, mulligan flow, priority progression across the live ring,
 * authoritative decisions, and turn advancement with no silently skipped
 * callback. 4P is a fresh regression (not retained WS213 evidence).
 * Concession/elimination is exercised in 3P and 5P; multiple defending
 * players are observed natively in 4P and 5P combat.
 */
class XmageVariablePlayerLifecycleTest {

    private static final long LIFECYCLE_SEED = 424242L;
    private static final Map<String, Integer> MULLIGANS_TAKEN = new HashMap<>();
    private static final Set<String> BASIC_LANDS = Set.of(
            "Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
            "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
            "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes");

    @Test
    void twoPlayerBoundedLifecycle() throws Exception {
        LifecycleSummary summary = runBoundedLifecycle(2, LIFECYCLE_SEED, 150, "neutral");
        assertLifecycle(summary, 2);
    }

    @Test
    void threePlayerBoundedLifecycle() throws Exception {
        LifecycleSummary summary = runBoundedLifecycle(3, LIFECYCLE_SEED, 150, "neutral");
        assertLifecycle(summary, 3);
    }

    @Test
    void fourPlayerBoundedLifecycleRegression() throws Exception {
        LifecycleSummary summary = runBoundedLifecycle(4, LIFECYCLE_SEED, 150, "neutral");
        assertLifecycle(summary, 4);
    }

    @Test
    void fivePlayerBoundedLifecycle() throws Exception {
        LifecycleSummary summary = runBoundedLifecycle(5, LIFECYCLE_SEED, 150, "neutral");
        assertLifecycle(summary, 5);
    }

    @Test
    void threePlayerConcessionEliminatesExactlyOnePrincipal() throws Exception {
        concessionContinues(3, LIFECYCLE_SEED);
    }

    @Test
    void fivePlayerConcessionEliminatesExactlyOnePrincipal() throws Exception {
        concessionContinues(5, LIFECYCLE_SEED);
    }

    @Test
    void fourPlayerMultipleDefendingPlayersObserved() throws Exception {
        LifecycleSummary summary = runBoundedLifecycle(4, LIFECYCLE_SEED, 600, "develop", "lions");
        assertTrue(
                summary.defenders.size() >= 2,
                "4P combat must name >=2 distinct native defenders; observed "
                        + summary.defenders.size()
        );
    }

    @Test
    void fivePlayerMultipleDefendingPlayersObserved() throws Exception {
        LifecycleSummary summary = runBoundedLifecycle(5, LIFECYCLE_SEED, 600, "develop", "lions");
        assertTrue(
                summary.defenders.size() >= 2,
                "5P combat must name >=2 distinct native defenders; observed "
                        + summary.defenders.size()
        );
    }

    private static void assertLifecycle(LifecycleSummary summary, int expected) {
        assertEquals(expected, summary.playerCount, "native player registration");
        assertEquals(Math.floorMod(LIFECYCLE_SEED, expected), summary.startingSeat,
                "starting player is seed mod N");
        assertTrue(summary.mulligansAnswered >= expected,
                "every seat must pass the mulligan flow");
        assertTrue(summary.classes.contains("priority"), "priority must progress");
        assertTrue(summary.priorityActors.size() >= 2,
                "priority must rotate across the live ring");
        assertTrue(summary.maxTurn >= 2, "turns must advance natively");
        assertTrue(summary.decisions > 0, "authoritative decisions must execute");
        assertEquals(0, summary.hiddenViolations, "principal-scoped observations");
        assertTrue(summary.bindingMatches && summary.bindingExplicit && summary.seedSupported,
                "WS213 seed binding holds for every count");
        assertTrue(summary.rulesRandomCalls > 0, "Rules RNG must be consumed");
        assertTrue(summary.failure == null, "no unsupported callback may fail silently");
        assertEquals(expected, summary.outcomes, "exact seat/principal map");
    }

    private static void concessionContinues(int players, long seed) throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, loadRogShaiRuntimeDeck(), players);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws215-concede-" + players + "p", handles,
                (int) Math.floorMod(seed, players), 40, seed, importer
        );
        session.start();
        answerMulligans(session, players * 2);

        String conceder = outcomePlayerId(session, 1);
        assertTrue(session.concedeOfferPayload(conceder)
                .get("concede_available").getAsBoolean());
        JsonObject result = session.submitConcede(concedeProposal(conceder));
        assertEquals(conceder, result.get("conceded_actor_id").getAsString());
        assertTrue(outcomeLost(result, conceder), "native concede marks exact principal lost");

        int answered = 0;
        String lastActor = null;
        for (int step = 0; step < 60; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            lastActor = pending.get("actor_id").getAsString();
            answerNeutrally(session, pending, "neutral");
            answered++;
        }
        assertTrue(answered > 0, "surviving ring must keep deciding after elimination");
        JsonObject tail = session.pendingDecisionPayload();
        if (!tail.get("decision").isJsonNull()) {
            String actor = tail.getAsJsonObject("decision").get("actor_id").getAsString();
            assertTrue(!conceder.equals(actor)
                            || !session.concedeOfferPayload(conceder)
                                    .get("concede_available").getAsBoolean(),
                    "losers no longer receive production decisions");
        }
        JsonObject outcomes = session.pendingDecisionPayload();
        assertEquals(players, outcomes.getAsJsonArray("outcomes").size(),
                "seat/principal map stays exact after elimination");
    }

    private record LifecycleSummary(
            int playerCount,
            int startingSeat,
            int decisions,
            Set<String> classes,
            Set<String> priorityActors,
            Set<String> defenders,
            int mulligansAnswered,
            int maxTurn,
            boolean bindingMatches,
            boolean bindingExplicit,
            boolean seedSupported,
            long rulesRandomCalls,
            int outcomes,
            int hiddenViolations,
            String failure
    ) {
    }

    private static LifecycleSummary runBoundedLifecycle(
            int players, long seed, int budget, String mode) throws Exception {
        return runBoundedLifecycle(players, seed, budget, mode, "rogshai");
    }

    private static LifecycleSummary runBoundedLifecycle(
            int players, long seed, int budget, String mode, String deckName) throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        RuntimeDeck deck = "lions".equals(deckName)
                ? loadLionsTechnicalDeck()
                : loadRogShaiRuntimeDeck();
        List<String> handles = importCopies(importer, deck, players);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws215-lifecycle-" + players + "p", handles,
                (int) Math.floorMod(seed, players), 40, seed, importer
        );
        session.start();

        Set<String> classes = new HashSet<>();
        Set<String> priorityActors = new HashSet<>();
        Set<String> defenders = new HashSet<>();
        int mulligans = 0;
        int maxTurn = 1;
        int hiddenViolations = 0;
        int decisions = 0;
        int startingSeat = -1;
        int outcomeCount = -1;
        String failure = null;

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
            if ("priority".equals(decisionClass)) {
                priorityActors.add(actor);
            }
            if ("mulligan".equals(decisionClass)) {
                mulligans++;
            }
            if ("declare_attacker".equals(decisionClass)) {
                collectDefenders(pending, defenders);
            }
            startingSeat = payload.get("starting_player_seat").getAsInt();
            outcomeCount = payload.getAsJsonArray("outcomes").size();
            maxTurn = Math.max(maxTurn, payload.get("turn_number").getAsInt());
            hiddenViolations += checkActorScoping(pending);
            answerNeutrally(session, pending, mode);
            decisions++;
        }

        JsonObject binding = session.rulesSeedBindingPayload();
        JsonObject tail = session.pendingDecisionPayload();
        if (!tail.get("failure").isJsonNull()) {
            failure = tail.get("failure").toString();
        }
        return new LifecycleSummary(
                tail.get("player_count").getAsInt(),
                startingSeat,
                decisions,
                classes,
                priorityActors,
                defenders,
                mulligans,
                maxTurn,
                binding.get("rules_seed_matches").getAsBoolean(),
                binding.get("rules_seed_explicit").getAsBoolean(),
                binding.get("seed_supported").getAsBoolean(),
                binding.get("rules_random_calls").getAsLong(),
                outcomeCount,
                hiddenViolations,
                failure
        );
    }

    private static void collectDefenders(JsonObject pending, Set<String> defenders) {
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
                defenders.add(metadata.get("defender_id").getAsString());
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
            } else {
                if (entry.has("hand") || entry.has("mana_pool")) {
                    violations++;
                }
            }
        }
        return violations;
    }

    private static void answerMulligans(XmageFullGameSession session, int budget) {
        for (int step = 0; step < budget; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                return;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            if (!"mulligan".equals(pending.get("decision_class").getAsString())) {
                return;
            }
            answerNeutrally(session, pending, "neutral");
        }
    }

    private static void answerNeutrally(
            XmageFullGameSession session, JsonObject pending, String mode) {
        String decisionClass = pending.get("decision_class").getAsString();
        JsonObject legal = session.legalActionsPayload();
        String actor = legal.get("actor_id").getAsString();
        JsonArray actions = legal.getAsJsonArray("actions");
        if (actions.size() == 0) {
            return;
        }
        if ("mulligan".equals(decisionClass)) {
            if ("develop".equals(mode)) {
                int taken = MULLIGANS_TAKEN.getOrDefault(actor, 0);
                if (taken == 0 && isExtremeOpener(pending)) {
                    for (JsonElement element : actions) {
                        JsonObject action = element.getAsJsonObject();
                        if ("mulligan".equals(action.getAsJsonObject("metadata")
                                .get("option_type").getAsString())) {
                            MULLIGANS_TAKEN.put(actor, 1);
                            session.submitAction(genericProposal(
                                    "ws215-develop", actor,
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
                    session.submitAction(genericProposal(
                            "ws215-neutral", actor,
                            action.get("action_id").getAsString(), "mulligan"));
                    return;
                }
            }
        }
        if ("choose_object".equals(decisionClass) && isLondonBottom(pending)) {
            int need = pending.has("minimum_selections")
                    && !pending.get("minimum_selections").isJsonNull()
                    ? pending.get("minimum_selections").getAsInt() : 0;
            List<JsonObject> ranked = new ArrayList<>();
            for (JsonElement element : actions) {
                ranked.add(element.getAsJsonObject());
            }
            ranked.sort(Comparator.comparing(XmageVariablePlayerLifecycleTest::stableActionKey));
            JsonArray selected = new JsonArray();
            for (int index = 0; index < Math.min(need, ranked.size()); index++) {
                JsonObject meta = ranked.get(index).getAsJsonObject("metadata");
                if (meta != null && meta.has("option_id") && !meta.get("option_id").isJsonNull()) {
                    selected.add(meta.get("option_id").getAsString());
                }
            }
            JsonObject proposal = genericProposal("ws215-bottom", actor, "", "structural_decision");
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
            session.submitAction(proposal);
            return;
        }
        if ("priority".equals(decisionClass)) {
            if ("develop".equals(mode)) {
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
                    session.submitAction(genericProposal(
                            "ws215-develop", actor,
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
                    // Develop casts only target-free, mode-free spells (the
                    // harness cannot author legal targets/modes).
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
                    session.submitAction(genericProposal(
                            "ws215-develop", actor,
                            cast.get("action_id").getAsString(),
                            cast.get("action_type").getAsString()));
                    return;
                }
            }
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                if ("pass_priority".equals(action.get("action_type").getAsString())) {
                    session.submitAction(genericProposal(
                            "ws215-neutral", actor,
                            action.get("action_id").getAsString(), "pass_priority"));
                    return;
                }
            }
        }
        if ("mana_payment".equals(decisionClass)) {
            // Pool-aware deterministic mana with the WS215 liveness guard
            // (never spend pool mana that matches no unpaid colored need).
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
                session.submitAction(genericProposal(
                        "ws215-mana", actor,
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
                session.submitAction(genericProposal(
                        "ws215-mana", actor,
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
                    session.submitAction(genericProposal(
                            "ws215-mana", actor,
                            action.get("action_id").getAsString(),
                            action.get("action_type").getAsString()));
                    return;
                }
            }
        }
        if ("declare_attacker".equals(decisionClass) && "develop".equals(mode)) {
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
                session.submitAction(genericProposal(
                        "ws215-develop", actor,
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
                session.submitAction(genericProposal(
                        "ws215-develop", actor,
                        block.get("action_id").getAsString(), "declare_blockers"));
                return;
            }
        }
        if ("declare_attacker".equals(decisionClass)) {
            for (JsonElement element : actions) {
                JsonObject action = element.getAsJsonObject();
                if ("hold_attacker".equals(action.getAsJsonObject("metadata")
                        .get("option_type").getAsString())) {
                    session.submitAction(genericProposal(
                            "ws215-neutral", actor,
                            action.get("action_id").getAsString(), "declare_attackers"));
                    return;
                }
            }
        }
        // Deterministic harness fallback (reachability only): rank by stable
        // Rules-visible content, never by raw action id (per-process UUIDs).
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
                "ws215-neutral", actor,
                first.get("action_id").getAsString(),
                first.get("action_type").getAsString());
        JsonObject context = pending.getAsJsonObject("context");
        if (context != null && context.has("numeric_min") && !context.get("numeric_min").isJsonNull()
                && ("announce_x".equals(decisionClass) || "amount".equals(decisionClass)
                        || "multi_amount".equals(decisionClass))) {
            proposal.getAsJsonObject("choices").addProperty(
                    "numeric_choice", context.get("numeric_min").getAsInt());
        }
        session.submitAction(proposal);
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

    private static String outcomePlayerId(XmageFullGameSession session, int seat) {
        JsonObject payload = session.pendingDecisionPayload();
        JsonArray outcomes = payload.getAsJsonArray("outcomes");
        return outcomes.get(seat).getAsJsonObject().get("player_id").getAsString();
    }

    private static boolean outcomeLost(JsonObject result, String principal) {
        for (JsonElement element : result.getAsJsonArray("outcomes")) {
            JsonObject item = element.getAsJsonObject();
            if (principal.equals(item.get("player_id").getAsString())) {
                return item.get("lost").getAsBoolean();
            }
        }
        return false;
    }

    private static JsonObject concedeProposal(String principal) {
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", "ws215-concede");
        proposal.addProperty("actor_id", principal);
        proposal.addProperty("player_id", principal);
        return proposal;
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

    private static List<String> importCopies(
            XmageDeckImporter importer, RuntimeDeck deck, int count) {
        List<String> handles = new ArrayList<>(count);
        for (int copy = 0; copy < count; copy++) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    deck.deckId(), deck.deckHash(), deck.mainboard(), deck.commanders()
            );
            handles.add(imported.deckHandle());
        }
        return List.copyOf(handles);
    }

    private static RuntimeDeck loadLionsTechnicalDeck() throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
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

    private static RuntimeDeck loadRogShaiRuntimeDeck() throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
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

    private record RuntimeDeck(
            String deckId,
            String deckHash,
            List<String> mainboard,
            List<String> commanders
    ) {
    }
}

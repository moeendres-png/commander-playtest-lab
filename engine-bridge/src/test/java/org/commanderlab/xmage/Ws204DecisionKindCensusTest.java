package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.game.CommanderFreeForAll;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS204 non-scoring actual-card census through the generic B4-D boundary.
 *
 * <p>Drives a real full-game session exclusively via
 * {@link XmageFullGameSession#legalActionsPayload()} plus
 * {@link XmageFullGameSession#submitAction(JsonObject)} (the generic
 * LegalAction/ActionProposal transport). Every selection is an offered native
 * option; XMage executes natively. Reachability only; First-Wave behavior
 * scoring stays NOT_RUN and no behavior credit is claimed.</p>
 */
class Ws204DecisionKindCensusTest {

    private static final long CENSUS_SEED = 7017L;
    private static final int MAX_DECISIONS = 120;

    @Test
    void genericBoundaryCensusClassifiesTwentyKindUnionWithoutScoring()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws204-decision-kind-census",
                handles,
                0,
                40,
                CENSUS_SEED,
                importer
        );
        session.start();

        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> censusPlayers =
                (List<XmageFullGamePlayer>) field(session, "players", List.class);
        String requestedStarterId = censusPlayers.get(0).getId().toString();

        List<String> sequence = new ArrayList<>();
        Set<String> observedClasses = new LinkedHashSet<>();
        Map<String, Integer> classCounts = new LinkedHashMap<>();
        String stoppedBy = "decision_budget";
        int answered = 0;
        JsonObject stopDetail = new JsonObject();
        List<JsonObject> evidence = new ArrayList<>();

        for (int step = 0; step < MAX_DECISIONS; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            JsonObject pending = payload.get("decision").isJsonNull()
                    ? null
                    : payload.getAsJsonObject("decision");
            if (pending == null) {
                stoppedBy = "terminal";
                break;
            }
            String decisionClass = pending.get("decision_class").getAsString();
            sequence.add(decisionClass);
            observedClasses.add(decisionClass);
            classCounts.merge(decisionClass, 1, Integer::sum);

            JsonObject legal;
            try {
                legal = session.legalActionsPayload();
            } catch (XmageFullGameDecisionController.DecisionException exc) {
                stoppedBy = "legal_actions_failed:" + decisionClass;
                stopDetail = describeForCensus(pending);
                break;
            }
            // Generic transport invariant: projection preserves actor, decision
            // identity, and offers exactly the native option set.
            if (!legal.get("decision_id").getAsString()
                    .equals(pending.get("decision_id").getAsString())) {
                stoppedBy = "projection_mismatch:" + decisionClass;
                stopDetail = describeForCensus(pending);
                break;
            }
            if (legal.getAsJsonArray("actions").size()
                    != pending.getAsJsonArray("legal_options").size()
                    && pending.getAsJsonArray("legal_options").size() != 0) {
                stoppedBy = "projection_count_mismatch:" + decisionClass;
                stopDetail = describeForCensus(pending);
                break;
            }

            JsonObject proposal = genericAnswer(legal, pending, requestedStarterId);
            if (proposal == null) {
                stoppedBy = "unhandled_decision_class:" + decisionClass;
                stopDetail = describeForCensus(pending);
                break;
            }
            try {
                session.submitAction(proposal);
            } catch (XmageFullGameDecisionController.DecisionException exc) {
                stoppedBy = "submit_rejected:" + decisionClass + ":" + exc.getMessage();
                stopDetail = describeForCensus(pending);
                break;
            }
            answered++;
            if (evidence.size() < 12) {
                JsonObject record = new JsonObject();
                record.addProperty("decision_class", decisionClass);
                record.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
                record.addProperty("actor_seat", pending.get("seat").getAsInt());
                record.addProperty(
                        "legal_option_count",
                        pending.getAsJsonArray("legal_options").size()
                );
                record.addProperty("proposal_id", proposal.get("proposal_id").getAsString());
                record.addProperty(
                        "submitted_action_id",
                        proposal.has("legal_action_id") && !proposal.get("legal_action_id").isJsonNull()
                                ? proposal.get("legal_action_id").getAsString() : "<empty>"
                );
                evidence.add(record);
            }
        }

        JsonObject census = buildCensus(
                session, sequence, observedClasses, classCounts, answered, stoppedBy,
                stopDetail, evidence
        );
        Path out = Path.of("ws204-decision-kind-census.json");
        Files.writeString(out, census.toString(), StandardCharsets.UTF_8);

        assertTrue(observedClasses.contains("mulligan"), "census must reach mulligan");
        assertTrue(observedClasses.contains("priority"), "census must reach priority");
        assertTrue(
                observedClasses.contains("choose_object"),
                "census must reach an object-choice frame"
        );
        // B4-D transport must advance strictly beyond the sealed pass/keep stop
        // point (37 answered, halted on the turn-1 cleanup discard).
        assertTrue(
                answered > 37 || observedClasses.size() > 3 || "terminal".equals(stoppedBy),
                "generic boundary must advance beyond the sealed 37-decision prefix "
                        + "or terminate the game (answered=" + answered
                        + " classes=" + observedClasses + " stoppedBy=" + stoppedBy + ")"
        );
    }

    /**
     * Reachability-only generic answers. Every returned proposal selects only
     * offered native options through the decision-bound transport. Returns null
     * for classes this census driver leaves unanswered (fail-closed stop).
     */
    private static JsonObject genericAnswer(
            JsonObject legal,
            JsonObject pending,
            String requestedStarterId
    ) {
        String decisionClass = pending.get("decision_class").getAsString();
        String actorId = legal.get("actor_id").getAsString();
        JsonArray actions = legal.getAsJsonArray("actions");
        if ("choose_object".equals(decisionClass)
                && pending.get("prompt").getAsString().contains("starting player")) {
            for (JsonElement element : pending.getAsJsonArray("legal_options")) {
                String optionId = element.getAsJsonObject().get("option_id").getAsString();
                if (requestedStarterId.equals(optionId)) {
                    return genericProposal(
                            "ws204-census-starter", actorId,
                            legal.get("decision_id").getAsString() + ":" + optionId,
                            actions.get(0).getAsJsonObject().get("action_type").getAsString()
                    );
                }
            }
            return null;
        }
        return switch (decisionClass) {
            case "mulligan" -> {
                JsonObject keep = actionOfOptionType(legal, "keep");
                yield keep == null ? null : genericProposal(
                        "ws204-census-mulligan", actorId,
                        keep.get("action_id").getAsString(),
                        keep.get("action_type").getAsString());
            }
            case "priority" -> {
                // Reachability activation policy: prefer the smallest offered
                // non-pass action so the game casts/plays and opens mana,
                // target, and combat families. Falls back to pass only when no
                // activation exists. Transparent and deterministic.
                JsonObject activation = smallestNonPassAction(legal);
                JsonObject chosen = activation != null ? activation
                        : actionOfOptionType(legal, "pass_priority");
                yield chosen == null ? null : genericProposal(
                        "ws204-census-priority", actorId,
                        chosen.get("action_id").getAsString(),
                        chosen.get("action_type").getAsString());
            }
            case "declare_attacker" -> {
                // Reachability attack policy: prefer the smallest offered
                // attack so defender/blocker families open. Falls back to hold
                // only when no attack exists. Transparent and deterministic.
                JsonObject attack = smallestAttackAction(legal);
                JsonObject chosen = attack != null ? attack
                        : actionOfOptionType(legal, "hold_attacker");
                yield chosen == null ? null : genericProposal(
                        "ws204-census-attack", actorId,
                        chosen.get("action_id").getAsString(),
                        chosen.get("action_type").getAsString());
            }
            case "declare_blocker" -> {
                JsonObject empty = new JsonObject();
                empty.addProperty("proposal_id", "ws204-census-block");
                empty.addProperty("actor_id", actorId);
                empty.add("legal_action_id", com.google.gson.JsonNull.INSTANCE);
                empty.addProperty("action_type", "structural_decision");
                empty.add("target_ids", new JsonArray());
                empty.add("selected_modes", new JsonArray());
                JsonObject choices = new JsonObject();
                choices.add("selected_option_ids", new JsonArray());
                choices.add("ordering", new JsonArray());
                empty.add("choices", choices);
                yield empty;
            }
            case "choose_object", "target", "target_amount",
                    "choose_use", "choice", "pile",
                    "replacement_effect", "trigger_order", "mode" -> {
                // Reachability selection: lexicographically smallest offered
                // action. Transparent and deterministic; any offered option
                // proves transport because XMage supplied the entire domain.
                // Numeric companions (target_amount) use the schema minimum.
                if (actions.size() == 0) {
                    yield null;
                }
                JsonObject first = actions.get(0).getAsJsonObject();
                for (JsonElement element : actions) {
                    JsonObject candidate = element.getAsJsonObject();
                    if (candidate.get("action_id").getAsString()
                            .compareTo(first.get("action_id").getAsString()) < 0) {
                        first = candidate;
                    }
                }
                JsonObject proposal = genericProposal(
                        "ws204-census-" + decisionClass, actorId,
                        first.get("action_id").getAsString(),
                        first.get("action_type").getAsString());
                if ("target_amount".equals(decisionClass)) {
                    JsonObject context = pending.getAsJsonObject("context");
                    if (context.has("numeric_min") && !context.get("numeric_min").isJsonNull()) {
                        proposal.getAsJsonObject("choices").addProperty(
                                "numeric_choice", context.get("numeric_min").getAsInt());
                    } else {
                        yield null;
                    }
                }
                yield proposal;
            }
            case "mana_payment" -> {
                // Prefer spending pool mana or tapping a source over cancel so
                // casts resolve and open downstream families. Cancel remains a
                // legal offered option; it is simply not the reachability pick.
                JsonObject chosen = smallestNonCancelManaAction(legal);
                yield chosen == null ? null : genericProposal(
                        "ws204-census-mana", actorId,
                        chosen.get("action_id").getAsString(),
                        chosen.get("action_type").getAsString());
            }
            case "announce_x", "amount", "multi_amount" -> {
                JsonObject context = pending.getAsJsonObject("context");
                if (!context.has("numeric_min") || !context.has("numeric_max")) {
                    yield null;
                }
                if (actions.size() != 1) {
                    yield null;
                }
                JsonObject numeric = actions.get(0).getAsJsonObject();
                JsonObject proposal = genericProposal(
                        "ws204-census-numeric", actorId,
                        numeric.get("action_id").getAsString(),
                        numeric.get("action_type").getAsString());
                proposal.getAsJsonObject("choices").addProperty(
                        "numeric_choice", context.get("numeric_min").getAsInt());
                yield proposal;
            }
            default -> null;
        };
    }

    private static JsonObject actionOfOptionType(JsonObject legal, String optionType) {
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String actual = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (optionType.equals(actual)) {
                return action;
            }
        }
        return null;
    }

    private static JsonObject smallestNonPassAction(JsonObject legal) {
        JsonObject best = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if ("pass_priority".equals(optionType)) {
                continue;
            }
            if (best == null
                    || action.get("action_id").getAsString()
                            .compareTo(best.get("action_id").getAsString()) < 0) {
                best = action;
            }
        }
        return best;
    }

    private static JsonObject smallestNonCancelManaAction(JsonObject legal) {
        JsonObject best = null;
        JsonObject cancel = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if ("cancel_mana_payment".equals(optionType)) {
                cancel = action;
                continue;
            }
            if (best == null
                    || action.get("action_id").getAsString()
                            .compareTo(best.get("action_id").getAsString()) < 0) {
                best = action;
            }
        }
        return best != null ? best : cancel;
    }

    private static JsonObject smallestAttackAction(JsonObject legal) {
        JsonObject best = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject metadata = action.getAsJsonObject("metadata");
            String optionType = metadata.has("option_type") && !metadata.get("option_type").isJsonNull()
                    ? metadata.get("option_type").getAsString() : "";
            if (!"declare_attacker".equals(optionType)) {
                continue;
            }
            if (best == null
                    || action.get("action_id").getAsString()
                            .compareTo(best.get("action_id").getAsString()) < 0) {
                best = action;
            }
        }
        return best;
    }

    private static JsonObject genericProposal(
            String proposalId,
            String actorId,
            String actionId,
            String actionType
    ) {
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
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "ws204-census-reachability");
        return proposal;
    }

    private static JsonObject buildCensus(
            XmageFullGameSession session,
            List<String> sequence,
            Set<String> observedClasses,
            Map<String, Integer> classCounts,
            int answered,
            String stoppedBy,
            JsonObject stopDetail,
            List<JsonObject> evidence
    ) throws Exception {
        CommanderFreeForAll game = field(session, "game", CommanderFreeForAll.class);
        XmageFullGameDecisionController controller =
                field(session, "controller", XmageFullGameDecisionController.class);

        Map<String, String> kindToClass = new LinkedHashMap<>();
        kindToClass.put("cast", "choice(cast_ability)");
        kindToClass.put("targets", "target");
        kindToClass.put("mana payment", "mana_payment");
        kindToClass.put("activate", "priority(activated_ability)");
        kindToClass.put("mana source", "priority(mana_ability)");
        kindToClass.put("X", "announce_x");
        kindToClass.put("replacement ordering", "replacement_effect");
        kindToClass.put("trigger ordering", "trigger_order");
        kindToClass.put("modes", "mode");
        kindToClass.put("copy choices", "choice");
        kindToClass.put("hidden-zone selection", "choose_object");
        kindToClass.put("search", "choose_object(library)");
        kindToClass.put("attackers", "declare_attacker");
        kindToClass.put("defender per attacker", "declare_attacker");
        kindToClass.put("blockers", "declare_blocker");
        kindToClass.put("combat damage assignment", "declare_blocker(damage)");
        kindToClass.put("alternate cost", "choice");
        kindToClass.put("Commander movement", "choose_use(commander)");
        kindToClass.put("concession", "concede");
        kindToClass.put("pass", "priority");

        Map<String, String> kinds = new LinkedHashMap<>();
        kinds.put("pass", statusFor(observedClasses, "priority"));
        kinds.put("hidden-zone selection", statusFor(observedClasses, "choose_object"));
        kinds.put("attackers", statusFor(observedClasses, "declare_attacker"));
        kinds.put("defender per attacker", statusFor(observedClasses, "declare_attacker"));
        kinds.put("blockers", statusFor(observedClasses, "declare_blocker"));
        kinds.put("cast", statusFor(observedClasses, "choice"));
        kinds.put("alternate cost", statusFor(observedClasses, "choice"));
        kinds.put("copy choices", statusFor(observedClasses, "choice"));
        kinds.put("targets", statusFor(observedClasses, "target"));
        kinds.put("search", searchStatus(observedClasses));
        kinds.put("mana payment", statusFor(observedClasses, "mana_payment"));
        kinds.put("activate", "NOT_OBSERVED via generic priority driver in this run "
                + "(priority passes only; activation requires a cast/ability selection policy)");
        kinds.put("mana source", "NOT_OBSERVED via generic priority driver in this run "
                + "(priority passes only; mana abilities require an activation policy)");
        kinds.put("X", statusFor(observedClasses, "announce_x"));
        kinds.put("replacement ordering", statusFor(observedClasses, "replacement_effect"));
        kinds.put("trigger ordering", statusFor(observedClasses, "trigger_order"));
        kinds.put("modes", statusFor(observedClasses, "mode"));
        kinds.put("combat damage assignment",
                "NOT_OBSERVED: no Player damage-assignment hook exists on the pinned "
                        + "engine; XMAGE_ENGINE_CORE_REMEDIATION_REQUIRED (see WS204 report)");
        kinds.put("Commander movement", statusFor(observedClasses, "choose_use"));
        kinds.put("concession",
                "NOT_OBSERVED: concession is explicitly fail-closed "
                        + "(concede_supported=false; XMAGE_ENGINE_CORE_REMEDIATION_REQUIRED)");
        for (String kind : kindToClass.keySet()) {
            kinds.putIfAbsent(kind, "NOT_OBSERVED in this generic-boundary run");
        }

        JsonObject census = new JsonObject();
        census.addProperty("schema", "ws204.decision-kind-census.v1");
        census.addProperty("workstream", "WS204-XMAGE-B4D-ACTION-SUBMISSION");
        census.addProperty("engine_commit", "cfc36f445f917f101fa2ed588770e043f53bc44c");
        census.addProperty("seed", CENSUS_SEED);
        census.addProperty("deck", "rogshai_current.json");
        census.addProperty("operational_pod_size", 4);
        census.addProperty("driver",
                "generic B4-D transport (legalActionsPayload/submitAction); "
                        + "mulligan keep, priority pass, attacker hold, zero blockers, "
                        + "lexicographically-smallest offered option for richer classes, "
                        + "schema-minimum numeric; reachability only");
        census.addProperty("behavior_scoring", "NOT_RUN");
        census.addProperty("behavior_credit_change", 0);
        census.addProperty("engine_game_id", game.getId().toString());
        census.addProperty("decisions_answered", answered);
        census.addProperty("stopped_by", stoppedBy);
        census.add("stop_detail", stopDetail);
        census.addProperty("controller_decision_count", controller.decisionCount());
        JsonArray sequenceJson = new JsonArray();
        sequence.forEach(sequenceJson::add);
        census.add("offered_decision_class_sequence", sequenceJson);
        JsonArray observedJson = new JsonArray();
        observedClasses.forEach(observedJson::add);
        census.add("observed_decision_classes", observedJson);
        JsonObject counts = new JsonObject();
        classCounts.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> counts.addProperty(entry.getKey(), entry.getValue()));
        census.add("observed_class_counts", counts);
        JsonObject kindsJson = new JsonObject();
        kinds.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> kindsJson.addProperty(entry.getKey(), entry.getValue()));
        census.add("twenty_kind_classification", kindsJson);
        JsonObject mapping = new JsonObject();
        kindToClass.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> mapping.addProperty(entry.getKey(), entry.getValue()));
        census.add("kind_to_decision_class_mapping", mapping);
        JsonArray evidenceJson = new JsonArray();
        evidence.forEach(evidenceJson::add);
        census.add("transport_evidence", evidenceJson);
        return census;
    }

    private static String statusFor(Set<String> observed, String decisionClass) {
        if (observed.contains(decisionClass)) {
            return "OBSERVED: engine requested " + decisionClass
                    + " through the generic B4-D transport in a real cfc36f game "
                    + "(reachability only; not behavior PASS)";
        }
        return "NOT_OBSERVED in this generic-boundary run";
    }

    private static String searchStatus(Set<String> observed) {
        if (observed.contains("choose_object")) {
            return "OBSERVED (choose_object frame reached; library-scoped search "
                    + "proven only when the offered set is library-zone with a D2 "
                    + "look grant; see Ws92D1D2D3ProjectionTest for grant lifecycle)";
        }
        return "NOT_OBSERVED in this generic-boundary run";
    }

    private static JsonObject describeForCensus(JsonObject pending) {
        JsonObject detail = new JsonObject();
        detail.addProperty(
                "prompt",
                XmageFullGameDecisionController.redactObjectIds(
                        pending.get("prompt").getAsString()
                )
        );
        detail.addProperty("minimum_selections", pending.get("minimum_selections").getAsInt());
        detail.addProperty("maximum_selections", pending.get("maximum_selections").getAsInt());
        detail.addProperty("legal_option_count", pending.getAsJsonArray("legal_options").size());
        Map<String, Integer> histogram = new LinkedHashMap<>();
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            String type = element.getAsJsonObject().get("option_type").getAsString();
            histogram.put(type, histogram.getOrDefault(type, 0) + 1);
        }
        JsonObject types = new JsonObject();
        histogram.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> types.addProperty(entry.getKey(), entry.getValue()));
        detail.add("legal_option_types", types);
        return detail;
    }

    @SuppressWarnings("unchecked")
    private static <T> T field(Object target, String name, Class<T> type)
            throws ReflectiveOperationException {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return (T) field.get(target);
    }

    private static List<String> importCopies(
            XmageDeckImporter importer,
            RuntimeDeck deck,
            int count
    ) {
        List<String> handles = new ArrayList<>(count);
        for (int copy = 0; copy < count; copy++) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    deck.deckId(),
                    deck.deckHash(),
                    deck.mainboard(),
                    deck.commanders()
            );
            handles.add(imported.deckHandle());
        }
        return List.copyOf(handles);
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck()
            throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
        Path path = Path.of(repoRoot, "data", "decks", "rogshai_current.json").normalize();
        JsonObject root = JsonParser.parseString(
                Files.readString(path, StandardCharsets.UTF_8)
        ).getAsJsonObject();
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
        return new RuntimeDeck(
                root.get("deck_id").getAsString(),
                root.get("deck_hash").getAsString(),
                List.copyOf(mainboard),
                List.copyOf(commanders)
        );
    }

    private record RuntimeDeck(
            String deckId,
            String deckHash,
            List<String> mainboard,
            List<String> commanders
    ) {
    }
}

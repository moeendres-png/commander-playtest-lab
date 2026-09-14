package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
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
 * WS92 non-scoring actual-card decision-kind census on current cfc36f.
 *
 * <p>Drives a real started full-game session (real RogShai decks, engine seed
 * authority) with a pass/keep-only scripted census driver and records which
 * engine-requested decision classes the D1-D5-restored bridge surfaces. The
 * driver answers only always-legal progressions (mulligan keep, priority
 * pass, attacker hold, zero blockers); any richer engine decision is
 * recorded and left unanswered, so the driver never selects among meaningful
 * options and never reconstructs legality.</p>
 *
 * <p>Classification discipline: a WS90 kind is OBSERVED only when the engine
 * requested its dedicated decision class in a real game. OBSERVED is a
 * reachability fact, never behavior PASS. First-Wave behavior scoring stays
 * NOT_RUN. No historical WS60 credit is consumed.</p>
 */
class Ws92DecisionKindCensusTest {

    private static final long CENSUS_SEED = 7017L;
    private static final int MAX_DECISIONS = 60;

    @Test
    void actualCardCensusClassifiesTwentyKindUnionWithoutScoring()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws92-decision-kind-census",
                handles,
                0,
                40,
                CENSUS_SEED,
                importer
        );
        session.start();

        List<String> sequence = new ArrayList<>();
        Set<String> observedClasses = new LinkedHashSet<>();
        String stoppedBy = "decision_budget";
        int answered = 0;
        JsonObject stopDetail = new JsonObject();
        // The session declares seat 0 the starting player; the engine still
        // opens a starting-player selection, which the census driver honors
        // by voting the declared seat (setup-honoring, never tactical).
        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> censusPlayers =
                (List<XmageFullGamePlayer>) field(session, "players", List.class);
        String requestedStarterId = censusPlayers.get(0).getId().toString();

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

            List<String> answer = censusAnswer(pending, requestedStarterId);
            if (answer == null) {
                stoppedBy = "unhandled_decision_class:" + decisionClass;
                stopDetail = describeForCensus(pending);
                break;
            }
            session.submit(submitFor(pending, answer));
            answered++;
        }

        JsonObject census = buildCensus(
                session, sequence, observedClasses, answered, stoppedBy, stopDetail
        );
        // Surefire runs with workingDirectory=target, so a bare relative path
        // lands predictably in engine-bridge/target/ (which always exists).
        Path out = Path.of("ws92-decision-kind-census.json");
        Files.writeString(out, census.toString(), StandardCharsets.UTF_8);

        // The restored bridge must drive a real game at least through setup
        // selection, opening hands, and priority passing to turn-1 cleanup,
        // where the engine offers a real hand-discard choice the census
        // driver records but leaves unanswered by discipline.
        assertTrue(observedClasses.contains("mulligan"), "census must reach mulligan");
        assertTrue(observedClasses.contains("priority"), "census must reach priority");
        assertTrue(
                observedClasses.contains("choose_object"),
                "census must reach an object-choice frame"
        );
        assertTrue(
                stoppedBy.startsWith("unhandled_decision_class:choose_object"),
                "census driver must stop fail-closed on the discard choice, "
                        + "never selecting among meaningful options"
        );
    }

    /**
     * Pass/keep-only census answers, selected by engine-supplied option type
     * (never by position), plus the setup-honoring starting-player vote.
     * Returns null for decision classes the census driver must not answer.
     */
    private static List<String> censusAnswer(JsonObject pending, String requestedStarterId) {
        String decisionClass = pending.get("decision_class").getAsString();
        if ("choose_object".equals(decisionClass)
                && pending.get("prompt").getAsString().contains("starting player")) {
            for (JsonElement element : pending.getAsJsonArray("legal_options")) {
                JsonObject option = element.getAsJsonObject();
                if (requestedStarterId.equals(option.get("option_id").getAsString())) {
                    return List.of(requestedStarterId);
                }
            }
            return null;
        }
        return switch (decisionClass) {
            case "mulligan" -> singleOfType(pending, "keep");
            case "priority" -> singleOfType(pending, "pass_priority");
            case "declare_attacker" -> singleOfType(pending, "hold_attacker");
            case "declare_blocker" -> List.of();
            default -> null;
        };
    }

    private static List<String> singleOfType(JsonObject pending, String optionType) {
        for (JsonElement element : pending.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (optionType.equals(option.get("option_type").getAsString())) {
                return List.of(option.get("option_id").getAsString());
            }
        }
        return null;
    }

    private static JsonObject submitFor(JsonObject pending, List<String> selected) {
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", pending.get("decision_id").getAsString());
        response.addProperty("actor_id", pending.get("actor_id").getAsString());
        JsonArray ids = new JsonArray();
        selected.forEach(ids::add);
        response.add("selected_option_ids", ids);
        response.add("ordering", new JsonArray());
        response.add("numeric_choice", JsonNull.INSTANCE);
        return response;
    }

    private static JsonObject buildCensus(
            XmageFullGameSession session,
            List<String> sequence,
            Set<String> observedClasses,
            int answered,
            String stoppedBy,
            JsonObject stopDetail
    ) throws Exception {
        CommanderFreeForAll game = field(session, "game", CommanderFreeForAll.class);
        XmageFullGameDecisionController controller =
                field(session, "controller", XmageFullGameDecisionController.class);

        // Engine-requested decision class -> WS90 corrected union kinds it
        // instantiates. A kind is OBSERVED only when its dedicated class was
        // requested by the engine in this real game.
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

        Map<String, String> observedKindStatus = new LinkedHashMap<>();
        observedKindStatus.put("pass", statusFor(observedClasses, "priority"));
        observedKindStatus.put(
                "hidden-zone selection",
                "OBSERVED: engine requested choose_object over real hand cards "
                        + "(turn-1 cleanup discard, 8 options); the census driver records "
                        + "the offer and leaves it unanswered by discipline, so no discard "
                        + "preference is exercised. Library look-window path (D2) is proven "
                        + "only by the Ws92D1D2D3ProjectionTest grant test, not end to end."
        );
        observedKindStatus.put(
                "attackers",
                "NOT_OBSERVED: pass-only play reaches turn-1 cleanup discard without "
                        + "plays; combat declaration never opens. Requires an "
                        + "action-submission pilot (B4-D boundary)."
        );
        observedKindStatus.put(
                "defender per attacker",
                "NOT_OBSERVED: same combat cause as attackers."
        );
        observedKindStatus.put(
                "blockers",
                "NOT_OBSERVED: same combat cause as attackers."
        );
        for (String kind : kindToClass.keySet()) {
            observedKindStatus.putIfAbsent(
                    kind,
                    "NOT_OBSERVED: requires an action-submission pilot beyond the "
                            + "pass/keep census driver (B4-D legal_actions/action_submission "
                            + "boundary; see WS90 XMAGE_EXECUTION_READINESS BLOCKED_BY_BOUNDARY)"
            );
        }

        JsonObject census = new JsonObject();
        census.addProperty("schema", "ws92.decision-kind-census.v1");
        census.addProperty("workstream", "WS92-XMAGE-D1-D5-BOUNDARY-REACQUISITION");
        census.addProperty("engine_commit", "cfc36f445f917f101fa2ed588770e043f53bc44c");
        census.addProperty("seed", CENSUS_SEED);
        census.addProperty("deck", "rogshai_current.json");
        census.addProperty("operational_pod_size", 4);
        census.addProperty("driver", "pass/keep-only (mulligan keep, priority pass, "
                + "attacker hold, zero blockers); richer decisions recorded unanswered");
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
        JsonObject kinds = new JsonObject();
        observedKindStatus.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> kinds.addProperty(entry.getKey(), entry.getValue()));
        census.add("twenty_kind_classification", kinds);
        JsonObject mapping = new JsonObject();
        kindToClass.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> mapping.addProperty(entry.getKey(), entry.getValue()));
        census.add("kind_to_decision_class_mapping", mapping);
        return census;
    }

    /**
     * Stop diagnostics for the census seal: prompt (redacted), selection
     * bounds, and option-type histogram. Labels and metadata stay out of the
     * artifact so no hidden identity leaks into evidence.
     */
    private static JsonObject describeForCensus(JsonObject pending) {
        JsonObject detail = new JsonObject();
        detail.addProperty(
                "prompt",
                XmageFullGameDecisionController.redactObjectIds(
                        pending.get("prompt").getAsString()
                )
        );
        detail.addProperty(
                "minimum_selections", pending.get("minimum_selections").getAsInt()
        );
        detail.addProperty(
                "maximum_selections", pending.get("maximum_selections").getAsInt()
        );
        detail.addProperty(
                "legal_option_count", pending.getAsJsonArray("legal_options").size()
        );
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

    private static String statusFor(Set<String> observedClasses, String decisionClass) {
        if (observedClasses.contains(decisionClass)) {
            return "OBSERVED: engine requested the dedicated decision class in a real "
                    + "cfc36f game (reachability only; not behavior PASS)";
        }
        return "NOT_OBSERVED under the pass/keep census driver";
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

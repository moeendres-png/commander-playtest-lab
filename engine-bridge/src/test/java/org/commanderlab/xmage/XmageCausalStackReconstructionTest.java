package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.stack.StackObject;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageCausalStackReconstructionTest {

    private static final long SEED = 424242L;

    @Test
    void targetedLightningBoltIsReconstructedByRealCastAtThreeFourAndFivePlayers() {
        for (int players : List.of(3, 4, 5)) {
            JsonObject record = baseRecord("rg01-bolt-" + players, players);
            addObject(record, "obj:bolt", "Lightning Bolt", "P1", "P1", "stack");
            addObject(record, "obj:red", "Mountain", "P1", "P1", "battlefield");
            addStackFrame(record, "obj:bolt", "P1", List.of("P2"), List.of());

            Run run = reconstruct(
                    record,
                    "rg01-bolt-" + players,
                    modeBySemantic(Map.of()),
                    Map.of("P1", List.of("obj:red")));
            assertEquals(1, run.result().nativeStackObjectIds().size());
            StackObject bolt = stackBySemantic(run, "obj:bolt");
            assertEquals("Lightning Bolt", bolt.getName());
            assertEquals(1, bolt.getStackAbility().getTargets().getTargetsByTag(0).size()
                    + bolt.getStackAbility().getTargets().stream()
                    .skip(1).mapToInt(t -> t.getTargets().size()).sum());
            assertTrue(run.result().submittedDecisions() > 0);
        }
    }

    @Test
    void modalSpellPreservesRealEngineModeSelection() {
        JsonObject record = baseRecord("rg01-modal", 4);
        addObject(record, "obj:burn", "Burn Down the House", "P1", "P1", "stack");
        for (int i = 1; i <= 5; i++) {
            addObject(record, "obj:red-" + i, "Mountain", "P1", "P1", "battlefield");
        }
        addStackFrame(record, "obj:burn", "P1", List.of(), List.of("create_devils"));

        Run run = reconstruct(
                record,
                "rg01-modal",
                modeBySemantic(Map.of("obj:burn", "Devil")),
                Map.of("P1", List.of(
                        "obj:red-1", "obj:red-2", "obj:red-3", "obj:red-4", "obj:red-5")));
        StackObject burn = stackBySemantic(run, "obj:burn");
        assertEquals(1, burn.getStackAbility().getModes().getSelectedModes().size());
    }

    @Test
    void nestedCounterspellTargetsExactLowerNativeStackObject() {
        JsonObject record = baseRecord("rg01-counter", 3);
        addObject(record, "obj:bolt", "Lightning Bolt", "P2", "P2", "stack");
        addObject(record, "obj:counter", "Counterspell", "P1", "P1", "stack");
        addObject(record, "obj:p2-red", "Mountain", "P2", "P2", "battlefield");
        addObject(record, "obj:p1-blue-a", "Island", "P1", "P1", "battlefield");
        addObject(record, "obj:p1-blue-b", "Island", "P1", "P1", "battlefield");
        // Frozen order is top -> bottom.
        addStackFrame(record, "obj:counter", "P1", List.of("obj:bolt"), List.of());
        addStackFrame(record, "obj:bolt", "P2", List.of("P1"), List.of());

        Run run = reconstruct(
                record,
                "rg01-counter",
                modeBySemantic(Map.of()),
                Map.of(
                        "P1", List.of("obj:p1-blue-a", "obj:p1-blue-b"),
                        "P2", List.of("obj:p2-red")));
        assertEquals(List.of("obj:counter", "obj:bolt"), semanticStackOrder(run));
        StackObject counter = stackBySemantic(run, "obj:counter");
        UUID boltStackId = run.result().nativeStackObjectIds().get("obj:bolt");
        List<UUID> targets = new ArrayList<>();
        counter.getStackAbility().getTargets().forEach(t -> targets.addAll(t.getTargets()));
        assertEquals(List.of(boltStackId), targets);
    }

    @Test
    void sameSeedFreshSessionsReconstructSameSemanticStack() {
        JsonObject record = baseRecord("rg01-replay", 4);
        addObject(record, "obj:bolt", "Lightning Bolt", "P1", "P1", "stack");
        addObject(record, "obj:red", "Mountain", "P1", "P1", "battlefield");
        addStackFrame(record, "obj:bolt", "P1", List.of("P3"), List.of());

        Run first = reconstruct(record, "rg01-replay-a",
                modeBySemantic(Map.of()), Map.of("P1", List.of("obj:red")));
        Run second = reconstruct(record, "rg01-replay-b",
                modeBySemantic(Map.of()), Map.of("P1", List.of("obj:red")));
        assertEquals(semanticStackSummary(first), semanticStackSummary(second));
        assertEquals(first.result().decisionClasses(), second.result().decisionClasses());
    }

    @Test
    void invalidOrControlDivergentFrozenStackFailsBeforeGameMutation() {
        JsonObject unknown = baseRecord("rg01-bad-source", 3);
        JsonObject frame = new JsonObject();
        frame.addProperty("source_semantic_id", "obj:missing");
        frame.addProperty("controller", "P1");
        frame.addProperty("cast_complete", true);
        frame.addProperty("costs_paid", true);
        frame.add("targets", new JsonArray());
        frame.add("modes", new JsonArray());
        unknown.getAsJsonArray("stack_state").add(frame);
        XmageCausalStackReconstruction.ReconstructionException e1 = assertThrows(
                XmageCausalStackReconstruction.ReconstructionException.class,
                () -> XmageCausalStackReconstruction.prepare(unknown, "bad", SEED));
        assertTrue(e1.getMessage().startsWith("UNBOUND_STACK_SOURCE"));

        JsonObject divergent = baseRecord("rg01-divergent", 3);
        addObject(divergent, "obj:bolt", "Lightning Bolt", "P1", "P2", "stack");
        addStackFrame(divergent, "obj:bolt", "P2", List.of("P1"), List.of());
        XmageCausalStackReconstruction.ReconstructionException e2 = assertThrows(
                XmageCausalStackReconstruction.ReconstructionException.class,
                () -> XmageCausalStackReconstruction.prepare(divergent, "bad2", SEED));
        assertTrue(e2.getMessage().startsWith("CONTROL_DIVERGENT_STACK_SOURCE"));
    }

    private static Run reconstruct(
            JsonObject record,
            String tag,
            Map<String, String> modeLabelBySemantic,
            Map<String, List<String>> manaSemanticOrderByPid
    ) {
        XmageCausalStackReconstruction.Prepared prepared =
                XmageCausalStackReconstruction.prepare(record, tag, SEED);
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = XmageNativeStateRestorationTest.importScaffolding(
                importer, prepared.preStackPlan(), tag);
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, SEED, importer, prepared.restoration());
        session.start();
        Map<String, Player> seats = session.restorationSeats();

        XmageCausalStackReconstruction.DecisionSource stackSource =
                (frame, pending, legal, index) -> {
                    String dc = pending.get("decision_class").getAsString();
                    if ("target".equals(dc)) {
                        return targetProposal(
                                tag + "-target-" + index,
                                frame,
                                legal,
                                prepared,
                                seats,
                                session);
                    }
                    if ("mode".equals(dc)) {
                        String needle = modeLabelBySemantic.get(frame.semanticId());
                        if (needle == null) {
                            return null;
                        }
                        return labelProposal(
                                tag + "-mode-" + index,
                                legal,
                                needle);
                    }
                    if ("mana_payment".equals(dc)) {
                        return manaProposal(
                                tag + "-mana-" + index,
                                frame.controller(),
                                legal,
                                prepared,
                                manaSemanticOrderByPid);
                    }
                    if ("choice".equals(dc)) {
                        // Single castable ability is normally recorded as a
                        // forced move by XmageFullGamePlayer. If an actual
                        // multi-ability card appears, the replay must supply a
                        // semantic choice instead of defaulting.
                        return null;
                    }
                    return null;
                };

        XmageCausalStackReconstruction.ReconstructionResult result =
                XmageCausalStackReconstruction.reconstruct(
                        session,
                        seats,
                        prepared,
                        arrivalSource(tag),
                        stackSource,
                        240);
        return new Run(session, seats, prepared, result);
    }

    private static XmageTemporalProgressionDriver.DecisionSource arrivalSource(String tag) {
        return (pending, legal, index) -> {
            String dc = pending.get("decision_class").getAsString();
            String actor = legal.get("actor_id").getAsString();
            if ("mulligan".equals(dc)) {
                return XmageCausalStackReconstruction.proposal(
                        tag + "-keep-" + index,
                        actor,
                        exactOptionType(legal, "mulligan", "keep"));
            }
            if ("choose_object".equals(dc)
                    && pending.has("prompt")
                    && pending.get("prompt").getAsString().contains("starting player")) {
                JsonObject match = null;
                for (JsonElement element : legal.getAsJsonArray("actions")) {
                    JsonObject action = element.getAsJsonObject();
                    if (action.get("action_id").getAsString().endsWith(":" + actor)) {
                        if (match != null) {
                            throw new AssertionError("ambiguous starting-player self option");
                        }
                        match = action;
                    }
                }
                if (match == null) {
                    throw new AssertionError("starting-player self option missing");
                }
                return XmageCausalStackReconstruction.proposal(
                        tag + "-start-" + index, actor, match);
            }
            if ("priority".equals(dc)) {
                return XmageCausalStackReconstruction.proposal(
                        tag + "-pass-" + index,
                        actor,
                        exactActionType(legal, "pass_priority"));
            }
            return null;
        };
    }

    private static JsonObject targetProposal(
            String proposalId,
            XmageCausalStackReconstruction.StackFrame frame,
            JsonObject legal,
            XmageCausalStackReconstruction.Prepared prepared,
            Map<String, Player> seats,
            XmageFullGameSession session
    ) {
        if (frame.targets().size() != 1) {
            return null;
        }
        String requested = frame.targets().get(0);
        String expectedNative = null;
        Player player = seats.get(requested);
        if (player != null) {
            expectedNative = player.getId().toString();
        } else if (isRequestedStackSource(prepared.requestedRecord(), requested)) {
            // Frozen stack targets name semantic source ids, but XMage
            // TargetSpell offers StackObject.getId(), not the underlying card
            // source UUID. Bind the unique live stack object by the exact
            // injected source UUID; never by card name.
            UUID sourceId = prepared.restoration().injectedObjectId(requested);
            List<StackObject> matches = new ArrayList<>();
            for (StackObject object : session.restorationGame().getStack()) {
                if (sourceId.equals(object.getSourceId())) {
                    matches.add(object);
                }
            }
            if (matches.size() == 1) {
                expectedNative = matches.get(0).getId().toString();
            } else if (matches.size() > 1) {
                throw new AssertionError(
                        "ambiguous live stack object for semantic source " + requested);
            }
        } else {
            expectedNative = prepared.restoration().injectedObjectId(requested).toString();
        }
        if (expectedNative == null) {
            return null;
        }
        JsonObject match = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            JsonObject meta = action.getAsJsonObject("metadata")
                    .getAsJsonObject("xmage_option_metadata");
            if (!meta.has("object_id")
                    || !expectedNative.equals(meta.get("object_id").getAsString())) {
                continue;
            }
            if (match != null) {
                throw new AssertionError("ambiguous exact target " + requested);
            }
            match = action;
        }
        if (match == null) {
            throw new AssertionError("required target not offered: " + requested);
        }
        return XmageCausalStackReconstruction.proposal(
                proposalId,
                legal.get("actor_id").getAsString(),
                match);
    }

    private static JsonObject manaProposal(
            String proposalId,
            String pid,
            JsonObject legal,
            XmageCausalStackReconstruction.Prepared prepared,
            Map<String, List<String>> semanticOrderByPid
    ) {
        List<String> order = semanticOrderByPid.getOrDefault(pid, List.of());
        for (String semantic : order) {
            UUID sourceId = prepared.restoration().injectedObjectId(semantic);
            for (JsonElement element : legal.getAsJsonArray("actions")) {
                JsonObject action = element.getAsJsonObject();
                JsonObject metadata = action.getAsJsonObject("metadata");
                if (!metadata.has("xmage_option_metadata")) {
                    continue;
                }
                JsonObject engine = metadata.getAsJsonObject("xmage_option_metadata");
                String optionType = metadata.get("option_type").getAsString();
                if ("mana_ability".equals(optionType)
                        && engine.has("source_object_id")
                        && sourceId.toString().equals(
                                engine.get("source_object_id").getAsString())) {
                    return XmageCausalStackReconstruction.proposal(
                            proposalId,
                            legal.get("actor_id").getAsString(),
                            action);
                }
            }
        }
        List<JsonObject> pool = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if ("mana_pool".equals(action.getAsJsonObject("metadata")
                    .get("option_type").getAsString())) {
                pool.add(action);
            }
        }
        if (pool.size() == 1) {
            return XmageCausalStackReconstruction.proposal(
                    proposalId,
                    legal.get("actor_id").getAsString(),
                    pool.get(0));
        }
        return null;
    }

    private static Map<String, String> modeBySemantic(Map<String, String> values) {
        return values;
    }

    private static JsonObject labelProposal(
            String proposalId,
            JsonObject legal,
            String needle
    ) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            String label = action.getAsJsonObject("metadata").get("label").getAsString();
            if (label.contains(needle)) {
                matches.add(action);
            }
        }
        if (matches.size() != 1) {
            throw new AssertionError("mode label match " + needle + " count=" + matches.size());
        }
        return XmageCausalStackReconstruction.proposal(
                proposalId,
                legal.get("actor_id").getAsString(),
                matches.get(0));
    }

    private static JsonObject exactActionType(JsonObject legal, String type) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (type.equals(action.get("action_type").getAsString())) {
                matches.add(action);
            }
        }
        if (matches.size() != 1) {
            throw new AssertionError(type + " action count=" + matches.size());
        }
        return matches.get(0);
    }

    private static JsonObject exactOptionType(
            JsonObject legal,
            String actionType,
            String optionType
    ) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!actionType.equals(action.get("action_type").getAsString())) {
                continue;
            }
            JsonObject meta = action.getAsJsonObject("metadata");
            if (optionType.equals(meta.get("option_type").getAsString())) {
                matches.add(action);
            }
        }
        if (matches.size() != 1) {
            throw new AssertionError(
                    actionType + "/" + optionType + " action count=" + matches.size());
        }
        return matches.get(0);
    }

    private static StackObject stackBySemantic(Run run, String semantic) {
        UUID id = run.result().nativeStackObjectIds().get(semantic);
        for (StackObject object : run.session().restorationGame().getStack()) {
            if (object.getId().equals(id)) {
                return object;
            }
        }
        throw new AssertionError("stack object missing: " + semantic);
    }

    private static List<String> semanticStackOrder(Run run) {
        Map<UUID, String> semanticById = new LinkedHashMap<>();
        run.result().nativeStackObjectIds().forEach(
                (semantic, id) -> semanticById.put(id, semantic));
        List<String> result = new ArrayList<>();
        for (StackObject object : run.session().restorationGame().getStack()) {
            if (semanticById.containsKey(object.getId())) {
                result.add(semanticById.get(object.getId()));
            }
        }
        return result;
    }

    private static List<String> semanticStackSummary(Run run) {
        List<String> result = new ArrayList<>();
        for (String semantic : semanticStackOrder(run)) {
            StackObject object = stackBySemantic(run, semantic);
            List<String> targets = new ArrayList<>();
            object.getStackAbility().getTargets().forEach(
                    t -> t.getTargets().forEach(id -> {
                        String pid = pidOf(run.seats(), id);
                        targets.add(pid == null ? "object" : pid);
                    }));
            targets.sort(Comparator.naturalOrder());
            result.add(semantic + "|" + object.getName() + "|" + targets
                    + "|modes=" + object.getStackAbility().getModes().getSelectedModes().size());
        }
        return result;
    }

    private static String pidOf(Map<String, Player> seats, UUID id) {
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            if (entry.getValue().getId().equals(id)) {
                return entry.getKey();
            }
        }
        return null;
    }

    private static JsonObject baseRecord(String fixtureId, int playerCount) {
        JsonObject record = new JsonObject();
        record.addProperty("fixture_id", fixtureId);
        JsonArray players = new JsonArray();
        JsonArray commanders = new JsonArray();
        for (int seat = 1; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            JsonObject player = new JsonObject();
            player.addProperty("player_id", pid);
            player.addProperty("seat", seat);
            player.addProperty("life", 40);
            player.addProperty("poison", 0);
            players.add(player);

            JsonObject commander = new JsonObject();
            commander.addProperty("commander_id", "cmd:" + pid);
            commander.addProperty("card_identity", "Rograkh, Son of Rohgahh");
            commander.addProperty("owner", pid);
            commander.addProperty("prior_command_zone_cast_count", 0);
            commanders.add(commander);
        }
        record.add("players", players);
        JsonObject commanderState = new JsonObject();
        commanderState.add("commanders", commanders);
        commanderState.add("commander_damage_matrix", new JsonArray());
        commanderState.add("multiple_commander_relations", new JsonArray());
        record.add("commander_state", commanderState);
        record.add("semantic_objects", new JsonArray());
        record.add("stack_state", new JsonArray());
        JsonObject temporal = new JsonObject();
        temporal.addProperty("turn_number", 1);
        temporal.addProperty("phase", "precombat_main");
        temporal.addProperty("step", "main");
        temporal.addProperty("active_player", "P1");
        temporal.addProperty("priority_player", "P1");
        temporal.add("extra_turn_queue", new JsonArray());
        record.add("temporal_state", temporal);
        return record;
    }

    private static void addObject(
            JsonObject record,
            String semanticId,
            String card,
            String owner,
            String controller,
            String zone
    ) {
        JsonObject object = new JsonObject();
        object.addProperty("semantic_id", semanticId);
        object.addProperty("card_identity", card);
        object.addProperty("owner", owner);
        object.addProperty("controller", controller);
        object.addProperty("zone", zone);
        object.addProperty("tapped", false);
        object.add("counters", new JsonObject());
        object.add("attachments", new JsonArray());
        object.addProperty("face_down", false);
        record.getAsJsonArray("semantic_objects").add(object);
    }

    private static void addStackFrame(
            JsonObject record,
            String semanticId,
            String controller,
            List<String> targets,
            List<String> modes
    ) {
        JsonObject frame = new JsonObject();
        frame.addProperty("source_semantic_id", semanticId);
        frame.addProperty("controller", controller);
        frame.addProperty("cast_complete", true);
        frame.addProperty("costs_paid", true);
        JsonArray targetArray = new JsonArray();
        targets.forEach(targetArray::add);
        frame.add("targets", targetArray);
        JsonArray modeArray = new JsonArray();
        modes.forEach(modeArray::add);
        frame.add("modes", modeArray);
        record.getAsJsonArray("stack_state").add(frame);
    }

    private static boolean isRequestedStackSource(
            JsonObject record,
            String semanticId
    ) {
        for (JsonElement element : record.getAsJsonArray("stack_state")) {
            JsonObject frame = element.getAsJsonObject();
            if (semanticId.equals(frame.get("source_semantic_id").getAsString())) {
                return true;
            }
        }
        return false;
    }

    private static JsonObject semanticObject(JsonObject record, String semanticId) {
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            if (semanticId.equals(object.get("semantic_id").getAsString())) {
                return object;
            }
        }
        throw new AssertionError("semantic object missing: " + semanticId);
    }

    private record Run(
            XmageFullGameSession session,
            Map<String, Player> seats,
            XmageCausalStackReconstruction.Prepared prepared,
            XmageCausalStackReconstruction.ReconstructionResult result
    ) {
    }
}

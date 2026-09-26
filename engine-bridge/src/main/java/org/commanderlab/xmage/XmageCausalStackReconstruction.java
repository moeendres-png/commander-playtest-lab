package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.stack.StackObject;
import mage.players.Player;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * RG-01 causal stack reconstruction.
 *
 * <p>A requested stack is never inserted with SpellStack.push and never
 * materialized as a fabricated Spell/StackAbility. The frozen stack is first
 * converted into a pre-causal state in which its source cards exist in hand.
 * The running engine then casts/activates/creates triggers normally via the
 * existing decision-scoped LegalAction/ActionProposal path. This class only
 * binds semantic history to native objects and validates the reached
 * checkpoint.</p>
 */
final class XmageCausalStackReconstruction {

    static final class ReconstructionException extends RuntimeException {
        ReconstructionException(String code, String detail) {
            super(code + ": " + detail);
        }
    }

    /**
     * Frozen stack frames are stored top-to-bottom. Prepared frames are
     * bottom-to-top so replay reconstructs causality in legal order.
     */
    record StackFrame(
            String semanticId,
            String cardIdentity,
            String owner,
            String controller,
            List<String> targets,
            List<String> modes
    ) {
    }

    record Prepared(
            String fixtureId,
            JsonObject requestedRecord,
            XmageNativeStateRestoration.Plan preStackPlan,
            XmageNativeStateRestoration restoration,
            List<StackFrame> bottomToTop
    ) {
    }

    record ReconstructionResult(
            Map<String, UUID> nativeStackObjectIds,
            int submittedDecisions,
            List<String> decisionClasses
    ) {
    }

    /**
     * External reconstruction decision source.
     *
     * <p>The source receives the exact current native decision and authoritative
     * offered actions. Returning null is a hard unsupported-path signal; there
     * is no fallback/default answer.</p>
     */
    @FunctionalInterface
    interface DecisionSource {
        JsonObject choose(
                StackFrame frame,
                JsonObject pendingDecision,
                JsonObject legalActions,
                int decisionIndex
        );
    }

    private XmageCausalStackReconstruction() {
    }

    static Prepared prepare(JsonObject frozenRecord, String planId, long seed) {
        if (frozenRecord == null) {
            throw new ReconstructionException("INVALID_RECORD", "record is null");
        }
        JsonObject record = frozenRecord.deepCopy();
        String fixtureId = requiredText(record, "fixture_id");
        if (!record.has("stack_state") || !record.get("stack_state").isJsonArray()) {
            throw new ReconstructionException("MISSING_STACK_STATE", fixtureId);
        }
        JsonArray stack = record.getAsJsonArray("stack_state");
        if (stack.isEmpty()) {
            throw new ReconstructionException("EMPTY_STACK_STATE", fixtureId);
        }

        Map<String, JsonObject> objects = new LinkedHashMap<>();
        for (JsonElement element : record.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            String semanticId = requiredText(object, "semantic_id");
            if (objects.put(semanticId, object) != null) {
                throw new ReconstructionException(
                        "DUPLICATE_SEMANTIC_OBJECT", semanticId);
            }
        }

        List<StackFrame> topToBottom = new ArrayList<>();
        Set<String> stackSources = new LinkedHashSet<>();
        for (JsonElement element : stack) {
            JsonObject frame = element.getAsJsonObject();
            String semanticId = requiredText(frame, "source_semantic_id");
            if (!stackSources.add(semanticId)) {
                throw new ReconstructionException(
                        "DUPLICATE_STACK_SOURCE", semanticId);
            }
            if (!frame.has("cast_complete") || !frame.get("cast_complete").getAsBoolean()) {
                throw new ReconstructionException(
                        "UNSUPPORTED_INCOMPLETE_CAST", semanticId);
            }
            if (!frame.has("costs_paid") || !frame.get("costs_paid").getAsBoolean()) {
                throw new ReconstructionException(
                        "UNSUPPORTED_UNPAID_STACK_OBJECT", semanticId);
            }
            JsonObject source = objects.get(semanticId);
            if (source == null) {
                throw new ReconstructionException(
                        "UNBOUND_STACK_SOURCE", semanticId);
            }
            if (!"stack".equals(requiredText(source, "zone"))) {
                throw new ReconstructionException(
                        "STACK_SOURCE_ZONE_MISMATCH",
                        semanticId + " zone=" + requiredText(source, "zone"));
            }
            String owner = requiredText(source, "owner");
            String controller = requiredText(frame, "controller");
            String objectController = requiredText(source, "controller");
            if (!controller.equals(objectController)) {
                throw new ReconstructionException(
                        "STACK_CONTROLLER_MISMATCH",
                        semanticId + " frame=" + controller + " object=" + objectController);
            }
            // Casting a card owned by another player is a control/access
            // history problem owned by RG-04. Do not silently invent access.
            if (!owner.equals(controller)) {
                throw new ReconstructionException(
                        "CONTROL_DIVERGENT_STACK_SOURCE", semanticId);
            }

            List<String> targets = stringList(frame, "targets");
            List<String> modes = stringList(frame, "modes");
            topToBottom.add(new StackFrame(
                    semanticId,
                    requiredText(source, "card_identity"),
                    owner,
                    controller,
                    targets,
                    modes
            ));

            // Pre-causal materialization: the same physical card exists in
            // hand. The later transition to stack must be a real cast.
            source.addProperty("zone", "hand");
        }

        // Validate target referents before any engine mutation. A target may
        // name a player, a normal semantic object, or a lower stack object.
        Set<String> players = new LinkedHashSet<>();
        for (JsonElement element : record.getAsJsonArray("players")) {
            players.add(requiredText(element.getAsJsonObject(), "player_id"));
        }
        for (StackFrame frame : topToBottom) {
            for (String target : frame.targets()) {
                if (!players.contains(target) && !objects.containsKey(target)
                        && !stackSources.contains(target)) {
                    throw new ReconstructionException(
                            "UNBOUND_STACK_TARGET",
                            frame.semanticId() + " -> " + target);
                }
            }
        }

        // Restoration itself must arrive before any reconstructed stack
        // history. Natural turn priority belongs to the active player; later
        // casters receive priority only by explicit scripted passes.
        JsonObject temporal = record.getAsJsonObject("temporal_state");
        temporal.addProperty(
                "priority_player",
                requiredText(temporal, "active_player"));

        // The restoration parser deliberately never sees a stack zone.
        // Keeping the requested stack array is safe (it is not consumed by
        // restoration), but clearing it makes the boundary auditable.
        record.add("stack_state", new JsonArray());

        final XmageNativeStateRestoration.Plan plan;
        try {
            plan = XmageNativeStateRestoration.planFromFrozenRecord(
                    record, planId, seed);
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            throw new ReconstructionException(
                    "PRESTACK_RESTORATION_UNSUPPORTED", exc.getMessage());
        }

        List<String> identities = plan.objects().stream()
                .map(XmageNativeStateRestoration.RequestedObject::cardIdentity)
                .toList();
        XmageNativeStateRestoration restoration =
                new XmageNativeStateRestoration(
                        plan,
                        XmageNativeStateRestoration.materializeCards(identities));

        List<StackFrame> bottomToTop = new ArrayList<>(topToBottom);
        Collections.reverse(bottomToTop);
        return new Prepared(
                fixtureId,
                frozenRecord.deepCopy(),
                plan,
                restoration,
                List.copyOf(bottomToTop));
    }

    /**
     * Reconstructs every prepared stack frame using live native decisions.
     *
     * <p>The session must have been constructed with {@link Prepared#restoration}
     * and started. This method first reaches the pre-stack temporal checkpoint
     * through RG-03 native progression, restores Commander history, then
     * replays frames bottom-to-top. Priority passes used solely to hand
     * priority to the known next historical caster are exact semantic
     * pass-priority selections, never first-option/default fallbacks.</p>
     */
    static ReconstructionResult reconstruct(
            XmageFullGameSession session,
            Map<String, Player> seats,
            Prepared prepared,
            XmageTemporalProgressionDriver.DecisionSource temporalSource,
            DecisionSource decisionSource,
            int maxDecisions
    ) {
        if (session == null || seats == null || prepared == null
                || temporalSource == null || decisionSource == null) {
            throw new ReconstructionException(
                    "INVALID_RECONSTRUCTION_INPUT", "null reconstruction input");
        }
        if (maxDecisions < 1) {
            throw new ReconstructionException(
                    "INVALID_DECISION_BOUND", String.valueOf(maxDecisions));
        }

        XmageTemporalProgressionDriver.driveToPlanTarget(
                session,
                seats,
                prepared.preStackPlan(),
                temporalSource,
                maxDecisions);
        prepared.restoration().restoreCommanderCasts(
                session.restorationGame(), seats);
        XmageNativeStateRestoration.revalidate(session.restorationGame());

        Map<String, UUID> stackIds = new LinkedHashMap<>();
        List<String> classes = new ArrayList<>();
        int decisions = 0;

        for (StackFrame frame : prepared.bottomToTop()) {
            // Hand priority to the historical caster through explicit passes.
            for (;;) {
                JsonObject pending = pending(session);
                String actorPid = pidOf(seats, requiredText(pending, "actor_id"));
                if (frame.controller().equals(actorPid)) {
                    break;
                }
                requireDecisionClass(pending, "priority");
                JsonObject legal = session.legalActionsPayload();
                session.submitAction(exactPassProposal(
                        "rg01-pass-" + decisions,
                        legal));
                classes.add("priority");
                decisions++;
                requireBound(decisions, maxDecisions);
            }

            UUID sourceId = prepared.restoration()
                    .injectedObjectId(frame.semanticId());
            JsonObject castLegal = session.legalActionsPayload();
            requireDecisionClass(
                    session.pendingDecisionPayload().getAsJsonObject("decision"),
                    "priority");
            JsonObject castAction = exactSourceAction(castLegal, sourceId);
            session.submitAction(proposal(
                    "rg01-cast-" + decisions,
                    castLegal.get("actor_id").getAsString(),
                    castAction));
            classes.add("priority");
            decisions++;
            requireBound(decisions, maxDecisions);

            // The card can move onto the stack before targets/modes/payment are
            // complete. A frame is complete only once native priority returns
            // with the exact source still on stack; every intermediate
            // decision comes from the external replay source.
            for (;;) {
                StackObject stackObject =
                        stackObjectBySource(session, sourceId);
                JsonObject payload = session.pendingDecisionPayload();
                if (stackObject != null
                        && !payload.get("decision").isJsonNull()
                        && "priority".equals(payload.getAsJsonObject("decision")
                                .get("decision_class").getAsString())) {
                    validateFrame(
                            session, seats, prepared, frame, stackObject, stackIds);
                    stackIds.put(frame.semanticId(), stackObject.getId());
                    break;
                }
                if (payload.get("decision").isJsonNull()) {
                    throw new ReconstructionException(
                            "ENGINE_TERMINAL_DURING_CAST", frame.semanticId());
                }
                JsonObject pending = payload.getAsJsonObject("decision");
                JsonObject legal = session.legalActionsPayload();
                JsonObject chosen = decisionSource.choose(
                        frame, pending.deepCopy(), legal.deepCopy(), decisions);
                if (chosen == null) {
                    throw new ReconstructionException(
                            "UNSCRIPTED_STACK_DECISION",
                            frame.semanticId() + " " + requiredText(pending, "decision_class"));
                }
                classes.add(requiredText(pending, "decision_class"));
                session.submitAction(chosen);
                decisions++;
                requireBound(decisions, maxDecisions);
            }
        }

        // Final top-to-bottom source ordering must match the frozen request.
        List<String> expectedTopToBottom = new ArrayList<>();
        for (JsonElement element
                : prepared.requestedRecord().getAsJsonArray("stack_state")) {
            expectedTopToBottom.add(
                    requiredText(element.getAsJsonObject(), "source_semantic_id"));
        }
        List<String> actualTopToBottom =
                semanticStackOrder(session, stackIds);
        if (!expectedTopToBottom.equals(actualTopToBottom)) {
            throw new ReconstructionException(
                    "STACK_ORDER_MISMATCH",
                    "expected=" + expectedTopToBottom + " actual=" + actualTopToBottom);
        }

        return new ReconstructionResult(
                Map.copyOf(stackIds),
                decisions,
                List.copyOf(classes));
    }

    private static void validateFrame(
            XmageFullGameSession session,
            Map<String, Player> seats,
            Prepared prepared,
            StackFrame frame,
            StackObject stackObject,
            Map<String, UUID> earlierStackIds
    ) {
        String controller = pidOf(seats, stackObject.getControllerId().toString());
        if (!frame.controller().equals(controller)) {
            throw new ReconstructionException(
                    "STACK_CONTROLLER_MISMATCH",
                    frame.semanticId() + " expected=" + frame.controller()
                            + " actual=" + controller);
        }
        if (!frame.cardIdentity().equals(stackObject.getName())) {
            throw new ReconstructionException(
                    "STACK_IDENTITY_MISMATCH",
                    frame.semanticId() + " expected=" + frame.cardIdentity()
                            + " actual=" + stackObject.getName());
        }

        List<UUID> expectedTargets = new ArrayList<>();
        for (String target : frame.targets()) {
            Player player = seats.get(target);
            if (player != null) {
                expectedTargets.add(player.getId());
                continue;
            }
            UUID stackId = earlierStackIds.get(target);
            if (stackId != null) {
                expectedTargets.add(stackId);
                continue;
            }
            expectedTargets.add(prepared.restoration().injectedObjectId(target));
        }

        List<UUID> actualTargets = new ArrayList<>();
        if (stackObject.getStackAbility() != null) {
            stackObject.getStackAbility().getTargets().forEach(
                    target -> actualTargets.addAll(target.getTargets()));
        }
        if (!multiset(expectedTargets).equals(multiset(actualTargets))) {
            throw new ReconstructionException(
                    "STACK_TARGET_MISMATCH",
                    frame.semanticId() + " expected=" + expectedTargets
                            + " actual=" + actualTargets);
        }

        if (stackObject.getStackAbility() == null) {
            if (!frame.modes().isEmpty()) {
                throw new ReconstructionException(
                        "STACK_MODE_MISMATCH",
                        frame.semanticId() + " has requested modes but no stack ability");
            }
            return;
        }
        // XMage's internal Modes always contains/selects the ordinary
        // default mode for a nonmodal spell. Frozen modes=[] means "no
        // discretionary modal choice", not "zero internal modes". Only an
        // explicitly mode-bearing frozen frame constrains selected-mode
        // cardinality here; mode identity itself remains native-decision
        // evidence supplied/checked by the actual cast path.
        if (!frame.modes().isEmpty()) {
            int selectedModes =
                    stackObject.getStackAbility().getModes().getSelectedModes().size();
            if (selectedModes != frame.modes().size()) {
                throw new ReconstructionException(
                        "STACK_MODE_COUNT_MISMATCH",
                        frame.semanticId() + " expected=" + frame.modes().size()
                                + " actual=" + selectedModes);
            }
        }
    }

    private static Map<UUID, Integer> multiset(List<UUID> ids) {
        Map<UUID, Integer> counts = new LinkedHashMap<>();
        for (UUID id : ids) {
            counts.merge(id, 1, Integer::sum);
        }
        return counts;
    }

    private static List<String> semanticStackOrder(
            XmageFullGameSession session,
            Map<String, UUID> stackIds
    ) {
        Map<UUID, String> semanticByNative = new LinkedHashMap<>();
        stackIds.forEach((semantic, nativeId) -> semanticByNative.put(nativeId, semantic));
        List<String> order = new ArrayList<>();
        for (StackObject object : session.restorationGame().getStack()) {
            String semantic = semanticByNative.get(object.getId());
            if (semantic != null) {
                order.add(semantic);
            }
        }
        return order;
    }

    private static StackObject stackObjectBySource(
            XmageFullGameSession session,
            UUID sourceId
    ) {
        StackObject found = null;
        for (StackObject object : session.restorationGame().getStack()) {
            if (!sourceId.equals(object.getSourceId())) {
                continue;
            }
            if (found != null) {
                throw new ReconstructionException(
                        "AMBIGUOUS_NATIVE_STACK_SOURCE", sourceId.toString());
            }
            found = object;
        }
        return found;
    }

    private static JsonObject exactSourceAction(JsonObject legal, UUID sourceId) {
        List<JsonObject> matches = new ArrayList<>();
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!action.has("metadata")
                    || !action.get("metadata").isJsonObject()) {
                continue;
            }
            JsonObject metadata = action.getAsJsonObject("metadata");
            if (!metadata.has("xmage_option_metadata")
                    || !metadata.get("xmage_option_metadata").isJsonObject()) {
                continue;
            }
            JsonObject engine = metadata.getAsJsonObject("xmage_option_metadata");
            if (engine.has("source_object_id")
                    && sourceId.toString().equals(
                            engine.get("source_object_id").getAsString())
                    && engine.has("ability_type")
                    && "spell".equals(engine.get("ability_type").getAsString())) {
                matches.add(action);
            }
        }
        if (matches.size() != 1) {
            throw new ReconstructionException(
                    "CAST_OFFER_BINDING_FAILED",
                    sourceId + " matches=" + matches.size());
        }
        return matches.get(0);
    }

    private static JsonObject exactPassProposal(String proposalId, JsonObject legal) {
        JsonObject match = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!"pass_priority".equals(action.get("action_type").getAsString())) {
                continue;
            }
            if (match != null) {
                throw new ReconstructionException(
                        "AMBIGUOUS_PASS_PRIORITY", requiredText(legal, "decision_id"));
            }
            match = action;
        }
        if (match == null) {
            throw new ReconstructionException(
                    "MISSING_PASS_PRIORITY", requiredText(legal, "decision_id"));
        }
        return proposal(
                proposalId,
                requiredText(legal, "actor_id"),
                match);
    }

    static JsonObject proposal(String proposalId, String actor, JsonObject action) {
        if (action == null) {
            throw new ReconstructionException("INVALID_ACTION", "action is null");
        }
        JsonObject proposal = new JsonObject();
        proposal.addProperty("proposal_id", proposalId);
        proposal.addProperty("actor_id", actor);
        proposal.addProperty("legal_action_id",
                requiredText(action, "action_id"));
        proposal.addProperty("action_type",
                requiredText(action, "action_type"));
        proposal.add("target_ids", new JsonArray());
        proposal.add("selected_modes", new JsonArray());
        JsonObject choices = new JsonObject();
        choices.add("ordering", new JsonArray());
        proposal.add("choices", choices);
        proposal.addProperty("decision_tier", 1);
        proposal.addProperty("policy_name", "rg01-causal-stack-reconstruction");
        return proposal;
    }

    private static JsonObject pending(XmageFullGameSession session) {
        JsonObject payload = session.pendingDecisionPayload();
        if (payload.get("decision").isJsonNull()) {
            throw new ReconstructionException(
                    "ENGINE_TERMINAL_DURING_RECONSTRUCTION", "no pending decision");
        }
        return payload.getAsJsonObject("decision");
    }

    private static void requireDecisionClass(JsonObject pending, String expected) {
        String actual = requiredText(pending, "decision_class");
        if (!expected.equals(actual)) {
            throw new ReconstructionException(
                    "UNEXPECTED_DECISION_CLASS",
                    "expected=" + expected + " actual=" + actual);
        }
    }

    private static void requireBound(int decisions, int max) {
        if (decisions > max) {
            throw new ReconstructionException(
                    "STACK_RECONSTRUCTION_BOUND_EXCEEDED",
                    decisions + ">" + max);
        }
    }

    private static String pidOf(Map<String, Player> seats, String nativeId) {
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            if (entry.getValue().getId().toString().equals(nativeId)) {
                return entry.getKey();
            }
        }
        throw new ReconstructionException(
                "UNKNOWN_NATIVE_PLAYER", nativeId);
    }

    private static List<String> stringList(JsonObject object, String key) {
        if (!object.has(key) || object.get(key).isJsonNull()) {
            return List.of();
        }
        if (!object.get(key).isJsonArray()) {
            throw new ReconstructionException(
                    "INVALID_STACK_FIELD", key + " must be array");
        }
        List<String> values = new ArrayList<>();
        for (JsonElement element : object.getAsJsonArray(key)) {
            values.add(element.getAsString());
        }
        return List.copyOf(values);
    }

    private static String requiredText(JsonObject object, String key) {
        if (object == null || !object.has(key) || object.get(key).isJsonNull()) {
            throw new ReconstructionException(
                    "INVALID_STACK_FIELD", "missing " + key);
        }
        String value = object.get(key).getAsString();
        if (value.isBlank()) {
            throw new ReconstructionException(
                    "INVALID_STACK_FIELD", "blank " + key);
        }
        return value;
    }
}

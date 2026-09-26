package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.game.stack.StackObject;
import mage.players.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * RG-04 causal owner/controller divergence.
 *
 * <p>This class never assigns a Permanent controller field and never injects a
 * continuous effect. A source card must already exist in authoritative engine
 * state, the exact live spell offer must exist, and every target/mode/payment
 * decision must come from the external decision source. The engine creates and
 * removes all continuous control effects.</p>
 */
final class XmageControlDivergenceReconstruction {

    static final class ControlException extends RuntimeException {
        ControlException(String code, String detail) {
            super(code + ": " + detail);
        }
    }

    @FunctionalInterface
    interface DecisionSource {
        JsonObject choose(JsonObject pendingDecision, JsonObject legalActions, int decisionIndex);
    }

    record Result(int submittedDecisions, List<String> decisionClasses) {
    }

    private XmageControlDivergenceReconstruction() {
    }

    static Result castAndResolve(
            XmageFullGameSession session,
            Map<String, Player> seats,
            String actorPid,
            UUID sourceCardId,
            DecisionSource decisionSource,
            int maxDecisions
    ) {
        if (session == null || seats == null || actorPid == null
                || sourceCardId == null || decisionSource == null) {
            throw new ControlException("INVALID_CONTROL_INPUT", "null input");
        }
        if (!seats.containsKey(actorPid)) {
            throw new ControlException("UNKNOWN_ACTOR", actorPid);
        }
        if (maxDecisions < 1) {
            throw new ControlException("INVALID_DECISION_BOUND", String.valueOf(maxDecisions));
        }

        List<String> classes = new ArrayList<>();
        int decisions = 0;

        // Hand priority to the explicitly named actor through exact pass offers.
        for (;;) {
            JsonObject pending = pending(session);
            String currentPid = pidOf(seats, requiredText(pending, "actor_id"));
            if (actorPid.equals(currentPid)) {
                break;
            }
            requireClass(pending, "priority");
            JsonObject legal = session.legalActionsPayload();
            session.submitAction(passProposal("rg04-pass-" + decisions, legal));
            classes.add("priority");
            decisions++;
            requireBound(decisions, maxDecisions);
        }

        JsonObject pending = pending(session);
        requireClass(pending, "priority");
        JsonObject legal = session.legalActionsPayload();
        JsonObject cast = exactSpellOffer(legal, sourceCardId);
        session.submitAction(XmageCausalStackReconstruction.proposal(
                "rg04-cast-" + decisions,
                requiredText(legal, "actor_id"),
                cast));
        classes.add("priority");
        decisions++;
        requireBound(decisions, maxDecisions);

        // Complete the cast transaction. No hidden/default choice is supplied.
        for (;;) {
            StackObject live = stackObjectBySource(session, sourceCardId);
            JsonObject payload = session.pendingDecisionPayload();
            if (live != null
                    && !payload.get("decision").isJsonNull()
                    && "priority".equals(payload.getAsJsonObject("decision")
                            .get("decision_class").getAsString())) {
                break;
            }
            if (payload.get("decision").isJsonNull()) {
                throw new ControlException(
                        "ENGINE_TERMINAL_DURING_CONTROL_CAST", sourceCardId.toString());
            }
            JsonObject castPending = payload.getAsJsonObject("decision");
            JsonObject castLegal = session.legalActionsPayload();
            JsonObject proposal = decisionSource.choose(
                    castPending.deepCopy(), castLegal.deepCopy(), decisions);
            if (proposal == null) {
                throw new ControlException(
                        "UNSCRIPTED_CONTROL_DECISION",
                        requiredText(castPending, "decision_class"));
            }
            classes.add(requiredText(castPending, "decision_class"));
            session.submitAction(proposal);
            decisions++;
            requireBound(decisions, maxDecisions);
        }

        // Resolve the actual native stack object. Any non-priority decision
        // produced while resolving remains externally owned and fail-closed.
        for (;;) {
            StackObject live = stackObjectBySource(session, sourceCardId);
            JsonObject payload = session.pendingDecisionPayload();
            if (live == null && session.restorationGame().getStack().isEmpty()) {
                XmageNativeStateRestoration.revalidate(session.restorationGame());
                return new Result(decisions, List.copyOf(classes));
            }
            if (payload.get("decision").isJsonNull()) {
                throw new ControlException(
                        "ENGINE_TERMINAL_DURING_CONTROL_RESOLUTION",
                        sourceCardId.toString());
            }
            JsonObject resolvePending = payload.getAsJsonObject("decision");
            JsonObject resolveLegal = session.legalActionsPayload();
            String decisionClass = requiredText(resolvePending, "decision_class");
            final JsonObject proposal;
            if ("priority".equals(decisionClass)) {
                proposal = passProposal("rg04-resolve-" + decisions, resolveLegal);
            } else {
                proposal = decisionSource.choose(
                        resolvePending.deepCopy(), resolveLegal.deepCopy(), decisions);
                if (proposal == null) {
                    throw new ControlException(
                            "UNSCRIPTED_CONTROL_DECISION", decisionClass);
                }
            }
            classes.add(decisionClass);
            session.submitAction(proposal);
            decisions++;
            requireBound(decisions, maxDecisions);
        }
    }

    static void requireOwnerController(
            XmageFullGameSession session,
            UUID permanentId,
            UUID expectedOwner,
            UUID expectedController
    ) {
        var permanent = session.restorationGame().getPermanent(permanentId);
        if (permanent == null) {
            throw new ControlException("PERMANENT_MISSING", permanentId.toString());
        }
        if (!expectedOwner.equals(permanent.getOwnerId())) {
            throw new ControlException(
                    "OWNER_MISMATCH",
                    permanentId + " expected=" + expectedOwner
                            + " actual=" + permanent.getOwnerId());
        }
        if (!expectedController.equals(permanent.getControllerId())) {
            throw new ControlException(
                    "CONTROLLER_MISMATCH",
                    permanentId + " expected=" + expectedController
                            + " actual=" + permanent.getControllerId());
        }
    }

    private static StackObject stackObjectBySource(
            XmageFullGameSession session,
            UUID sourceCardId
    ) {
        StackObject found = null;
        for (StackObject object : session.restorationGame().getStack()) {
            if (!sourceCardId.equals(object.getSourceId())) {
                continue;
            }
            if (found != null) {
                throw new ControlException(
                        "AMBIGUOUS_CONTROL_SOURCE", sourceCardId.toString());
            }
            found = object;
        }
        return found;
    }

    private static JsonObject exactSpellOffer(JsonObject legal, UUID sourceCardId) {
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
            if (sourceCardId.toString().equals(
                        textOrEmpty(engine, "source_object_id"))
                    && "spell".equals(textOrEmpty(engine, "ability_type"))) {
                matches.add(action);
            }
        }
        if (matches.size() != 1) {
            throw new ControlException(
                    "CONTROL_CAST_OFFER_BINDING_FAILED",
                    sourceCardId + " matches=" + matches.size());
        }
        return matches.get(0);
    }

    private static JsonObject passProposal(String proposalId, JsonObject legal) {
        JsonObject match = null;
        for (JsonElement element : legal.getAsJsonArray("actions")) {
            JsonObject action = element.getAsJsonObject();
            if (!"pass_priority".equals(requiredText(action, "action_type"))) {
                continue;
            }
            if (match != null) {
                throw new ControlException(
                        "AMBIGUOUS_PASS_PRIORITY", requiredText(legal, "decision_id"));
            }
            match = action;
        }
        if (match == null) {
            throw new ControlException(
                    "MISSING_PASS_PRIORITY", requiredText(legal, "decision_id"));
        }
        return XmageCausalStackReconstruction.proposal(
                proposalId, requiredText(legal, "actor_id"), match);
    }

    private static JsonObject pending(XmageFullGameSession session) {
        JsonObject payload = session.pendingDecisionPayload();
        if (payload.get("decision").isJsonNull()) {
            throw new ControlException("ENGINE_TERMINAL", "no pending decision");
        }
        return payload.getAsJsonObject("decision");
    }

    private static void requireClass(JsonObject pending, String expected) {
        String actual = requiredText(pending, "decision_class");
        if (!expected.equals(actual)) {
            throw new ControlException(
                    "UNEXPECTED_DECISION_CLASS",
                    "expected=" + expected + " actual=" + actual);
        }
    }

    private static void requireBound(int decisions, int max) {
        if (decisions > max) {
            throw new ControlException(
                    "CONTROL_RECONSTRUCTION_BOUND_EXCEEDED",
                    decisions + ">" + max);
        }
    }

    private static String pidOf(Map<String, Player> seats, String nativeId) {
        for (Map.Entry<String, Player> entry : seats.entrySet()) {
            if (entry.getValue().getId().toString().equals(nativeId)) {
                return entry.getKey();
            }
        }
        throw new ControlException("UNKNOWN_NATIVE_PLAYER", nativeId);
    }

    private static String textOrEmpty(JsonObject object, String key) {
        return object.has(key) && !object.get(key).isJsonNull()
                ? object.get(key).getAsString() : "";
    }

    private static String requiredText(JsonObject object, String key) {
        if (object == null || !object.has(key) || object.get(key).isJsonNull()) {
            throw new ControlException("BRIDGE_PROTOCOL_ERROR", "missing " + key);
        }
        String value = object.get(key).getAsString();
        if (value.isBlank()) {
            throw new ControlException("BRIDGE_PROTOCOL_ERROR", "blank " + key);
        }
        return value;
    }
}

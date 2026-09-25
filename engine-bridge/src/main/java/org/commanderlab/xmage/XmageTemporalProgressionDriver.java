package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.constants.PhaseStep;
import mage.players.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * RG-03 native temporal progression.
 *
 * <p>This driver never assigns turn, phase, step, active-player or priority
 * fields. It observes the live engine checkpoint and advances only by
 * submitting an explicit external proposal through the already-qualified
 * decision-scoped legal-action boundary. The caller owns every discretionary
 * choice. If no explicit proposal is supplied, the path fails closed.</p>
 */
final class XmageTemporalProgressionDriver {

    static final class ProgressionException extends RuntimeException {
        ProgressionException(String code, String detail) {
            super(code + ": " + detail);
        }
    }

    /**
     * External decision source. It receives only the current actor-scoped
     * native decision plus its authoritative projected legal actions.
     */
    @FunctionalInterface
    interface DecisionSource {
        JsonObject choose(JsonObject pendingDecision, JsonObject legalActions, int decisionIndex);
    }

    record ProgressionResult(
            JsonObject observed,
            int submittedDecisions,
            List<String> decisionClasses
    ) {
    }

    private XmageTemporalProgressionDriver() {
    }

    static ProgressionResult driveToPlanTarget(
            XmageFullGameSession session,
            Map<String, Player> seats,
            XmageNativeStateRestoration.Plan plan,
            DecisionSource decisionSource,
            int maxDecisions
    ) {
        if (session == null || seats == null || plan == null) {
            throw new ProgressionException(
                    "INVALID_DRIVER_INPUT", "session, seats and plan are required");
        }
        if (!XmageNativeStateRestoration.isSupportedTemporalPoint(plan)) {
            throw new ProgressionException(
                    "UNSUPPORTED_TEMPORAL_POINT",
                    plan.turnNumber() + "/" + plan.phase() + "/" + plan.step());
        }
        if (decisionSource == null) {
            throw new ProgressionException(
                    "MISSING_DECISION_SOURCE",
                    "temporal progression never supplies hidden/default decisions");
        }
        if (maxDecisions < 1) {
            throw new ProgressionException(
                    "INVALID_DECISION_BOUND", String.valueOf(maxDecisions));
        }

        List<String> classes = new ArrayList<>();
        for (int decisionIndex = 0; decisionIndex <= maxDecisions; decisionIndex++) {
            JsonObject observed =
                    XmageNativeStateRestoration.readback(session.restorationGame(), seats);
            if (matchesTarget(observed, plan)) {
                return new ProgressionResult(
                        observed.deepCopy(), decisionIndex, List.copyOf(classes));
            }
            if (hasOvershot(observed, plan)) {
                throw new ProgressionException(
                        "TEMPORAL_TARGET_OVERSHOT",
                        describe(observed) + " after target "
                                + plan.turnNumber() + "/" + plan.phase() + "/" + plan.step());
            }
            if (decisionIndex == maxDecisions) {
                throw new ProgressionException(
                        "TEMPORAL_DECISION_BOUND_EXCEEDED",
                        "target not reached after " + maxDecisions + " explicit decisions");
            }

            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                throw new ProgressionException(
                        "ENGINE_TERMINAL_BEFORE_TARGET",
                        describe(observed));
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            JsonObject legal = session.legalActionsPayload();
            String pendingId = requiredText(pending, "decision_id");
            String legalId = requiredText(legal, "decision_id");
            if (!pendingId.equals(legalId)) {
                throw new ProgressionException(
                        "DECISION_REVISION_DIVERGENCE",
                        pendingId + " != " + legalId);
            }
            String decisionClass = requiredText(pending, "decision_class");
            classes.add(decisionClass);

            JsonObject proposal = decisionSource.choose(
                    pending.deepCopy(), legal.deepCopy(), decisionIndex);
            if (proposal == null) {
                throw new ProgressionException(
                        "UNSCRIPTED_DECISION",
                        decisionClass + " decision_id=" + pendingId);
            }

            // XmageFullGameSession validates the proposal against the exact
            // current authoritative offer and lets XMage execute it natively.
            session.submitAction(proposal);
        }
        throw new ProgressionException(
                "TEMPORAL_DECISION_BOUND_EXCEEDED", "unreachable defensive tail");
    }

    private static boolean matchesTarget(
            JsonObject observed,
            XmageNativeStateRestoration.Plan plan
    ) {
        return observed.get("turn_number").getAsInt() == plan.turnNumber()
                && plan.phase().name().equals(observed.get("phase").getAsString())
                && plan.step().name().equals(observed.get("step").getAsString())
                && plan.activePlayer().equals(observed.get("active_player").getAsString())
                && plan.priorityPlayer().equals(observed.get("priority_player").getAsString());
    }

    private static boolean hasOvershot(
            JsonObject observed,
            XmageNativeStateRestoration.Plan plan
    ) {
        int turn = observed.get("turn_number").getAsInt();
        if (turn > plan.turnNumber()) {
            return true;
        }
        if (turn < plan.turnNumber()) {
            return false;
        }
        String stepName = observed.get("step").getAsString();
        if ("UNINITIALIZED".equals(stepName)) {
            return false;
        }
        final PhaseStep observedStep;
        try {
            observedStep = PhaseStep.valueOf(stepName);
        } catch (IllegalArgumentException exc) {
            throw new ProgressionException(
                    "UNKNOWN_NATIVE_STEP", stepName);
        }
        return observedStep.getIndex() > plan.step().getIndex();
    }

    private static String describe(JsonObject observed) {
        return observed.get("turn_number").getAsInt()
                + "/" + observed.get("phase").getAsString()
                + "/" + observed.get("step").getAsString()
                + " active=" + observed.get("active_player").getAsString()
                + " priority=" + observed.get("priority_player").getAsString();
    }

    private static String requiredText(JsonObject object, String key) {
        if (object == null || !object.has(key) || object.get(key).isJsonNull()) {
            throw new ProgressionException(
                    "BRIDGE_PROTOCOL_ERROR", "missing " + key);
        }
        String value = object.get(key).getAsString();
        if (value.isBlank()) {
            throw new ProgressionException(
                    "BRIDGE_PROTOCOL_ERROR", "blank " + key);
        }
        return value;
    }
}

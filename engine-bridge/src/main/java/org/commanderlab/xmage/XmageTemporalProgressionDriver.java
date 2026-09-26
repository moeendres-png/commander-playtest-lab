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

    /**
     * Read-only native checkpoint predicate. It may inspect the live provider
     * state but must not mutate it or manufacture Rules outcomes.
     */
    @FunctionalInterface
    interface Checkpoint {
        boolean reached(
                XmageFullGameSession session,
                Map<String, Player> seats,
                JsonObject observed
        );
    }

    record ProgressionResult(
            JsonObject observed,
            int submittedDecisions,
            List<String> decisionClasses,
            List<String> temporalTrace
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
        if (plan == null) {
            throw new ProgressionException(
                    "INVALID_DRIVER_INPUT", "plan is required");
        }
        if (!XmageNativeStateRestoration.isSupportedTemporalPoint(plan)) {
            throw new ProgressionException(
                    "UNSUPPORTED_TEMPORAL_POINT",
                    plan.turnNumber() + "/" + plan.phase() + "/" + plan.step());
        }
        return drive(
                session,
                seats,
                (liveSession, liveSeats, observed) -> matchesTarget(observed, plan),
                decisionSource,
                maxDecisions,
                plan);
    }

    /**
     * General RG-03 progression primitive for causal work such as skipped
     * phases, extra turns/combats, trigger settlement and stack blocking.
     * The checkpoint is read-only. There is deliberately no generic
     * "overshoot" heuristic because event/state predicates can span turns.
     */
    static ProgressionResult driveUntil(
            XmageFullGameSession session,
            Map<String, Player> seats,
            Checkpoint checkpoint,
            DecisionSource decisionSource,
            int maxDecisions
    ) {
        if (checkpoint == null) {
            throw new ProgressionException(
                    "INVALID_DRIVER_INPUT", "checkpoint is required");
        }
        return drive(session, seats, checkpoint, decisionSource, maxDecisions, null);
    }

    private static ProgressionResult drive(
            XmageFullGameSession session,
            Map<String, Player> seats,
            Checkpoint checkpoint,
            DecisionSource decisionSource,
            int maxDecisions,
            XmageNativeStateRestoration.Plan temporalPlan
    ) {
        if (session == null || seats == null) {
            throw new ProgressionException(
                    "INVALID_DRIVER_INPUT", "session and seats are required");
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
        List<String> trace = new ArrayList<>();
        for (int decisionIndex = 0; decisionIndex <= maxDecisions; decisionIndex++) {
            JsonObject observed =
                    XmageNativeStateRestoration.readback(session.restorationGame(), seats);
            String sample = describe(observed);
            if (trace.isEmpty() || !trace.get(trace.size() - 1).equals(sample)) {
                trace.add(sample);
            }
            if (checkpoint.reached(session, seats, observed)) {
                return new ProgressionResult(
                        observed.deepCopy(), decisionIndex,
                        List.copyOf(classes), List.copyOf(trace));
            }
            if (temporalPlan != null && hasOvershot(observed, temporalPlan)) {
                throw new ProgressionException(
                        "TEMPORAL_TARGET_OVERSHOT",
                        describe(observed) + " after target "
                                + temporalPlan.turnNumber() + "/"
                                + temporalPlan.phase() + "/" + temporalPlan.step());
            }
            if (decisionIndex == maxDecisions) {
                throw new ProgressionException(
                        "TEMPORAL_DECISION_BOUND_EXCEEDED",
                        "checkpoint not reached after " + maxDecisions
                                + " explicit decisions");
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

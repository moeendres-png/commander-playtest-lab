package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import mage.game.Game;
import mage.players.Player;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Blocking, fail-closed decision handoff for full-game XMage external control.
 *
 * <p>The XMage engine thread publishes a decision and blocks. The JSONL control
 * thread may read that immutable request and submit only option identifiers that
 * XMage itself supplied. No default, random, tactical, structural or XMage-AI
 * answer exists in this controller.</p>
 */
final class XmageFullGameDecisionController {

    static final String PROTOCOL_VERSION = "xmage-external-decision-protocol-1.0.0";

    record DecisionResponse(
            String decisionId,
            String actorId,
            List<String> selectedOptionIds,
            List<String> ordering,
            Integer numericChoice,
            List<Integer> numericChoices
    ) {
    }

    static final class DecisionException extends RuntimeException {
        DecisionException(String message) {
            super(message);
        }

        DecisionException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    /**
     * Native XMage cancelled an already-published decision because the
     * controlled player conceded. This is an engine synchronization signal,
     * never a pilot response and never a default selection.
     */
    static final class DecisionCancelledException extends RuntimeException {
        DecisionCancelledException(String message) {
            super(message);
        }
    }

    private final long timeoutMillis;
    private long decisionOffset;
    private JsonObject pendingRequest;
    private UUID pendingPlayerId;
    private DecisionResponse response;
    private String cancelledDecisionId;
    private DecisionException terminalFailure;
    private boolean terminal;
    private final JsonArray transcript = new JsonArray();

    XmageFullGameDecisionController() {
        this(Duration.ofMinutes(2));
    }

    XmageFullGameDecisionController(Duration timeout) {
        if (timeout == null || timeout.isZero() || timeout.isNegative()) {
            throw new IllegalArgumentException("decision timeout must be positive");
        }
        this.timeoutMillis = timeout.toMillis();
    }

    synchronized DecisionResponse request(
            Game game,
            Player actor,
            String decisionClass,
            String prompt,
            int minimumSelections,
            int maximumSelections,
            JsonArray legalOptions,
            JsonObject context,
            JsonObject sourceObject
    ) {
        if (terminalFailure != null) {
            throw terminalFailure;
        }
        if (terminal) {
            throw new DecisionException("FULL_GAME_ALREADY_TERMINAL");
        }
        if (pendingRequest != null) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: concurrent pending decision");
        }
        if (game == null || actor == null) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: game/actor unavailable");
        }
        if (decisionClass == null || decisionClass.isBlank()) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: decision_class is blank");
        }
        if (minimumSelections < 0 || maximumSelections < minimumSelections) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: invalid selection bounds");
        }

        if (!actor.isInGame()) {
            // A player who left makes no choices (CR 800.4a): no frame is ever
            // published for it; the lane fails closed instead of guessing.
            DecisionException failure = new DecisionException(
                    "PLAYER_LEFT_GAME_UNSUPPORTED_DECISION: the engine asked a player who left the game for "
                            + decisionClass
            );
            terminalFailure = failure;
            recordFailure(failure.getMessage());
            notifyAll();
            throw failure;
        }

        // CR 723 (controlling another player): XMage remains the sole authority
        // for whether this player's turn is controlled. The bridge only routes
        // the engine-generated decision to that controller's principal.
        Player controlled = actor;
        actor = decidingPlayer(game, actor);

        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", PROTOCOL_VERSION);
        address(request, game, controlled, actor, decisionClass);
        String decisionId = request.get("decision_id").getAsString();
        request.addProperty("decision_class", decisionClass);
        request.addProperty("prompt", prompt == null ? "" : prompt);
        request.add("context", context == null ? new JsonObject() : context.deepCopy());
        request.addProperty("minimum_selections", minimumSelections);
        request.addProperty("maximum_selections", maximumSelections);
        request.add("legal_options", legalOptions == null ? new JsonArray() : legalOptions.deepCopy());
        JsonObject actorView = bindViews(request, game, actor);
        request.addProperty("timeout_millis", timeoutMillis);
        request.add("source_object", sourceObject == null ? JsonNull.INSTANCE : sourceObject.deepCopy());
        request.addProperty("xmage_identity", game.getClass().getName());
        request.addProperty("protocol_identity", PROTOCOL_VERSION);
        request.add("pilot_state", actorView);

        pendingRequest = request;
        pendingPlayerId = controlled.getId();
        response = null;
        recordDecisionRequested(request);
        notifyAll();

        long deadlineNanos = System.nanoTime() + timeoutMillis * 1_000_000L;
        while (response == null
                && terminalFailure == null
                && !terminal
                && !decisionId.equals(cancelledDecisionId)) {
            long remainingNanos = deadlineNanos - System.nanoTime();
            if (remainingNanos <= 0L) {
                DecisionException failure = new DecisionException(
                        "DECISION_TIMEOUT: " + decisionId + " class=" + decisionClass
                );
                terminalFailure = failure;
                recordFailure(failure.getMessage());
                pendingRequest = null;
                notifyAll();
                throw failure;
            }
            try {
                long millis = Math.max(1L, remainingNanos / 1_000_000L);
                wait(millis);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                DecisionException failure = new DecisionException(
                        "DECISION_TIMEOUT: interrupted while awaiting " + decisionId,
                        exc
                );
                terminalFailure = failure;
                recordFailure(failure.getMessage());
                pendingRequest = null;
                notifyAll();
                throw failure;
            }
        }

        if (terminalFailure != null) {
            throw terminalFailure;
        }
        if (decisionId.equals(cancelledDecisionId)) {
            cancelledDecisionId = null;
            pendingRequest = null;
            pendingPlayerId = null;
            notifyAll();
            throw new DecisionCancelledException(
                    "ENGINE_DECISION_CANCELLED: " + decisionId + " class=" + decisionClass
            );
        }
        if (response == null) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: decision ended without response");
        }
        DecisionResponse result = response;
        response = null;
        pendingRequest = null;
        notifyAll();
        return result;
    }

    /**
     * Binds a decision frame to the principal that makes it: a fresh
     * decision offset and id, the deciding seat, and the controlled seat
     * when they differ (CR 723).
     */
    private void address(JsonObject request, Game game, Player controlled, Player decider, String decisionClass) {
        decisionOffset++;
        String actorId = decider.getId().toString();
        request.addProperty("game_id", game.getId().toString());
        request.addProperty("decision_id", stableId(
                game.getId().toString(),
                Long.toString(decisionOffset),
                actorId,
                decisionClass
        ));
        request.addProperty("decision_offset", decisionOffset);
        request.addProperty("actor_id", actorId);
        request.addProperty("seat", XmageFullGameStateRedactor.seat(game, decider.getId()));
        request.remove("acting_for_seat");
        if (!controlled.getId().equals(decider.getId())) {
            request.addProperty(
                    "acting_for_seat",
                    XmageFullGameStateRedactor.seat(game, controlled.getId())
            );
        }
    }

    /** Binds the deciding principal's own views; returns its pilot state. */
    private static JsonObject bindViews(JsonObject request, Game game, Player decider) {
        JsonObject actorView = XmageFullGameStateRedactor.actorView(game, decider);
        JsonObject publicView = XmageFullGameStateRedactor.publicView(game);
        request.addProperty(
                "public_state_reference",
                "public-view:" + XmageAuditEventLog.stateHash(publicView)
        );
        request.addProperty(
                "private_actor_state_reference",
                "actor-view:" + XmageAuditEventLog.stateHash(actorView)
        );
        return actorView;
    }

    /**
     * F-34: the unanswered decision follows the engine's current turn-control
     * relationship. When a player leaves (CR 800.4a) while its pending frame
     * is one it makes for a player whose turn it controls, the engine's
     * control state decides who now makes that same engine-generated
     * decision; the options, bounds and prompt are unchanged, only the
     * addressee and its views are re-bound under a new decision id. A
     * departed controller that the engine still names fails closed.
     *
     * <p>F-39: a priority frame whose own principal just left keeps only the
     * engine's pass option. A player who left takes no actions (CR 800.4a),
     * and the engine no longer executes the other options, so offering them
     * would let a pilot pick an action that fails the lane. Options are only
     * removed, never added, and the pilot still answers the frame.</p>
     *
     * @return whether the pending frame was re-issued
     */
    synchronized boolean followTurnControl(Game game) {
        if (pendingRequest == null || response != null || terminalFailure != null || terminal
                || game == null || pendingPlayerId == null) {
            return false;
        }
        Player controlled = game.getPlayer(pendingPlayerId);
        if (controlled == null) {
            return false;
        }
        Player decider;
        try {
            decider = decidingPlayer(game, controlled);
        } catch (DecisionException failure) {
            terminalFailure = failure;
            recordFailure(failure.getMessage());
            pendingRequest = null;
            notifyAll();
            return false;
        }
        JsonObject request = pendingRequest.deepCopy();
        boolean narrowed = !decider.isInGame()
                && "priority".equals(request.get("decision_class").getAsString())
                && keepOnlyPass(request);
        if (!narrowed && decider.getId().toString().equals(pendingRequest.get("actor_id").getAsString())) {
            return false;
        }
        address(request, game, controlled, decider, request.get("decision_class").getAsString());
        request.add("pilot_state", bindViews(request, game, decider));
        pendingRequest = request;
        recordDecisionRequested(request);
        notifyAll();
        return true;
    }

    /**
     * Propagates XMage's native {@code signalPlayerConcede(true)} semantics
     * for the currently observed mid-cast seams. The engine has invalidated
     * the outstanding target/payment callback, so it is retired without
     * accepting any pilot response. Priority remains on the existing F-39
     * re-issue path; other decision classes remain fail-closed until observed
     * and qualified.
     */
    synchronized boolean cancelPendingForConcession(UUID controlledPlayerId) {
        if (pendingRequest == null
                || response != null
                || terminalFailure != null
                || terminal
                || controlledPlayerId == null
                || pendingPlayerId == null
                || !controlledPlayerId.equals(pendingPlayerId)) {
            return false;
        }
        String decisionClass = pendingRequest.get("decision_class").getAsString();
        if (!"target".equals(decisionClass) && !"mana_payment".equals(decisionClass)) {
            return false;
        }

        String decisionId = pendingRequest.get("decision_id").getAsString();
        JsonObject event = new JsonObject();
        event.addProperty("decision_id", decisionId);
        event.addProperty("decision_class", decisionClass);
        event.addProperty("actor_seat", pendingRequest.get("seat").getAsInt());
        event.addProperty("reason", "native_player_concede_signal");
        recordTranscript("engine_decision_cancelled", event);

        cancelledDecisionId = decisionId;
        pendingRequest = null;
        notifyAll();
        return true;
    }

    /**
     * F-40: the native signal above reaches only the priority player (or its
     * controller), because XMage stops only that player's dialog. A player
     * who concedes while one of its <em>own</em> choices is pending during
     * another player's spell (for example the "may" of a tempting offer) is
     * not signalled, and its stale frame stayed answerable: a player who had
     * left still decided (a tempting offer, a sacrifice, a council vote),
     * and the engine counted the answer (CR 800.4a: a player who left makes
     * no choices). After the native concession this
     * handles a frame of a player no longer in the game systemically: a
     * class whose callback unwinds natively is retired; priority keeps its
     * F-39 path; every other class ends the lane fail-closed
     * ({@code PLAYER_LEFT_GAME_UNSUPPORTED_DECISION}). No departed player's
     * frame is ever left answerable.
     */
    synchronized boolean cancelPendingForDepartedPlayer(Game game) {
        if (pendingRequest == null
                || response != null
                || terminalFailure != null
                || terminal
                || game == null
                || pendingPlayerId == null) {
            return false;
        }
        Player player = game.getPlayer(pendingPlayerId);
        String decisionClass = pendingRequest.get("decision_class").getAsString();
        if (player == null || player.isInGame() || "priority".equals(decisionClass)) {
            // Priority keeps its F-39 path (followTurnControl).
            return false;
        }
        String decisionId = pendingRequest.get("decision_id").getAsString();
        JsonObject event = new JsonObject();
        event.addProperty("decision_id", decisionId);
        event.addProperty("decision_class", decisionClass);
        event.addProperty("actor_seat", pendingRequest.get("seat").getAsInt());
        if (!DEPARTED_CANCELLABLE.contains(decisionClass)) {
            // Systemic rule: a departed player's pending frame is never left
            // answerable. A class whose callback is not qualified to unwind
            // natively ends the lane fail-closed instead of guessing a result.
            event.addProperty("reason", "player_left_game_unsupported_class");
            recordTranscript("engine_decision_cancelled", event);
            DecisionException failure = new DecisionException(
                    "PLAYER_LEFT_GAME_UNSUPPORTED_DECISION: " + decisionClass
                            + " frame of a player who left the game has no qualified native unwind"
            );
            terminalFailure = failure;
            recordFailure(failure.getMessage());
            pendingRequest = null;
            notifyAll();
            return true;
        }
        event.addProperty("reason", "player_left_game");
        recordTranscript("engine_decision_cancelled", event);

        cancelledDecisionId = decisionId;
        pendingRequest = null;
        notifyAll();
        return true;
    }

    private static final Set<String> DEPARTED_CANCELLABLE = Set.of("target", "choose_object", "mana_payment", "choose_use");

    /** Narrows a priority frame to its pass option; false when there is nothing to remove. */
    private static boolean keepOnlyPass(JsonObject request) {
        JsonArray kept = new JsonArray();
        JsonArray options = request.getAsJsonArray("legal_options");
        for (JsonElement element : options) {
            JsonObject option = element.getAsJsonObject();
            if (option.has("option_type") && "pass_priority".equals(option.get("option_type").getAsString())) {
                kept.add(option);
            }
        }
        if (kept.isEmpty() || kept.size() == options.size()) {
            return false;
        }
        request.add("legal_options", kept);
        request.getAsJsonObject("context").addProperty("actor_left_game", true);
        return true;
    }

    synchronized JsonObject pendingDecision() {
        return pendingRequest == null ? null : pendingRequest.deepCopy();
    }

    synchronized boolean awaitPendingOrTerminal(Duration timeout) {
        long millis = timeout == null ? 10_000L : timeout.toMillis();
        long deadline = System.nanoTime() + millis * 1_000_000L;
        while (pendingRequest == null && terminalFailure == null && !terminal) {
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0L) {
                return false;
            }
            try {
                wait(Math.max(1L, remaining / 1_000_000L));
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return true;
    }

    synchronized void submit(JsonObject submitted) {
        if (pendingRequest == null) {
            throw new DecisionException("STALE_DECISION: no pending decision");
        }
        if (submitted == null) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: response is null");
        }
        String expectedDecisionId = pendingRequest.get("decision_id").getAsString();
        String expectedActorId = pendingRequest.get("actor_id").getAsString();
        String decisionId = requiredText(submitted, "decision_id");
        String actorId = requiredText(submitted, "actor_id");
        if (!expectedDecisionId.equals(decisionId)) {
            throw new DecisionException("STALE_DECISION: expected " + expectedDecisionId);
        }
        if (!expectedActorId.equals(actorId)) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: wrong actor");
        }

        List<String> selected = stringArray(submitted, "selected_option_ids");
        List<String> ordering = stringArray(submitted, "ordering");
        Integer numeric = optionalInteger(submitted, "numeric_choice");
        List<Integer> numerics = optionalIntegerArray(submitted, "numeric_choices");
        if (numeric != null && numerics != null) {
            throw new DecisionException(
                    "PILOT_RESPONSE_INVALID: numeric_choice and numeric_choices are mutually exclusive"
            );
        }

        int min = pendingRequest.get("minimum_selections").getAsInt();
        int max = pendingRequest.get("maximum_selections").getAsInt();
        if (selected.size() < min || selected.size() > max) {
            throw new DecisionException(
                    "PILOT_RESPONSE_INVALID: selected " + selected.size()
                            + " options, expected " + min + ".." + max
            );
        }
        if (new HashSet<>(selected).size() != selected.size()) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: duplicate option id");
        }

        Set<String> allowed = new HashSet<>();
        for (JsonElement element : pendingRequest.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (option.has("option_id") && !option.get("option_id").isJsonNull()) {
                allowed.add(option.get("option_id").getAsString());
            }
        }
        for (String optionId : selected) {
            if (!allowed.contains(optionId)) {
                throw new DecisionException("ILLEGAL_ACTION: option not offered by XMage: " + optionId);
            }
        }
        for (String optionId : ordering) {
            if (!allowed.contains(optionId)) {
                throw new DecisionException("PILOT_RESPONSE_INVALID: ordering contains unknown option");
            }
        }

        JsonObject context = pendingRequest.getAsJsonObject("context");
        if (numeric != null && context.has("numeric_min") && context.has("numeric_max")) {
            int numericMin = context.get("numeric_min").getAsInt();
            int numericMax = context.get("numeric_max").getAsInt();
            if (numeric < numericMin || numeric > numericMax) {
                throw new DecisionException("PILOT_RESPONSE_INVALID: numeric choice out of range");
            }
        } else if (numeric != null) {
            // WS229 N-22 transport lane: a scalar number where no bounds
            // were authorized is schema confusion and fails closed.
            throw new DecisionException(
                    "PILOT_RESPONSE_INVALID: numeric_choice not authorized by decision schema"
            );
        }

        // WS229 joint vector transport: the pending joint frame carries its
        // own authoritative legs/totals (emitted by the native callback
        // owner). The controller enforces the exact isGoodValues projection
        // — length, per-leg membership, total band — mirroring the scalar
        // range check above. It invents no bounds.
        if (numerics != null) {
            requireJointVector(numerics, context);
        }

        response = new DecisionResponse(
                decisionId,
                actorId,
                List.copyOf(selected),
                List.copyOf(ordering),
                numeric,
                numerics == null ? null : List.copyOf(numerics)
        );
        recordDecisionAccepted(pendingRequest, selected, numeric, numerics);
        notifyAll();
    }

    synchronized void failClosed(String failureCode, String detail) {
        String code = failureCode == null || failureCode.isBlank()
                ? "BRIDGE_PROTOCOL_ERROR"
                : failureCode.trim();
        String message = code + (detail == null || detail.isBlank() ? "" : ": " + detail.trim());
        terminalFailure = new DecisionException(message);
        recordFailure(message);
        notifyAll();
    }

    synchronized void markTerminal() {
        terminal = true;
        notifyAll();
    }

    synchronized DecisionException terminalFailure() {
        return terminalFailure;
    }

    synchronized JsonArray transcript() {
        return transcript.deepCopy();
    }

    synchronized long decisionCount() {
        return decisionOffset;
    }

    private void recordDecisionRequested(JsonObject request) {        JsonObject event = new JsonObject();
        event.addProperty("sequence", transcript.size() + 1L);
        event.addProperty("kind", "decision_requested");
        event.addProperty("decision_class", request.get("decision_class").getAsString());
        event.addProperty("actor_seat", request.get("seat").getAsInt());
        if (request.has("acting_for_seat") && !request.get("acting_for_seat").isJsonNull()) {
            event.addProperty("acting_for_seat", request.get("acting_for_seat").getAsInt());
        }
        event.addProperty("prompt", request.get("prompt").getAsString());
        event.addProperty(
                "public_state_reference",
                request.get("public_state_reference").getAsString()
        );
        JsonArray types = new JsonArray();
        JsonArray labels = new JsonArray();
        for (JsonElement element : request.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            types.add(option.has("option_type") ? option.get("option_type").getAsString() : "generic");
            labels.add(option.has("label") ? option.get("label").getAsString() : "");
        }
        event.add("legal_option_types", types);
        event.add("legal_option_labels", labels);
        transcript.add(event);
    }

    private void recordDecisionAccepted(
            JsonObject request,
            List<String> selected,
            Integer numeric,
            List<Integer> numerics
    ) {
        JsonObject event = new JsonObject();
        event.addProperty("sequence", transcript.size() + 1L);
        event.addProperty("kind", "decision_accepted");
        event.addProperty("decision_class", request.get("decision_class").getAsString());
        event.addProperty("actor_seat", request.get("seat").getAsInt());
        if (request.has("acting_for_seat") && !request.get("acting_for_seat").isJsonNull()) {
            event.addProperty("acting_for_seat", request.get("acting_for_seat").getAsInt());
        }
        event.addProperty("prompt", request.get("prompt").getAsString());
        JsonArray selectedTypes = new JsonArray();
        JsonArray selectedLabels = new JsonArray();
        for (String selectedId : selected) {
            for (JsonElement element : request.getAsJsonArray("legal_options")) {
                JsonObject option = element.getAsJsonObject();
                if (option.has("option_id")
                        && selectedId.equals(option.get("option_id").getAsString())) {
                    selectedTypes.add(
                            option.has("option_type")
                                    ? option.get("option_type").getAsString()
                                    : "generic"
                    );
                    selectedLabels.add(
                            option.has("label") ? option.get("label").getAsString() : ""
                    );
                    break;
                }
            }
        }
        event.add("selected_option_types", selectedTypes);
        event.add("selected_option_labels", selectedLabels);
        if (numeric == null) {
            event.add("numeric_choice", JsonNull.INSTANCE);
        } else {
            event.addProperty("numeric_choice", numeric);
        }
        if (numerics == null) {
            event.add("numeric_choices", JsonNull.INSTANCE);
        } else {
            JsonArray vector = new JsonArray();
            numerics.forEach(vector::add);
            event.add("numeric_choices", vector);
        }
        transcript.add(event);
    }

    /**
     * WS229 F-RULES-03 disposition: logged forced-move record for native
     * auto-submits with no pilot discretion (single-offer ability choice).
     * Observable in the session transcript; never a pilot decision.
     */
    synchronized void recordForcedMove(String decisionClass, String prompt, String detail) {
        JsonObject payload = new JsonObject();
        payload.addProperty("decision_class", decisionClass == null ? "" : decisionClass);
        payload.addProperty("prompt", prompt == null ? "" : prompt);
        payload.addProperty("detail", detail == null ? "" : detail);
        recordTranscript("forced_move", payload);
    }

    /**
     * WS229 joint isGoodValues projection for transport validation.
     * Bounds come verbatim from the pending frame's own context; a vector
     * on a frame without joint legs is schema confusion and fails closed.
     */
    static void requireJointVector(List<Integer> vector, JsonObject context) {
        if (context == null
                || !context.has("numeric_legs")
                || !context.get("numeric_legs").isJsonArray()) {
            throw new DecisionException(
                    "PILOT_RESPONSE_INVALID: numeric_choices not authorized by decision schema"
            );
        }
        JsonArray legs = context.getAsJsonArray("numeric_legs");
        if (!context.has("numeric_total_min")
                || !context.has("numeric_total_max")) {
            throw new DecisionException(
                    "BRIDGE_PROTOCOL_ERROR: joint frame is missing its total band"
            );
        }
        int totalMin;
        int totalMax;
        try {
            totalMin = context.get("numeric_total_min").getAsInt();
            totalMax = context.get("numeric_total_max").getAsInt();
        } catch (RuntimeException exc) {
            throw new DecisionException(
                    "BRIDGE_PROTOCOL_ERROR: joint frame total band is malformed", exc);
        }
        if (vector.size() != legs.size()) {
            throw new DecisionException(
                    "PILOT_RESPONSE_INVALID: joint vector length " + vector.size()
                            + " differs from legs " + legs.size()
            );
        }
        int total = 0;
        for (int index = 0; index < legs.size(); index++) {
            JsonElement legElement = legs.get(index);
            if (!legElement.isJsonObject()) {
                throw new DecisionException(
                        "BRIDGE_PROTOCOL_ERROR: joint frame leg " + index + " is malformed");
            }
            JsonObject leg = legElement.getAsJsonObject();
            int legMin;
            int legMax;
            try {
                legMin = leg.get("min").getAsInt();
                legMax = leg.get("max").getAsInt();
            } catch (RuntimeException exc) {
                throw new DecisionException(
                        "BRIDGE_PROTOCOL_ERROR: joint frame leg " + index + " is malformed", exc);
            }
            int value = vector.get(index);
            if (value < legMin || value > legMax) {
                throw new DecisionException(
                        "PILOT_RESPONSE_INVALID: joint leg " + index + " value " + value
                                + " out of range " + legMin + ".." + legMax
                );
            }
            total += value;
        }
        if (total < totalMin || total > totalMax) {
            throw new DecisionException(
                    "PILOT_RESPONSE_INVALID: joint total " + total
                            + " outside " + totalMin + ".." + totalMax
            );
        }
    }

    private void recordFailure(String message) {
        JsonObject payload = new JsonObject();
        payload.addProperty("message", message);
        recordTranscript("controller_failure", payload);
    }

    private void recordTranscript(String eventType, JsonObject payload) {
        JsonObject event = new JsonObject();
        event.addProperty("offset", transcript.size() + 1L);
        event.addProperty("event_type", eventType);
        event.add("payload", payload == null ? new JsonObject() : payload.deepCopy());
        transcript.add(event);
    }

    /**
     * Principal that makes this player's decision under the engine's current
     * turn-control relationship. Missing controller state fails closed.
     */
    static Player decidingPlayer(Game game, Player player) {
        UUID controllerId = player.getTurnControlledBy();
        if (controllerId == null || controllerId.equals(player.getId())) {
            return player;
        }
        Player controller = game.getPlayer(controllerId);
        if (controller == null) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: turn controller unavailable");
        }
        if (!controller.isInGame()) {
            // CR 800.4a ends a departed player's control of other players;
            // the bridge never makes that call itself.
            throw new DecisionException(
                    "TURN_CONTROLLER_LEFT: the engine still names a player who left the game as turn controller"
            );
        }
        return controller;
    }

    static JsonObject option(String optionId, String label, String optionType, JsonObject metadata) {
        JsonObject option = new JsonObject();
        option.addProperty("option_id", optionId);
        option.addProperty("label", redactObjectIds(label == null ? optionId : label));
        option.addProperty("option_type", optionType == null ? "generic" : optionType);
        option.add("metadata", redactObjectIds(metadata == null ? new JsonObject() : metadata.deepCopy()));
        return option;
    }

    /**
     * WS92-D4 twin-stable redaction (systemic reacquisition, not a verbatim
     * restore). Per-game engine object identity carries no Rules content and
     * must not enter twin-stable projections: primary and replica mint
     * distinct ids, so raw ids would falsely diverge replay equality.
     * Read-only label/metadata scrub; no Rules semantics computed or altered.
     */
    private static final java.util.regex.Pattern OBJECT_ID_UUID = java.util.regex.Pattern.compile(
            "object_id='[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'");

    static String redactObjectIds(String text) {
        return text == null ? null : OBJECT_ID_UUID.matcher(text).replaceAll("object_id='#'");
    }

    private static JsonObject redactObjectIds(JsonObject object) {
        for (java.util.Map.Entry<String, com.google.gson.JsonElement> entry : object.entrySet()) {
            if (entry.getValue().isJsonPrimitive()
                    && entry.getValue().getAsJsonPrimitive().isString()) {
                entry.setValue(new JsonPrimitive(
                        redactObjectIds(entry.getValue().getAsString())));
            } else if (entry.getValue().isJsonObject()) {
                redactObjectIds(entry.getValue().getAsJsonObject());
            } else if (entry.getValue().isJsonArray()) {
                com.google.gson.JsonArray array = entry.getValue().getAsJsonArray();
                for (int index = 0; index < array.size(); index++) {
                    if (array.get(index).isJsonPrimitive()
                            && array.get(index).getAsJsonPrimitive().isString()) {
                        array.set(index, new com.google.gson.JsonPrimitive(
                                redactObjectIds(array.get(index).getAsString())));
                    } else if (array.get(index).isJsonObject()) {
                        redactObjectIds(array.get(index).getAsJsonObject());
                    }
                }
            }
        }
        return object;
    }

    static String stableId(String... parts) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String part : parts) {
                String value = part == null ? "<null>" : part;
                digest.update(value.getBytes(StandardCharsets.UTF_8));
                digest.update((byte) 0);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException("SHA-256 unavailable", exc);
        }
    }

    private static String requiredText(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: missing " + property);
        }
        String value = object.get(property).getAsString().trim();
        if (value.isBlank()) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: blank " + property);
        }
        return value;
    }

    private static List<String> stringArray(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return List.of();
        }
        if (!object.get(property).isJsonArray()) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: " + property + " must be an array");
        }
        List<String> values = new ArrayList<>();
        for (JsonElement element : object.getAsJsonArray(property)) {
            if (!element.isJsonPrimitive() || !element.getAsJsonPrimitive().isString()) {
                throw new DecisionException("PILOT_RESPONSE_INVALID: non-string in " + property);
            }
            values.add(element.getAsString());
        }
        return values;
    }

    private static Integer optionalInteger(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return null;
        }
        // WS229: strict integer — strings, booleans, and fractionals fail
        // closed instead of truncating (matches the projection lane).
        JsonElement element = object.get(property);
        if (!element.isJsonPrimitive() || !element.getAsJsonPrimitive().isNumber()) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: " + property + " must be integer");
        }
        try {
            double asDouble = element.getAsJsonPrimitive().getAsDouble();
            int asInt = element.getAsJsonPrimitive().getAsInt();
            if (asDouble != (double) asInt) {
                throw new DecisionException(
                        "PILOT_RESPONSE_INVALID: " + property + " must be integer");
            }
            return asInt;
        } catch (DecisionException exc) {
            throw exc;
        } catch (RuntimeException exc) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: " + property + " must be integer", exc);
        }
    }

    private static List<Integer> optionalIntegerArray(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return null;
        }
        if (!object.get(property).isJsonArray()) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: " + property + " must be an array");
        }
        List<Integer> values = new ArrayList<>();
        for (JsonElement element : object.getAsJsonArray(property)) {
            if (!element.isJsonPrimitive() || !element.getAsJsonPrimitive().isNumber()) {
                throw new DecisionException(
                        "PILOT_RESPONSE_INVALID: non-integer element in " + property);
            }
            try {
                double asDouble = element.getAsJsonPrimitive().getAsDouble();
                int asInt = element.getAsJsonPrimitive().getAsInt();
                if (asDouble != (double) asInt) {
                    throw new DecisionException(
                            "PILOT_RESPONSE_INVALID: non-integer element in " + property);
                }
                values.add(asInt);
            } catch (DecisionException exc) {
                throw exc;
            } catch (RuntimeException exc) {
                throw new DecisionException(
                        "PILOT_RESPONSE_INVALID: non-integer element in " + property, exc);
            }
        }
        return values;
    }
}

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

    private final long timeoutMillis;
    private long decisionOffset;
    private JsonObject pendingRequest;
    private DecisionResponse response;
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

        decisionOffset++;
        String actorId = actor.getId().toString();
        String gameId = game.getId().toString();
        String decisionId = stableId(
                gameId,
                Long.toString(decisionOffset),
                actorId,
                decisionClass
        );

        JsonObject actorView = XmageFullGameStateRedactor.actorView(game, actor);
        String actorViewHash = XmageAuditEventLog.stateHash(actorView);

        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", PROTOCOL_VERSION);
        request.addProperty("game_id", gameId);
        request.addProperty("decision_id", decisionId);
        request.addProperty("decision_offset", decisionOffset);
        request.addProperty("actor_id", actorId);
        request.addProperty("seat", XmageFullGameStateRedactor.seat(game, actor.getId()));
        request.addProperty("decision_class", decisionClass);
        request.addProperty("prompt", prompt == null ? "" : prompt);
        request.add("context", context == null ? new JsonObject() : context.deepCopy());
        request.addProperty("minimum_selections", minimumSelections);
        request.addProperty("maximum_selections", maximumSelections);
        request.add("legal_options", legalOptions == null ? new JsonArray() : legalOptions.deepCopy());
        request.addProperty("public_state_reference", "actor-view:" + actorViewHash);
        request.addProperty("private_actor_state_reference", "actor-view:" + actorViewHash);
        request.addProperty("timeout_millis", timeoutMillis);
        request.add("source_object", sourceObject == null ? JsonNull.INSTANCE : sourceObject.deepCopy());
        request.addProperty("xmage_identity", game.getClass().getName());
        request.addProperty("protocol_identity", PROTOCOL_VERSION);
        request.add("pilot_state", actorView);

        pendingRequest = request;
        response = null;
        recordDecisionRequested(request);
        notifyAll();

        long deadlineNanos = System.nanoTime() + timeoutMillis * 1_000_000L;
        while (response == null && terminalFailure == null && !terminal) {
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
        if (response == null) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: decision ended without response");
        }
        DecisionResponse result = response;
        response = null;
        pendingRequest = null;
        notifyAll();
        return result;
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
        event.addProperty("prompt", request.get("prompt").getAsString());
        event.addProperty(
                "public_state_reference",
                request.get("public_state_reference").getAsString()
        );
        event.addProperty(
                "private_actor_state_reference",
                request.get("private_actor_state_reference").getAsString()
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
        try {
            return object.get(property).getAsInt();
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

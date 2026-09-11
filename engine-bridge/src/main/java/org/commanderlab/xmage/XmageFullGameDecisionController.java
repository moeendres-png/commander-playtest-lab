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
import java.util.Map;
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

    static final String PROTOCOL_VERSION = "xmage-external-decision-protocol-1.1.0";

    record DecisionResponse(
            String decisionId,
            String actorId,
            List<String> selectedOptionIds,
            List<String> ordering,
            Integer numericChoice
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
    private Map<String, String> pendingExternalToNative = Map.of();
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
            Player decisionSubject,
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
        if (game == null || decisionSubject == null) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: game/decision subject unavailable");
        }
        if (decisionClass == null || decisionClass.isBlank()) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: decision_class is blank");
        }
        if (minimumSelections < 0 || maximumSelections < minimumSelections) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: invalid selection bounds");
        }

        XmageKnowledgeLedger ledger = XmageFullGameStateRedactor.knowledgeLedger(game);
        Player decisionAuthority = ledger.decisionAuthority(game, decisionSubject);
        XmageFullGameObservationGateway.SafeDecision safeDecision;
        XmageDecisionOptionIdentity.Binding optionBinding;
        try {
            /*
             * Keep native XMage option UUIDs in the privileged domain until the
             * exact current actor-visible object projection is known. WS-34
             * projected the options first and then attempted to externalize the
             * already-opaque ids, producing opaque->opaque bindings which were
             * later parsed as native UUIDs by XmageFullGamePlayer.
             *
             * The ordering below is intentionally one-way:
             *   native XMage option -> actor-visible opaque option -> pilot
             * while optionBinding retains the exact opaque -> native relation
             * only for this pending DecisionFrame.
             */
            JsonObject privilegedActorView = ledger.snapshot(
                    game,
                    decisionAuthority,
                    decisionSubject
            );
            JsonObject actorIdentityView = XmageActorIdentityProjection.actorView(
                    game,
                    decisionAuthority,
                    privilegedActorView
            );
            JsonArray nativeOptions = legalOptions == null
                    ? new JsonArray()
                    : legalOptions.deepCopy();
            optionBinding = XmageDecisionOptionIdentity.externalize(
                    nativeOptions,
                    XmageDecisionOptionIdentity.visibleNativeToSemantic(
                            game,
                            actorIdentityView
                    )
            );
            safeDecision = XmageFullGameObservationGateway.validate(
                    game,
                    decisionAuthority,
                    decisionSubject,
                    prompt,
                    context,
                    optionBinding.externalOptions(),
                    sourceObject
            );
            optionBinding = XmageDecisionOptionIdentity.rebindAfterOutboundProjection(
                    optionBinding,
                    safeDecision.legalOptions()
            );
        } catch (IllegalStateException exc) {
            DecisionException failure = new DecisionException(exc.getMessage(), exc);
            terminalFailure = failure;
            recordFailure(failure.getMessage());
            pendingExternalToNative = Map.of();
            notifyAll();
            throw failure;
        }

        decisionOffset++;
        String actorId = decisionAuthority.getId().toString();
        String subjectId = decisionSubject.getId().toString();
        String gameId = game.getId().toString();
        String decisionId = stableId(
                gameId,
                Long.toString(decisionOffset),
                actorId,
                subjectId,
                decisionClass
        );

        JsonObject actorView = safeDecision.actorView();
        String actorViewHash = XmageAuditEventLog.stateHash(actorView);

        // WS56 Phase D: adapter-owned freshness binding. Binds game identity,
        // principal, decision kind, current authoritative option identities,
        // and relevant current frame/state identity without introducing a
        // second Rules engine. Digests are opaque hashes (no hidden leakage).
        // ENGINE_NATIVE: game_id, actor_id, subject, decision_class, option
        // set as issued by XMage. ADAPTER_OWNED: decision_id, offset,
        // option_digest, frame_digest, revision, hashes, provenance map.
        List<String> freshnessOptionIds = new ArrayList<>();
        for (JsonElement element : safeDecision.legalOptions()) {
            JsonObject option = element.getAsJsonObject();
            if (option.has("option_id") && !option.get("option_id").isJsonNull()) {
                freshnessOptionIds.add(option.get("option_id").getAsString());
            }
        }
        List<String> sortedFreshnessIds = new ArrayList<>(freshnessOptionIds);
        java.util.Collections.sort(sortedFreshnessIds);
        List<String> digestParts = new ArrayList<>();
        digestParts.add("options");
        digestParts.add(decisionClass);
        digestParts.addAll(sortedFreshnessIds);
        String optionDigest = stableId(digestParts.toArray(new String[0]));
        String frameDigest = stableId(
                gameId,
                Long.toString(decisionOffset),
                actorId,
                subjectId,
                decisionClass,
                optionDigest,
                actorViewHash);

        JsonObject request = new JsonObject();
        request.addProperty("protocol_version", PROTOCOL_VERSION);
        request.addProperty("game_id", gameId);
        request.addProperty("decision_id", decisionId);
        request.addProperty("decision_offset", decisionOffset);
        request.addProperty("actor_id", actorId);
        request.addProperty("seat", XmageFullGameStateRedactor.seat(game, decisionAuthority.getId()));
        request.addProperty("decision_subject_id", subjectId);
        request.addProperty("decision_subject_seat", XmageFullGameStateRedactor.seat(game, decisionSubject.getId()));
        request.addProperty("decision_class", decisionClass);
        request.addProperty("prompt", safeDecision.prompt());
        request.add("context", safeDecision.context());
        request.addProperty("minimum_selections", minimumSelections);
        request.addProperty("maximum_selections", maximumSelections);
        request.add("legal_options", safeDecision.legalOptions());
        request.addProperty("public_state_reference", "actor-view:" + actorViewHash);
        request.addProperty("private_actor_state_reference", "actor-view:" + actorViewHash);
        request.addProperty("actor_view_hash", actorViewHash);
        request.addProperty("option_digest", optionDigest);
        request.addProperty("frame_digest", frameDigest);
        request.addProperty("frame_revision", decisionOffset);
        JsonObject freshness = new JsonObject();
        freshness.addProperty("game_id", gameId);
        freshness.addProperty("actor_id", actorId);
        freshness.addProperty("decision_subject_id", subjectId);
        freshness.addProperty("decision_kind", decisionClass);
        freshness.addProperty("option_digest", optionDigest);
        freshness.addProperty("frame_digest", frameDigest);
        freshness.addProperty("frame_revision", decisionOffset);
        freshness.addProperty("actor_view_hash", actorViewHash);
        request.add("freshness", freshness);
        JsonObject provenance = new JsonObject();
        provenance.addProperty("game_id", "ENGINE_NATIVE");
        provenance.addProperty("decision_id", "ADAPTER_OWNED");
        provenance.addProperty("decision_offset", "ADAPTER_OWNED");
        provenance.addProperty("actor_id", "ENGINE_NATIVE");
        provenance.addProperty("decision_subject_id", "ENGINE_NATIVE");
        provenance.addProperty("decision_class", "ENGINE_NATIVE");
        provenance.addProperty("decision_kind", "ENGINE_NATIVE");
        provenance.addProperty("legal_options", "ENGINE_NATIVE");
        provenance.addProperty("option_digest", "ADAPTER_OWNED");
        provenance.addProperty("frame_digest", "ADAPTER_OWNED");
        provenance.addProperty("frame_revision", "ADAPTER_OWNED");
        provenance.addProperty("actor_view_hash", "ADAPTER_OWNED");
        provenance.addProperty("public_state_reference", "ADAPTER_OWNED");
        provenance.addProperty("private_actor_state_reference", "ADAPTER_OWNED");
        provenance.addProperty("pilot_state", "ENGINE_NATIVE");
        request.add("field_provenance", provenance);
        request.addProperty("timeout_millis", timeoutMillis);
        request.add(
                "source_object",
                safeDecision.sourceObject() == null ? JsonNull.INSTANCE : safeDecision.sourceObject()
        );
        request.addProperty("xmage_identity", game.getClass().getName());
        request.addProperty("protocol_identity", PROTOCOL_VERSION);
        request.add("pilot_state", actorView);

        pendingRequest = request;
        pendingExternalToNative = optionBinding.externalToNative();
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
                pendingExternalToNative = Map.of();
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
                pendingExternalToNative = Map.of();
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
        pendingExternalToNative = Map.of();
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
        // WS56 Phase D: freshness binding. The response must echo the current
        // frame's adapter-owned digests; an older frame's digests (or a
        // tampered digest) fail closed as STALE_DECISION. This binds game
        // identity, principal, decision kind, current option identities, and
        // frame/state identity without a second Rules engine.
        String expectedFrameDigest = pendingRequest.has("frame_digest")
                && !pendingRequest.get("frame_digest").isJsonNull()
                ? pendingRequest.get("frame_digest").getAsString() : "";
        String expectedOptionDigest = pendingRequest.has("option_digest")
                && !pendingRequest.get("option_digest").isJsonNull()
                ? pendingRequest.get("option_digest").getAsString() : "";
        long expectedRevision = pendingRequest.has("frame_revision")
                ? pendingRequest.get("frame_revision").getAsLong()
                : pendingRequest.get("decision_offset").getAsLong();
        if (expectedFrameDigest.isBlank() || expectedOptionDigest.isBlank()) {
            throw new DecisionException("BRIDGE_PROTOCOL_ERROR: pending frame has no freshness binding");
        }
        String submittedFrameDigest = submitted.has("frame_digest") && !submitted.get("frame_digest").isJsonNull()
                ? submitted.get("frame_digest").getAsString().trim() : "";
        String submittedOptionDigest = submitted.has("option_digest") && !submitted.get("option_digest").isJsonNull()
                ? submitted.get("option_digest").getAsString().trim() : "";
        long submittedRevision = submitted.has("frame_revision") && !submitted.get("frame_revision").isJsonNull()
                ? submitted.get("frame_revision").getAsLong() : Long.MIN_VALUE;
        // Backward-compatible alias: older helpers echo decision_offset as revision.
        if (submittedRevision == Long.MIN_VALUE && submitted.has("decision_offset")
                && !submitted.get("decision_offset").isJsonNull()) {
            try {
                submittedRevision = submitted.get("decision_offset").getAsLong();
            } catch (RuntimeException ignored) {
                submittedRevision = Long.MIN_VALUE;
            }
        }
        if (submittedFrameDigest.isBlank() || submittedOptionDigest.isBlank()
                || submittedRevision == Long.MIN_VALUE) {
            throw new DecisionException(
                    "PILOT_RESPONSE_INVALID: missing freshness binding (frame_digest/option_digest/frame_revision required)");
        }
        if (!expectedFrameDigest.equals(submittedFrameDigest)
                || !expectedOptionDigest.equals(submittedOptionDigest)
                || expectedRevision != submittedRevision) {
            throw new DecisionException(
                    "STALE_DECISION: freshness binding mismatch (expected frame " + expectedFrameDigest
                            + " rev " + expectedRevision + ")");
        }

        List<String> selectedExternal = stringArray(submitted, "selected_option_ids");
        List<String> orderingExternal = stringArray(submitted, "ordering");
        Integer numeric = optionalInteger(submitted, "numeric_choice");

        int min = pendingRequest.get("minimum_selections").getAsInt();
        int max = pendingRequest.get("maximum_selections").getAsInt();
        if (selectedExternal.size() < min || selectedExternal.size() > max) {
            throw new DecisionException(
                    "PILOT_RESPONSE_INVALID: selected " + selectedExternal.size()
                            + " options, expected " + min + ".." + max
            );
        }
        if (new HashSet<>(selectedExternal).size() != selectedExternal.size()) {
            throw new DecisionException("PILOT_RESPONSE_INVALID: duplicate option id");
        }

        Set<String> allowed = new HashSet<>();
        for (JsonElement element : pendingRequest.getAsJsonArray("legal_options")) {
            JsonObject option = element.getAsJsonObject();
            if (option.has("option_id") && !option.get("option_id").isJsonNull()) {
                allowed.add(option.get("option_id").getAsString());
            }
        }
        for (String optionId : selectedExternal) {
            if (!allowed.contains(optionId)) {
                throw new DecisionException("ILLEGAL_ACTION: option not offered by XMage: " + optionId);
            }
        }
        for (String optionId : orderingExternal) {
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
        }

        List<String> selectedNative = nativeOptionIds(selectedExternal);
        List<String> orderingNative = nativeOptionIds(orderingExternal);
        response = new DecisionResponse(
                decisionId,
                actorId,
                selectedNative,
                orderingNative,
                numeric
        );
        recordDecisionAccepted(pendingRequest, selectedExternal, numeric);
        notifyAll();
    }

    synchronized void failClosed(String failureCode, String detail) {
        String code = failureCode == null || failureCode.isBlank()
                ? "BRIDGE_PROTOCOL_ERROR"
                : failureCode.trim();
        String message = code + (detail == null || detail.isBlank() ? "" : ": " + detail.trim());
        terminalFailure = new DecisionException(message);
        pendingExternalToNative = Map.of();
        recordFailure(message);
        notifyAll();
    }

    synchronized void markTerminal() {
        terminal = true;
        pendingExternalToNative = Map.of();
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

    private List<String> nativeOptionIds(List<String> externalIds) {
        List<String> nativeIds = new ArrayList<>(externalIds.size());
        for (String externalId : externalIds) {
            String nativeId = pendingExternalToNative.get(externalId);
            if (nativeId == null) {
                throw new DecisionException(
                        "COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER: missing native binding for "
                                + externalId
                );
            }
            nativeIds.add(nativeId);
        }
        return List.copyOf(nativeIds);
    }

    private void recordDecisionRequested(JsonObject request) {
        JsonObject event = new JsonObject();
        event.addProperty("sequence", transcript.size() + 1L);
        event.addProperty("kind", "decision_requested");
        event.addProperty("decision_class", request.get("decision_class").getAsString());
        event.addProperty("actor_seat", request.get("seat").getAsInt());
        event.addProperty("decision_subject_seat", request.get("decision_subject_seat").getAsInt());
        event.addProperty("prompt", request.get("prompt").getAsString());
        event.addProperty("public_state_reference", request.get("public_state_reference").getAsString());
        event.addProperty("private_actor_state_reference", request.get("private_actor_state_reference").getAsString());
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

    private void recordDecisionAccepted(JsonObject request, List<String> selected, Integer numeric) {
        JsonObject event = new JsonObject();
        event.addProperty("sequence", transcript.size() + 1L);
        event.addProperty("kind", "decision_accepted");
        event.addProperty("decision_class", request.get("decision_class").getAsString());
        event.addProperty("actor_seat", request.get("seat").getAsInt());
        event.addProperty("decision_subject_seat", request.get("decision_subject_seat").getAsInt());
        event.addProperty("prompt", request.get("prompt").getAsString());
        JsonArray selectedTypes = new JsonArray();
        JsonArray selectedLabels = new JsonArray();
        for (String selectedId : selected) {
            for (JsonElement element : request.getAsJsonArray("legal_options")) {
                JsonObject option = element.getAsJsonObject();
                if (option.has("option_id") && selectedId.equals(option.get("option_id").getAsString())) {
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
        transcript.add(event);
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

    /** Per-game engine object identity carries no Rules content and must not
     * enter twin-stable projections (primary and replica mint distinct ids). */
    private static final java.util.regex.Pattern OBJECT_ID_UUID = java.util.regex.Pattern.compile(
            "object_id='[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'");

    static String redactObjectIds(String text) {
        return text == null ? null : OBJECT_ID_UUID.matcher(text).replaceAll("object_id='#'");
    }

    private static JsonObject redactObjectIds(JsonObject object) {
        for (Map.Entry<String, com.google.gson.JsonElement> entry : object.entrySet()) {
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
            throw new DecisionException(
                    "PILOT_RESPONSE_INVALID: " + property + " must be integer",
                    exc
            );
        }
    }
}

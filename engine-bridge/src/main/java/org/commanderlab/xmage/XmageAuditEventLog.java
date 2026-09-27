package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

/**
 * Per-game external audit log for the real XMage bridge.
 *
 * <p>This intentionally records lifecycle and externally controlled action
 * boundaries observed by the bridge. It is not presented as an exhaustive tap
 * of every internal XMage {@code GameEvent}. All recorded action/state data is
 * derived from the live XMage game used by the bridge.</p>
 */
final class XmageAuditEventLog {

    private final String gameId;
    private final String engineGameId;
    private final List<JsonObject> events = new ArrayList<>();
    private long nextSequence = 1L;

    XmageAuditEventLog(String gameId, String engineGameId) {
        this.gameId = requireText(gameId, "gameId");
        this.engineGameId = requireText(engineGameId, "engineGameId");
    }

    long latestOffset() {
        return nextSequence - 1L;
    }

    void record(
            String eventType,
            String actorId,
            String decisionId,
            String actionId,
            String preStateHash,
            String postStateHash,
            JsonObject payload
    ) {
        long sequence = nextSequence++;
        JsonObject event = new JsonObject();
        event.addProperty(
                "event_id",
                sha256(gameId + "|" + sequence + "|" + requireText(eventType, "eventType"))
        );
        event.addProperty("game_id", gameId);
        event.addProperty("sequence", sequence);
        event.addProperty("event_type", eventType);
        addNullableString(event, "actor_id", actorId);

        JsonObject eventPayload = payload == null ? new JsonObject() : payload.deepCopy();
        eventPayload.addProperty("engine_game_id", engineGameId);
        addNullableString(eventPayload, "decision_id", decisionId);
        addNullableString(eventPayload, "action_id", actionId);
        event.add("payload", eventPayload);

        addNullableString(event, "pre_state_hash", preStateHash);
        addNullableString(event, "post_state_hash", postStateHash);
        events.add(event);
    }

    JsonObject exportLog(long afterOffset) {
        if (afterOffset < 0L || afterOffset > latestOffset()) {
            throw new IllegalArgumentException(
                    "after_offset must be between 0 and " + latestOffset()
            );
        }

        JsonArray selected = new JsonArray();
        for (JsonObject event : events) {
            if (event.get("sequence").getAsLong() > afterOffset) {
                selected.add(event.deepCopy());
            }
        }

        JsonObject log = new JsonObject();
        log.addProperty("backend", XmageProvider.ENGINE);
        log.addProperty("session_id", gameId);
        log.add("events", selected);
        log.add("raw_lines", new JsonArray());
        log.addProperty("log_sha256", fullLogSha256());
        return log;
    }

    String fullLogSha256() {
        JsonArray all = new JsonArray();
        for (JsonObject event : events) {
            all.add(event.deepCopy());
        }
        return sha256(all.toString());
    }

    static String stateHash(JsonObject state) {
        JsonObject normalized = state.deepCopy();
        normalized.remove("event_sequence");
        return sha256(normalized.toString());
    }

    private static void addNullableString(JsonObject object, String property, String value) {
        if (value == null || value.isBlank()) {
            object.add(property, JsonNull.INSTANCE);
        } else {
            object.addProperty(property, value);
        }
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(
                    digest.digest(value.getBytes(StandardCharsets.UTF_8))
            );
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException("SHA-256 is unavailable", exc);
        }
    }

    private static String requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be nonblank");
        }
        return value.trim();
    }
}

package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;

/**
 * Whitelist projection for audit material that may outlive the actor-private
 * decision request.
 *
 * <p>This class intentionally never copies prompts, option identifiers,
 * labels, metadata, actor-private state references or failure details. The
 * live decision request remains actor scoped; durable/exported audit material
 * is structural only.</p>
 */
final class XmageAuditSurfaceRedactor {

    private XmageAuditSurfaceRedactor() {
    }

    static JsonArray redactTranscript(JsonArray raw) {
        JsonArray safe = new JsonArray();
        if (raw == null) {
            return safe;
        }
        for (JsonElement element : raw) {
            if (!element.isJsonObject()) {
                continue;
            }
            JsonObject source = element.getAsJsonObject();
            JsonObject event = new JsonObject();
            copyNumber(source, event, "sequence");
            copyNumber(source, event, "offset");
            copyText(source, event, "kind");
            copyText(source, event, "event_type");
            copyText(source, event, "decision_class");
            copyNumber(source, event, "actor_seat");
            copyNumber(source, event, "decision_subject_seat");

            if (source.has("legal_option_types") && source.get("legal_option_types").isJsonArray()) {
                JsonArray types = source.getAsJsonArray("legal_option_types");
                event.addProperty("legal_option_count", types.size());
            }
            if (source.has("selected_option_types") && source.get("selected_option_types").isJsonArray()) {
                JsonArray selected = source.getAsJsonArray("selected_option_types");
                event.addProperty("selected_option_count", selected.size());
            }
            if (source.has("numeric_choice")) {
                event.addProperty(
                        "numeric_choice_present",
                        !source.get("numeric_choice").isJsonNull()
                );
            }
            if ("controller_failure".equals(text(source, "event_type"))) {
                event.addProperty("failure_code", failureCode(source));
            }
            safe.add(event);
        }
        return safe;
    }

    static JsonObject redactFailure(Throwable failure) {
        JsonObject safe = new JsonObject();
        if (failure == null) {
            safe.add("type", JsonNull.INSTANCE);
            safe.add("code", JsonNull.INSTANCE);
            return safe;
        }
        safe.addProperty("type", failure.getClass().getName());
        safe.addProperty("code", leadingCode(failure.getMessage()));
        return safe;
    }

    static JsonObject redactFailure(String type, String message) {
        JsonObject safe = new JsonObject();
        safe.addProperty("type", type == null || type.isBlank() ? "unknown" : type);
        safe.addProperty("code", leadingCode(message));
        return safe;
    }

    private static String failureCode(JsonObject event) {
        if (!event.has("payload") || !event.get("payload").isJsonObject()) {
            return "CONTROLLER_FAILURE";
        }
        JsonObject payload = event.getAsJsonObject("payload");
        String message = text(payload, "message");
        return leadingCode(message);
    }

    private static String leadingCode(String message) {
        if (message == null || message.isBlank()) {
            return "UNKNOWN_FAILURE";
        }
        int colon = message.indexOf(':');
        String candidate = (colon < 0 ? message : message.substring(0, colon)).trim();
        if (candidate.matches("[A-Z][A-Z0-9_]{2,63}")) {
            return candidate;
        }
        return "UNCLASSIFIED_FAILURE";
    }

    private static String text(JsonObject object, String key) {
        if (!object.has(key) || object.get(key).isJsonNull()) {
            return "";
        }
        return object.get(key).getAsString();
    }

    private static void copyText(JsonObject source, JsonObject target, String key) {
        if (source.has(key) && !source.get(key).isJsonNull()) {
            target.addProperty(key, source.get(key).getAsString());
        }
    }

    private static void copyNumber(JsonObject source, JsonObject target, String key) {
        if (source.has(key) && source.get(key).isJsonPrimitive()
                && source.get(key).getAsJsonPrimitive().isNumber()) {
            target.addProperty(key, source.get(key).getAsLong());
        }
    }
}

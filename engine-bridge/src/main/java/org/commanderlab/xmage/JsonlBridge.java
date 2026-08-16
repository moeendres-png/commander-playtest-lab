package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

final class JsonlBridge {

    record Result(String json, boolean shutdown) {
    }

    Result handle(String input) {
        JsonObject request;

        try {
            request = JsonParser.parseString(input).getAsJsonObject();
        } catch (Exception ex) {
            return error(
                    "",
                    "invalid_json",
                    "Request is not a valid JSON object",
                    false
            );
        }

        String requestId = stringValue(request, "request_id");
        String protocolVersion = stringValue(request, "protocol_version");

        if (!XmageProvider.PROTOCOL_VERSION.equals(protocolVersion)) {
            return error(
                    requestId,
                    "protocol_version_mismatch",
                    "Expected protocol "
                            + XmageProvider.PROTOCOL_VERSION
                            + " but received "
                            + protocolVersion,
                    false
            );
        }

        String messageType = stringValue(request, "message_type");
        if (messageType.isBlank()) {
            messageType = stringValue(request, "method");
        }

        return switch (messageType) {
            case "start_engine" ->
                    success(requestId, startedPayload(), false);

            case "get_provider_version" ->
                    success(
                            requestId,
                            XmageProvider.providerVersion(),
                            false
                    );

            case "get_capabilities" ->
                    success(
                            requestId,
                            XmageProvider.capabilitiesPayload(),
                            false
                    );

            case "shutdown_engine" ->
                    success(requestId, shutdownPayload(), true);

            default ->
                    error(
                            requestId,
                            "unsupported_message",
                            "B1 does not support message type: " + messageType,
                            false
                    );
        };
    }

    private static JsonObject startedPayload() {
        XmageProvider.verifyRuntimeLoaded();

        JsonObject payload = new JsonObject();
        payload.addProperty("engine", XmageProvider.ENGINE);
        payload.addProperty("started", true);
        payload.addProperty(
                "phase",
                "B1_HANDSHAKE_ONLY"
        );
        return payload;
    }

    private static JsonObject shutdownPayload() {
        JsonObject payload = new JsonObject();
        payload.addProperty("engine", XmageProvider.ENGINE);
        payload.addProperty("shutdown", true);
        return payload;
    }

    private static Result success(
            String requestId,
            JsonObject payload,
            boolean shutdown
    ) {
        JsonObject response = baseResponse(requestId);
        response.addProperty("success", true);
        response.addProperty("status", "ok");
        response.add("payload", payload);
        response.addProperty("engine_event_offset", 0);
        return new Result(response.toString(), shutdown);
    }

    private static Result error(
            String requestId,
            String code,
            String message,
            boolean retryable
    ) {
        JsonObject response = baseResponse(requestId);
        response.addProperty("success", false);
        response.addProperty("status", "error");

        JsonObject error = new JsonObject();
        error.addProperty("code", code);
        error.addProperty("message", message);
        error.addProperty("retryable", retryable);

        com.google.gson.JsonArray errors =
                new com.google.gson.JsonArray();
        errors.add(error);

        response.add("errors", errors);
        response.addProperty("engine_event_offset", 0);

        return new Result(response.toString(), false);
    }

    private static JsonObject baseResponse(String requestId) {
        JsonObject response = new JsonObject();
        response.addProperty(
                "protocol_version",
                XmageProvider.PROTOCOL_VERSION
        );
        response.addProperty("request_id", requestId);
        return response;
    }

    private static String stringValue(
            JsonObject object,
            String property
    ) {
        if (!object.has(property)
                || object.get(property).isJsonNull()) {
            return "";
        }
        return object.get(property).getAsString();
    }
}
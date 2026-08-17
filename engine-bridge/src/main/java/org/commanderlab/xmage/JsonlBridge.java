package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.util.ArrayList;
import java.util.List;

final class JsonlBridge {

    private final XmageDeckImporter deckImporter =
            new XmageDeckImporter();

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

            case "import_deck" ->
                    importDeck(requestId, request);

            case "shutdown_engine" ->
                    success(requestId, shutdownPayload(), true);

            default ->
                    error(
                            requestId,
                            "unsupported_message",
                            "B2 does not support message type: " + messageType,
                            false
                    );
        };
    }

    private Result importDeck(
            String requestId,
            JsonObject request
    ) {
        try {
            if (!request.has("payload")
                    || !request.get("payload").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_deck_payload",
                        "IMPORT_DECK requires an object payload",
                        false
                );
            }

            JsonObject payload =
                    request.getAsJsonObject("payload");

            if (!payload.has("deck")
                    || !payload.get("deck").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_deck_payload",
                        "IMPORT_DECK requires payload.deck",
                        false
                );
            }

            JsonObject deck =
                    payload.getAsJsonObject("deck");

            String deckId =
                    stringValue(deck, "deck_id");

            String deckHash =
                    stringValue(deck, "deck_hash");

            List<String> mainboard =
                    requiredStringArray(
                            deck,
                            "mainboard"
                    );

            List<String> commanders =
                    requiredStringArray(
                            deck,
                            "commander_names"
                    );

            List<String> sideboard =
                    optionalStringArray(
                            deck,
                            "sideboard"
                    );

            /*
             * B2 supports Commander mainboard + commander zone only.
             * Do not silently reinterpret a conventional sideboard.
             */
            if (!sideboard.isEmpty()) {
                return error(
                        requestId,
                        "unsupported_deck_sideboard",
                        "B2 IMPORT_DECK does not support nonempty sideboard",
                        false
                );
            }

            XmageDeckImporter.ImportResult imported =
                    deckImporter.importCommanderDeck(
                            deckId,
                            deckHash,
                            mainboard,
                            commanders
                    );

            JsonObject handle =
                    new JsonObject();

            handle.addProperty(
                    "backend",
                    XmageProvider.ENGINE
            );

            handle.addProperty(
                    "handle_id",
                    imported.deckHandle()
            );

            handle.addProperty(
                    "deck_id",
                    imported.deckId()
            );

            handle.addProperty(
                    "deck_hash",
                    imported.deckHash()
            );

            JsonArray commanderNames =
                    new JsonArray();

            commanders.forEach(
                    commanderNames::add
            );

            handle.add(
                    "commander_names",
                    commanderNames
            );

            handle.addProperty(
                    "accepted_cards",
                    imported.mainboardCount()
                            + imported.commanderCount()
            );

            handle.add(
                    "rejected_cards",
                    new JsonArray()
            );

            handle.add(
                    "warnings",
                    new JsonArray()
            );

            JsonObject responsePayload =
                    new JsonObject();

            responsePayload.add(
                    "deck_handle",
                    handle
            );

            return success(
                    requestId,
                    responsePayload,
                    false
            );

        } catch (XmageDeckImporter.ImportException exc) {
            return error(
                    requestId,
                    "deck_import_failed",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "invalid_deck_payload",
                    exc.getClass().getSimpleName()
                            + ": "
                            + exc.getMessage(),
                    false
            );
        }
    }

    private static List<String> requiredStringArray(
            JsonObject object,
            String property
    ) {
        if (!object.has(property)
                || object.get(property).isJsonNull()) {
            throw new IllegalArgumentException(
                    "Missing required array: "
                            + property
            );
        }

        return stringArray(
                object,
                property
        );
    }

    private static List<String> optionalStringArray(
            JsonObject object,
            String property
    ) {
        if (!object.has(property)
                || object.get(property).isJsonNull()) {
            return List.of();
        }

        return stringArray(
                object,
                property
        );
    }

    private static List<String> stringArray(
            JsonObject object,
            String property
    ) {
        if (!object.get(property).isJsonArray()) {
            throw new IllegalArgumentException(
                    property
                            + " must be an array"
            );
        }

        JsonArray array =
                object.getAsJsonArray(property);

        List<String> values =
                new ArrayList<>(array.size());

        for (int index = 0; index < array.size(); index++) {
            if (!array.get(index).isJsonPrimitive()
                    || !array.get(index)
                    .getAsJsonPrimitive()
                    .isString()) {
                throw new IllegalArgumentException(
                        property
                                + "["
                                + index
                                + "] must be a string"
                );
            }

            String value =
                    array.get(index)
                            .getAsString()
                            .trim();

            if (value.isBlank()) {
                throw new IllegalArgumentException(
                        property
                                + "["
                                + index
                                + "] must be nonblank"
                );
            }

            values.add(value);
        }

        return List.copyOf(values);
    }

    private static JsonObject startedPayload() {
        XmageProvider.verifyRuntimeLoaded();

        JsonObject payload = new JsonObject();
        payload.addProperty("engine", XmageProvider.ENGINE);
        payload.addProperty("started", true);
        payload.addProperty(
                "phase",
                "B2_DECK_IMPORT"
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
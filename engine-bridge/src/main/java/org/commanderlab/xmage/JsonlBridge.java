package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

final class JsonlBridge {

    private final XmageDeckImporter deckImporter = new XmageDeckImporter();
    private final XmageGameManager gameManager = new XmageGameManager(deckImporter);

    /*
     * Protocol game_id is stable and client-facing. The mutable XMage Game is
     * addressed internally by a process-local xmage-game-* handle.
     */
    private final Map<String, String> gameHandlesById = new HashMap<>();

    record Result(String json, boolean shutdown) {
    }

    Result handle(String input) {
        JsonObject request;
        try {
            request = JsonParser.parseString(input).getAsJsonObject();
        } catch (Exception exc) {
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
            case "start_engine" -> success(requestId, startedPayload(), false);
            case "get_provider_version" -> success(
                    requestId,
                    XmageProvider.providerVersion(),
                    false
            );
            case "get_capabilities" -> success(
                    requestId,
                    XmageProvider.capabilitiesPayload(),
                    false
            );
            case "import_deck" -> importDeck(requestId, request);
            case "create_commander_game" -> createCommanderGame(requestId, request);
            case "start_game" -> startGame(requestId, request);
            case "get_game_state" -> getGameState(requestId, request);
            case "get_legal_actions" -> getLegalActions(requestId, request);
            case "pass_priority" -> passPriority(requestId, request);
            case "submit_action" -> submitAction(requestId, request);
            case "shutdown_engine" -> success(requestId, shutdownPayload(), true);
            default -> error(
                    requestId,
                    "unsupported_message",
                    "Current XMage bridge does not support message type: " + messageType,
                    false
            );
        };
    }

    private Result importDeck(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "invalid_deck_payload",
                    "IMPORT_DECK requires an object payload"
            );
            if (!payload.has("deck") || !payload.get("deck").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_deck_payload",
                        "IMPORT_DECK requires payload.deck",
                        false
                );
            }

            JsonObject deck = payload.getAsJsonObject("deck");
            String deckId = stringValue(deck, "deck_id");
            String deckHash = stringValue(deck, "deck_hash");
            List<String> mainboard = requiredStringArray(deck, "mainboard");
            List<String> commanders = requiredStringArray(deck, "commander_names");
            List<String> sideboard = optionalStringArray(deck, "sideboard");

            if (!sideboard.isEmpty()) {
                return error(
                        requestId,
                        "unsupported_deck_sideboard",
                        "B2 IMPORT_DECK does not support nonempty sideboard",
                        false
                );
            }

            XmageDeckImporter.ImportResult imported = deckImporter.importCommanderDeck(
                    deckId,
                    deckHash,
                    mainboard,
                    commanders
            );

            JsonObject handle = new JsonObject();
            handle.addProperty("backend", XmageProvider.ENGINE);
            handle.addProperty("handle_id", imported.deckHandle());
            handle.addProperty("deck_id", imported.deckId());
            handle.addProperty("deck_hash", imported.deckHash());

            JsonArray commanderNames = new JsonArray();
            commanders.forEach(commanderNames::add);
            handle.add("commander_names", commanderNames);
            handle.addProperty(
                    "accepted_cards",
                    imported.mainboardCount() + imported.commanderCount()
            );
            handle.add("rejected_cards", new JsonArray());
            handle.add("warnings", new JsonArray());

            JsonObject responsePayload = new JsonObject();
            responsePayload.add("deck_handle", handle);
            return success(requestId, responsePayload, false);
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
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private Result createCommanderGame(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "invalid_game_payload",
                    "CREATE_COMMANDER_GAME requires an object payload"
            );
            if (!payload.has("request") || !payload.get("request").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_game_payload",
                        "CREATE_COMMANDER_GAME requires payload.request",
                        false
                );
            }

            JsonObject gameRequest = payload.getAsJsonObject("request");
            String gameId = stringValue(gameRequest, "game_id").trim();
            if (gameId.isBlank()) {
                return error(
                        requestId,
                        "invalid_game_payload",
                        "game_id must be nonblank",
                        false
                );
            }

            String format = stringValue(gameRequest, "format").trim();
            if (!"commander".equals(format)) {
                return error(
                        requestId,
                        "unsupported_game_format",
                        "B4 compatibility bridge supports only format=commander",
                        false
                );
            }

            /*
             * Seeded execution and deterministic starting-state injection are
             * still unproven. Never silently accept them.
             */
            if (gameRequest.has("seed") && !gameRequest.get("seed").isJsonNull()) {
                return error(
                        requestId,
                        "unsupported_game_option",
                        "B4-C does not support seed",
                        false
                );
            }
            if (gameRequest.has("deterministic_starting_state")
                    && !gameRequest.get("deterministic_starting_state").isJsonNull()) {
                return error(
                        requestId,
                        "unsupported_game_option",
                        "B4-C does not support deterministic_starting_state",
                        false
                );
            }

            List<String> deckHandles = requiredStringArray(gameRequest, "deck_handles");
            int startingPlayerSeat = optionalInt(
                    gameRequest,
                    "starting_player_seat",
                    0
            );
            int startingLife = optionalInt(gameRequest, "starting_life", 40);
            boolean externalControl = optionalBoolean(
                    gameRequest,
                    "external_control",
                    false
            );

            if (gameHandlesById.containsKey(gameId)) {
                return error(
                        requestId,
                        "duplicate_game_id",
                        "Game already exists: " + gameId,
                        false
                );
            }

            XmageGameManager.CreateResult created = gameManager.createCommanderGame(
                    gameId,
                    new ArrayList<>(deckHandles),
                    startingPlayerSeat,
                    startingLife,
                    externalControl
            );
            gameHandlesById.put(created.gameId(), created.gameHandle());

            JsonObject responsePayload = new JsonObject();
            responsePayload.addProperty("game_id", created.gameId());
            responsePayload.addProperty("game_handle", created.gameHandle());
            responsePayload.addProperty("engine_game_id", created.engineGameId());
            responsePayload.addProperty("player_count", created.playerCount());
            responsePayload.addProperty(
                    "starting_player_seat",
                    created.startingPlayerSeat()
            );
            responsePayload.addProperty("external_control", created.externalControl());
            return success(requestId, responsePayload, false);
        } catch (XmageGameManager.GameException exc) {
            return error(
                    requestId,
                    "game_creation_failed",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "invalid_game_payload",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private Result startGame(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "invalid_start_payload",
                    "START_GAME requires an object payload"
            );
            String gameId = requestGameId(request, payload);
            if (gameId.isBlank()) {
                return error(
                        requestId,
                        "invalid_start_payload",
                        "START_GAME requires nonblank game_id",
                        false
                );
            }

            String gameHandle = gameHandlesById.get(gameId);
            if (gameHandle == null) {
                return error(
                        requestId,
                        "unknown_game_id",
                        "Unknown process-local game_id: " + gameId,
                        false
                );
            }

            XmageGameManager.StartResult started = gameManager.startGame(gameHandle);
            JsonObject responsePayload = new JsonObject();
            responsePayload.addProperty("game_id", started.gameId());
            responsePayload.addProperty("game_handle", started.gameHandle());
            responsePayload.addProperty("engine_game_id", started.engineGameId());
            responsePayload.addProperty("player_count", started.playerCount());
            responsePayload.addProperty(
                    "starting_player_id",
                    started.startingPlayerId()
            );
            responsePayload.addProperty("turn_number", started.turnNumber());
            responsePayload.addProperty("paused", started.paused());
            responsePayload.addProperty("external_control", started.externalControl());
            return success(requestId, responsePayload, false);
        } catch (XmageGameManager.GameException exc) {
            return error(
                    requestId,
                    "game_start_failed",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "invalid_start_payload",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private Result getGameState(String requestId, JsonObject request) {
        try {
            JsonObject payload = optionalObjectPayload(request);
            String gameId = requestGameId(request, payload);
            if (gameId.isBlank()) {
                return error(
                        requestId,
                        "invalid_state_payload",
                        "GET_GAME_STATE requires nonblank game_id",
                        false
                );
            }

            String gameHandle = gameHandlesById.get(gameId);
            if (gameHandle == null) {
                return error(
                        requestId,
                        "unknown_game_id",
                        "Unknown process-local game_id: " + gameId,
                        false
                );
            }

            XmageGameManager.StateSnapshot snapshot = gameManager.snapshotState(gameHandle);
            JsonObject responsePayload = new JsonObject();
            responsePayload.addProperty("game_id", snapshot.gameId());
            responsePayload.addProperty("engine_game_id", snapshot.engineGameId());
            responsePayload.addProperty(
                    "state_observation_offset",
                    snapshot.stateObservationOffset()
            );
            responsePayload.addProperty("seed_controlled", false);
            responsePayload.addProperty("legal_actions_complete", false);
            responsePayload.addProperty("event_log_supported", false);
            responsePayload.add("state", snapshot.state());
            return success(requestId, responsePayload, false);
        } catch (XmageGameManager.GameException exc) {
            return error(
                    requestId,
                    "game_state_failed",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "invalid_state_payload",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private Result getLegalActions(String requestId, JsonObject request) {
        try {
            JsonObject payload = optionalObjectPayload(request);
            String gameId = requestGameId(request, payload);
            if (gameId.isBlank()) {
                return error(
                        requestId,
                        "invalid_legal_actions_payload",
                        "GET_LEGAL_ACTIONS requires nonblank game_id",
                        false
                );
            }

            String gameHandle = gameHandlesById.get(gameId);
            if (gameHandle == null) {
                return error(
                        requestId,
                        "unknown_game_id",
                        "Unknown process-local game_id: " + gameId,
                        false
                );
            }

            XmageGameManager.LegalActionsSnapshot snapshot =
                    gameManager.legalActions(gameHandle);

            JsonObject responsePayload = legalActionsPayload(snapshot);
            responsePayload.addProperty("global_capability_promoted", false);
            return success(requestId, responsePayload, false);
        } catch (XmageGameManager.GameException exc) {
            return error(
                    requestId,
                    "legal_actions_failed",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "invalid_legal_actions_payload",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private Result passPriority(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "invalid_pass_priority_payload",
                    "PASS_PRIORITY requires an object payload"
            );
            String gameId = requestGameId(request, payload);
            String gameHandle = requireGameHandle(gameId);
            XmageGameManager.LegalActionsSnapshot before = gameManager.legalActions(gameHandle);

            XmageActionExecutor.ExecutionResult executed = XmageActionExecutor.passPriority(
                    gameManager.requireGame(gameHandle),
                    before,
                    stringValue(payload, "decision_id").trim(),
                    stringValue(payload, "actor_id").trim(),
                    stringValue(payload, "action_id").trim()
            );

            XmageGameManager.StateSnapshot state = gameManager.snapshotState(gameHandle);
            XmageGameManager.LegalActionsSnapshot after = gameManager.legalActions(gameHandle);
            JsonObject responsePayload = actionExecutionPayload(executed, state, after);
            responsePayload.addProperty("bounded_submission", true);
            responsePayload.addProperty("global_capability_promoted", false);
            return success(requestId, responsePayload, false);
        } catch (XmageActionExecutor.ActionException exc) {
            return error(requestId, "external_action_rejected", exc.getMessage(), false);
        } catch (XmageGameManager.GameException exc) {
            return error(requestId, "pass_priority_failed", exc.getMessage(), false);
        } catch (Exception exc) {
            return error(
                    requestId,
                    "invalid_pass_priority_payload",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private Result submitAction(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "invalid_submit_action_payload",
                    "SUBMIT_ACTION requires an object payload"
            );
            String gameId = requestGameId(request, payload);
            String gameHandle = requireGameHandle(gameId);
            if (!payload.has("proposal") || !payload.get("proposal").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_submit_action_payload",
                        "SUBMIT_ACTION requires payload.proposal",
                        false
                );
            }

            XmageGameManager.LegalActionsSnapshot before = gameManager.legalActions(gameHandle);
            XmageActionExecutor.ExecutionResult executed = XmageActionExecutor.submitAction(
                    gameManager.requireGame(gameHandle),
                    before,
                    stringValue(payload, "decision_id").trim(),
                    payload.getAsJsonObject("proposal")
            );

            XmageGameManager.StateSnapshot state = gameManager.snapshotState(gameHandle);
            XmageGameManager.LegalActionsSnapshot after = gameManager.legalActions(gameHandle);
            JsonObject responsePayload = actionExecutionPayload(executed, state, after);
            responsePayload.addProperty("bounded_submission", true);
            responsePayload.addProperty("global_capability_promoted", false);
            return success(requestId, responsePayload, false);
        } catch (XmageActionExecutor.ActionException exc) {
            return error(requestId, "external_action_rejected", exc.getMessage(), false);
        } catch (XmageGameManager.GameException exc) {
            return error(requestId, "submit_action_failed", exc.getMessage(), false);
        } catch (Exception exc) {
            return error(
                    requestId,
                    "invalid_submit_action_payload",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private String requireGameHandle(String gameId) {
        if (gameId == null || gameId.isBlank()) {
            throw new IllegalArgumentException("game_id must be nonblank");
        }
        String gameHandle = gameHandlesById.get(gameId);
        if (gameHandle == null) {
            throw new XmageGameManager.GameException(
                    "Unknown process-local game_id: " + gameId
            );
        }
        return gameHandle;
    }

    private static JsonObject legalActionsPayload(
            XmageGameManager.LegalActionsSnapshot snapshot
    ) {
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", snapshot.gameId());
        payload.addProperty("engine_game_id", snapshot.engineGameId());
        payload.addProperty("decision_offset", snapshot.decisionOffset());
        payload.addProperty("decision_id", snapshot.decisionId());
        payload.addProperty("actor_id", snapshot.actorId());
        payload.addProperty("decision_kind", snapshot.decisionKind());
        payload.addProperty("complete", snapshot.complete());
        JsonArray actions = new JsonArray();
        snapshot.actions().forEach(actions::add);
        payload.add("actions", actions);
        return payload;
    }

    private static JsonObject actionExecutionPayload(
            XmageActionExecutor.ExecutionResult executed,
            XmageGameManager.StateSnapshot state,
            XmageGameManager.LegalActionsSnapshot after
    ) {
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", state.gameId());
        payload.addProperty("engine_game_id", state.engineGameId());
        payload.addProperty("executed_decision_id", executed.decisionId());
        payload.addProperty("executed_action_id", executed.actionId());
        payload.addProperty("executed_action_type", executed.actionType());
        payload.addProperty("executed_actor_id", executed.actorId());
        if (executed.sourceObjectId() == null) {
            payload.add("executed_source_object_id", com.google.gson.JsonNull.INSTANCE);
        } else {
            payload.addProperty("executed_source_object_id", executed.sourceObjectId());
        }
        if (executed.sourceName() == null) {
            payload.add("executed_source_name", com.google.gson.JsonNull.INSTANCE);
        } else {
            payload.addProperty("executed_source_name", executed.sourceName());
        }
        payload.addProperty("state_observation_offset", state.stateObservationOffset());
        payload.add("state", state.state());
        payload.add("next_decision", legalActionsPayload(after));
        return payload;
    }

    private static JsonObject requireObjectPayload(
            JsonObject request,
            String code,
            String message
    ) {
        if (!request.has("payload") || !request.get("payload").isJsonObject()) {
            throw new IllegalArgumentException(code + ": " + message);
        }
        return request.getAsJsonObject("payload");
    }

    private static JsonObject optionalObjectPayload(JsonObject request) {
        return request.has("payload") && request.get("payload").isJsonObject()
                ? request.getAsJsonObject("payload")
                : new JsonObject();
    }

    private static String requestGameId(JsonObject request, JsonObject payload) {
        String gameId = stringValue(request, "game_id").trim();
        if (gameId.isBlank()) {
            gameId = stringValue(payload, "game_id").trim();
        }
        return gameId;
    }

    private static List<String> requiredStringArray(
            JsonObject object,
            String property
    ) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            throw new IllegalArgumentException(
                    "Missing required array: " + property
            );
        }
        return stringArray(object, property);
    }

    private static List<String> optionalStringArray(
            JsonObject object,
            String property
    ) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return List.of();
        }
        return stringArray(object, property);
    }

    private static List<String> stringArray(JsonObject object, String property) {
        if (!object.get(property).isJsonArray()) {
            throw new IllegalArgumentException(property + " must be an array");
        }

        JsonArray array = object.getAsJsonArray(property);
        List<String> values = new ArrayList<>(array.size());
        for (int index = 0; index < array.size(); index++) {
            if (!array.get(index).isJsonPrimitive()
                    || !array.get(index).getAsJsonPrimitive().isString()) {
                throw new IllegalArgumentException(
                        property + "[" + index + "] must be a string"
                );
            }
            String value = array.get(index).getAsString().trim();
            if (value.isBlank()) {
                throw new IllegalArgumentException(
                        property + "[" + index + "] must be nonblank"
                );
            }
            values.add(value);
        }
        return List.copyOf(values);
    }

    private static int optionalInt(
            JsonObject object,
            String property,
            int defaultValue
    ) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return defaultValue;
        }
        if (!object.get(property).isJsonPrimitive()
                || !object.get(property).getAsJsonPrimitive().isNumber()) {
            throw new IllegalArgumentException(property + " must be an integer");
        }
        String raw = object.get(property).getAsString();
        if (!raw.matches("-?\\d+")) {
            throw new IllegalArgumentException(property + " must be an integer");
        }
        return Integer.parseInt(raw);
    }

    private static boolean optionalBoolean(
            JsonObject object,
            String property,
            boolean defaultValue
    ) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return defaultValue;
        }
        if (!object.get(property).isJsonPrimitive()
                || !object.get(property).getAsJsonPrimitive().isBoolean()) {
            throw new IllegalArgumentException(property + " must be a boolean");
        }
        return object.get(property).getAsBoolean();
    }

    private static JsonObject startedPayload() {
        XmageProvider.verifyRuntimeLoaded();
        JsonObject payload = new JsonObject();
        payload.addProperty("engine", XmageProvider.ENGINE);
        payload.addProperty("started", true);
        payload.addProperty("phase", "B4C_BOUNDED_ACTION_SUBMISSION");
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
        JsonArray errors = new JsonArray();
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

    private static String stringValue(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return "";
        }
        return object.get(property).getAsString();
    }

    private static String exceptionMessage(Exception exc) {
        return exc.getClass().getSimpleName() + ": " + exc.getMessage();
    }
}

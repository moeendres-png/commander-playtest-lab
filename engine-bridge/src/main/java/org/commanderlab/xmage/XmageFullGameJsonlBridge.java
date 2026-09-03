package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.util.ArrayList;
import java.util.List;

/** Dedicated JSONL surface for one isolated full Commander game. */
final class XmageFullGameJsonlBridge {

    private final XmageDeckImporter deckImporter = new XmageDeckImporter();
    private XmageFullGameSession session;

    record Result(String json, boolean shutdown) {
    }

    Result handle(String input) {
        JsonObject request;
        try {
            request = JsonParser.parseString(input).getAsJsonObject();
        } catch (Exception exc) {
            return error("", "invalid_json", "Request is not a valid JSON object", false);
        }

        String requestId = stringValue(request, "request_id");
        String protocolVersion = stringValue(request, "protocol_version");
        if (!XmageProvider.PROTOCOL_VERSION.equals(protocolVersion)) {
            return error(
                    requestId,
                    "protocol_version_mismatch",
                    "Expected protocol " + XmageProvider.PROTOCOL_VERSION + " but received " + protocolVersion,
                    false
            );
        }

        String messageType = stringValue(request, "message_type");
        if (messageType.isBlank()) {
            messageType = stringValue(request, "method");
        }

        return switch (messageType) {
            case "start_engine" -> success(requestId, startedPayload(), false);
            case "get_provider_version" -> success(requestId, XmageProvider.providerVersion(), false);
            case "get_capabilities" -> success(requestId, capabilitiesPayload(), false);
            case "import_deck" -> importDeck(requestId, request);
            case "create_full_game" -> createFullGame(requestId, request);
            case "start_full_game" -> startFullGame(requestId);
            case "get_full_game_decision" -> getDecision(requestId);
            case "get_full_game_observation" -> getObservation(requestId, request);
            case "submit_full_game_decision" -> submitDecision(requestId, request);
            case "get_full_game_result" -> getResult(requestId);
            case "shutdown_engine" -> success(requestId, shutdownPayload(), true);
            default -> error(
                    requestId,
                    "unsupported_message",
                    "Full-game XMage lane does not support message type: " + messageType,
                    false
            );
        };
    }

    private Result importDeck(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(request, "IMPORT_DECK requires payload");
            if (!payload.has("deck") || !payload.get("deck").isJsonObject()) {
                return error(requestId, "invalid_deck_payload", "IMPORT_DECK requires payload.deck", false);
            }
            JsonObject deck = payload.getAsJsonObject("deck");
            String deckId = requiredText(deck, "deck_id");
            String deckHash = requiredText(deck, "deck_hash");
            List<String> mainboard = requiredStringArray(deck, "mainboard");
            List<String> commanders = requiredStringArray(deck, "commander_names");
            List<String> sideboard = optionalStringArray(deck, "sideboard");
            if (!sideboard.isEmpty()) {
                return error(
                        requestId,
                        "unsupported_deck_sideboard",
                        "Commander full-game lane does not support nonempty sideboards",
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
            handle.addProperty("accepted_cards", imported.mainboardCount() + imported.commanderCount());
            JsonArray commanderNames = new JsonArray();
            commanders.forEach(commanderNames::add);
            handle.add("commander_names", commanderNames);
            handle.add("rejected_cards", new JsonArray());
            handle.add("warnings", new JsonArray());

            JsonObject responsePayload = new JsonObject();
            responsePayload.add("deck_handle", handle);
            return success(requestId, responsePayload, false);
        } catch (XmageDeckImporter.ImportException exc) {
            return error(requestId, "deck_import_failed", exc.getMessage(), false);
        } catch (Exception exc) {
            return error(requestId, "invalid_deck_payload", exceptionMessage(exc), false);
        }
    }

    private Result createFullGame(String requestId, JsonObject request) {
        try {
            if (session != null) {
                return error(
                        requestId,
                        "full_game_process_already_used",
                        "Full-game lane permits exactly one game per JVM process",
                        false
                );
            }
            JsonObject payload = requireObjectPayload(request, "CREATE_FULL_GAME requires an object payload");
            String gameId = requiredText(payload, "game_id");
            List<String> deckHandles = requiredStringArray(payload, "deck_handles");
            if (!XmageFullGameSession.supportsPlayerCount(deckHandles.size())) {
                return error(
                        requestId,
                        "invalid_player_count",
                        "Full-game conformance requires 2 through 5 players; observed " + deckHandles.size(),
                        false
                );
            }
            if (!payload.has("seed") || payload.get("seed").isJsonNull()) {
                return error(
                        requestId,
                        "seed_required",
                        "Full-game conformance requires an explicit scenario seed",
                        false
                );
            }
            long seed = requiredLong(payload, "seed");
            int startingPlayerSeat = optionalInt(payload, "starting_player_seat", 0);
            int startingLife = optionalInt(payload, "starting_life", 40);

            session = new XmageFullGameSession(
                    gameId,
                    new ArrayList<>(deckHandles),
                    startingPlayerSeat,
                    startingLife,
                    seed,
                    deckImporter
            );

            JsonObject responsePayload = new JsonObject();
            responsePayload.addProperty("game_id", gameId);
            responsePayload.addProperty("player_count", session.playerCount());
            responsePayload.addProperty("starting_player_seat", startingPlayerSeat);
            responsePayload.addProperty("starting_life", startingLife);
            responsePayload.addProperty("seed", seed);
            responsePayload.addProperty("seed_controlled", true);
            responsePayload.addProperty("seed_scope", "single_isolated_jvm_process");
            responsePayload.addProperty("decision_protocol_version", XmageFullGameDecisionController.PROTOCOL_VERSION);
            responsePayload.addProperty("evidence_class", XmageFullGameSession.EVIDENCE_CLASS);
            responsePayload.addProperty("holdout_consumed", false);
            responsePayload.addProperty("official_campaign_eligible", false);
            return success(requestId, responsePayload, false);
        } catch (Exception exc) {
            return error(requestId, "full_game_creation_failed", exceptionMessage(exc), false);
        }
    }

    private Result startFullGame(String requestId) {
        try {
            return success(requestId, requireSession().start(), false);
        } catch (Exception exc) {
            return error(requestId, "full_game_start_failed", exceptionMessage(exc), false);
        }
    }

    private Result getDecision(String requestId) {
        try {
            return success(requestId, requireSession().pendingDecisionPayload(), false);
        } catch (Exception exc) {
            return error(requestId, "full_game_decision_failed", exceptionMessage(exc), false);
        }
    }

    private Result getObservation(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "GET_FULL_GAME_OBSERVATION requires an object payload"
            );
            int viewerSeat = requiredInt(payload, "viewer_seat");
            int decisionSubjectSeat = optionalInt(payload, "decision_subject_seat", viewerSeat);
            return success(
                    requestId,
                    requireSession().observationPayload(viewerSeat, decisionSubjectSeat),
                    false
            );
        } catch (Exception exc) {
            return error(requestId, "full_game_observation_failed", exceptionMessage(exc), false);
        }
    }

    private Result submitDecision(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "SUBMIT_FULL_GAME_DECISION requires an object payload"
            );
            if (!payload.has("response") || !payload.get("response").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_full_game_decision",
                        "SUBMIT_FULL_GAME_DECISION requires payload.response",
                        false
                );
            }
            return success(
                    requestId,
                    requireSession().submit(payload.getAsJsonObject("response")),
                    false
            );
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            return error(requestId, "external_pilot_decision_rejected", exc.getMessage(), false);
        } catch (Exception exc) {
            return error(requestId, "invalid_full_game_decision", exceptionMessage(exc), false);
        }
    }

    private Result getResult(String requestId) {
        try {
            return success(requestId, requireSession().resultPayload(), false);
        } catch (Exception exc) {
            return error(requestId, "full_game_result_failed", exceptionMessage(exc), false);
        }
    }

    private XmageFullGameSession requireSession() {
        if (session == null) {
            throw new IllegalStateException("FULL_GAME_NOT_CREATED");
        }
        return session;
    }

    private static JsonObject capabilitiesPayload() {
        JsonObject capabilities = new JsonObject();
        capabilities.addProperty("commander_supported", true);
        capabilities.addProperty("partner_supported", true);
        capabilities.addProperty("multiplayer_supported", true);
        capabilities.addProperty("min_players", XmageFullGameSession.MIN_PLAYER_COUNT);
        capabilities.addProperty("max_players", XmageFullGameSession.MAX_PLAYER_COUNT);
        JsonArray supportedPlayerCounts = new JsonArray();
        for (int count = XmageFullGameSession.MIN_PLAYER_COUNT; count <= XmageFullGameSession.MAX_PLAYER_COUNT; count++) {
            supportedPlayerCounts.add(count);
        }
        capabilities.add("supported_player_counts", supportedPlayerCounts);
        capabilities.addProperty("headless_supported", true);
        capabilities.addProperty("seed_supported", true);
        capabilities.addProperty("deck_import_supported", true);
        capabilities.addProperty("actor_scoped_observation_supported", true);

        // Generic B4-style legal-action flags deliberately remain false. This
        // lane uses blocking typed decision callbacks, not a globally complete
        // free-standing legal-actions API.
        capabilities.addProperty("legal_actions_supported", false);
        capabilities.addProperty("action_submission_supported", false);
        capabilities.addProperty("event_log_supported", false);
        capabilities.addProperty("replay_supported", false);
        capabilities.addProperty("stack_visible", true);
        capabilities.addProperty("priority_visible", true);
        capabilities.addProperty("commander_damage_visible", false);
        capabilities.addProperty("commander_tax_visible", false);
        capabilities.addProperty("starting_state_injection_supported", false);
        capabilities.addProperty("scenario_injection_supported", false);
        capabilities.addProperty("healthcheck_supported", true);
        capabilities.addProperty("target_selection_supported", true);
        capabilities.addProperty("mode_selection_supported", true);
        capabilities.addProperty("trigger_order_supported", true);
        capabilities.addProperty("mulligan_supported", true);
        capabilities.addProperty("concede_supported", false);
        capabilities.addProperty("game_shutdown_supported", false);
        capabilities.addProperty("engine_shutdown_supported", true);
        capabilities.addProperty("runtime_kind", "external_rules_engine");

        JsonArray notes = new JsonArray();
        notes.add("Dedicated full-game lane; existing B3/B4 JsonlBridge capability truth is unchanged");
        notes.add("Operational technical scope is 2 through 5 Commander players");
        notes.add("XMage is rules authority; Commander Lab external pilots are discretionary decision authority");
        notes.add("No Tactical, Structural, XMage-AI, random or default discretionary fallback is permitted");
        notes.add("Rules randomness remains XMage-owned and uses an explicit per-process seed");
        notes.add("One isolated JVM process is required per game because XMage RandomUtil is process-global");
        notes.add("Full-game runs are technical conformance only and may not consume gameplay evidence or holdouts");
        notes.add("Bit-exact replay remains unclaimed until a duplicate-run gate proves it");
        capabilities.add("notes", notes);

        JsonObject lane = new JsonObject();
        lane.addProperty("lane", "xmage_full_game_external_pilots");
        lane.addProperty("decision_protocol_version", XmageFullGameDecisionController.PROTOCOL_VERSION);
        lane.addProperty("min_players", XmageFullGameSession.MIN_PLAYER_COUNT);
        lane.addProperty("max_players", XmageFullGameSession.MAX_PLAYER_COUNT);
        lane.add("supported_player_counts", supportedPlayerCounts.deepCopy());
        lane.addProperty("evidence_class", XmageFullGameSession.EVIDENCE_CLASS);
        lane.addProperty("generic_capability_promotion", false);
        lane.addProperty("one_game_per_process", true);
        lane.addProperty("bit_exact_replay_validated", false);
        lane.addProperty("actor_scoped_observation_supported", true);

        JsonObject result = new JsonObject();
        result.add("capabilities", capabilities);
        result.add("full_game_lane", lane);
        return result;
    }

    private static JsonObject startedPayload() {
        XmageProvider.verifyRuntimeLoaded();
        JsonObject payload = new JsonObject();
        payload.addProperty("engine", XmageProvider.ENGINE);
        payload.addProperty("started", true);
        payload.addProperty("lane", "xmage_full_game_external_pilots");
        payload.addProperty("one_game_per_process", true);
        payload.addProperty("min_players", XmageFullGameSession.MIN_PLAYER_COUNT);
        payload.addProperty("max_players", XmageFullGameSession.MAX_PLAYER_COUNT);
        payload.addProperty("evidence_class", XmageFullGameSession.EVIDENCE_CLASS);
        return payload;
    }

    private static JsonObject shutdownPayload() {
        JsonObject payload = new JsonObject();
        payload.addProperty("engine", XmageProvider.ENGINE);
        payload.addProperty("shutdown", true);
        payload.addProperty("lane", "xmage_full_game_external_pilots");
        return payload;
    }

    private static JsonObject requireObjectPayload(JsonObject request, String message) {
        if (!request.has("payload") || !request.get("payload").isJsonObject()) {
            throw new IllegalArgumentException(message);
        }
        return request.getAsJsonObject("payload");
    }

    private static String requiredText(JsonObject object, String property) {
        String value = stringValue(object, property).trim();
        if (value.isBlank()) {
            throw new IllegalArgumentException(property + " must be nonblank");
        }
        return value;
    }

    private static List<String> requiredStringArray(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            throw new IllegalArgumentException("Missing required array: " + property);
        }
        return stringArray(object, property);
    }

    private static List<String> optionalStringArray(JsonObject object, String property) {
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
        List<String> result = new ArrayList<>(array.size());
        for (int index = 0; index < array.size(); index++) {
            if (!array.get(index).isJsonPrimitive() || !array.get(index).getAsJsonPrimitive().isString()) {
                throw new IllegalArgumentException(property + "[" + index + "] must be a string");
            }
            String value = array.get(index).getAsString().trim();
            if (value.isBlank()) {
                throw new IllegalArgumentException(property + "[" + index + "] must be nonblank");
            }
            result.add(value);
        }
        return List.copyOf(result);
    }

    private static long requiredLong(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            throw new IllegalArgumentException(property + " is required");
        }
        if (!object.get(property).isJsonPrimitive() || !object.get(property).getAsJsonPrimitive().isNumber()) {
            throw new IllegalArgumentException(property + " must be an integer");
        }
        String raw = object.get(property).getAsString();
        if (!raw.matches("-?\\d+")) {
            throw new IllegalArgumentException(property + " must be an integer");
        }
        return Long.parseLong(raw);
    }

    private static int requiredInt(JsonObject object, String property) {
        long value = requiredLong(object, property);
        if (value < Integer.MIN_VALUE || value > Integer.MAX_VALUE) {
            throw new IllegalArgumentException(property + " outside integer range");
        }
        return (int) value;
    }

    private static int optionalInt(JsonObject object, String property, int defaultValue) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return defaultValue;
        }
        return requiredInt(object, property);
    }

    private static Result success(String requestId, JsonObject payload, boolean shutdown) {
        JsonObject response = baseResponse(requestId);
        response.addProperty("success", true);
        response.addProperty("status", "ok");
        response.add("payload", payload);
        response.addProperty("engine_event_offset", 0);
        return new Result(response.toString(), shutdown);
    }

    private static Result error(String requestId, String code, String message, boolean retryable) {
        JsonObject response = baseResponse(requestId);
        response.addProperty("success", false);
        response.addProperty("status", "error");
        JsonObject error = new JsonObject();
        error.addProperty("code", code);
        error.addProperty("message", message == null ? code : message);
        error.addProperty("retryable", retryable);
        JsonArray errors = new JsonArray();
        errors.add(error);
        response.add("errors", errors);
        response.addProperty("engine_event_offset", 0);
        return new Result(response.toString(), false);
    }

    private static JsonObject baseResponse(String requestId) {
        JsonObject response = new JsonObject();
        response.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
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
        String message = exc.getMessage();
        return exc.getClass().getSimpleName() + ": " + (message == null ? "<no message>" : message);
    }
}

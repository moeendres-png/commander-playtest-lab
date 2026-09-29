package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.repository.CardInfo;
import mage.cards.repository.CardRepository;
import mage.players.Player;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Dedicated Protocol-2 surface for one isolated <em>mid-game</em> Commander
 * game whose starting state is materialised by the engine-native
 * {@link XmageNativeStateRestoration} seam.
 *
 * <p><b>Why this lane exists.</b> {@code XmageNativeStateRestoration} already
 * translates an explicit requested starting state into engine-native state
 * through public engine APIs only, revalidates it with engine-authoritative
 * state-based actions plus layers, and proves it with a strict native readback
 * compared field-by-field. It is already proven at runtime by the native PB-03
 * tier suites. Before this lane it was, however, constructed from exactly one
 * production site — always with a {@code null} restoration — so every
 * production-reachable lane reported a single coarse
 * {@code starting_state_injection_supported=false} and the per-dimension
 * manifest it already publishes had no consumer at all. This lane makes the
 * existing capability production-reachable without adding one line of new Rules
 * semantics: it composes the seam that already exists and exposes it over the
 * same Protocol-2 transport, the same external decision controller and the
 * same principal-scoped redactor used by the full-game lane.</p>
 *
 * <p><b>Rules authority is unchanged.</b> Every legal action, cost, target,
 * mode, division, combat step, trigger, replacement and state-based action
 * after arrival is produced by the running XMage engine. This class only
 * materialises a starting position, drives the engine-owned arrival transport,
 * and hands every discretionary decision to the external pilot through the
 * blocking {@link XmageFullGameDecisionController}. There is no default, no
 * first-option fallback and no fabricated option anywhere on this lane.</p>
 *
 * <p><b>Arrival is a transport, never a fixture decision.</b> The requested
 * temporal point is reached by the running engine through ordinary external
 * decisions submitted over this same protocol. Nothing here answers a decision
 * on the pilot's behalf. {@link #completeMidgameArrival(String, JsonObject)}
 * performs only the engine-side post-arrival steps (commander cast-count
 * restore, engine revalidation, native readback and field-level compare) and
 * returns the engine's own verdict; a construction mismatch fails the request
 * closed and is never converted into progress.</p>
 *
 * <p>Scope: 2..6-player Commander Free-for-All, one game per JVM process, which
 * matches the existing full-game lane's isolation contract. Scaffolding decks
 * are harness construction vehicles and are never registered as a game deck.</p>
 */
final class XmageMidgameJsonlBridge {

    private final XmageDeckImporter deckImporter = new XmageDeckImporter();

    private XmageFullGameSession session;
    private XmageNativeStateRestoration restoration;
    private String planId;

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
        if (!XmageProvider.PROTOCOL_VERSION.equals(stringValue(request, "protocol_version"))) {
            return error(
                    requestId,
                    "protocol_version_mismatch",
                    "Expected protocol " + XmageProvider.PROTOCOL_VERSION,
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
            case "create_midgame_game" -> createMidgameGame(requestId, request);
            case "start_midgame_game" -> startMidgameGame(requestId);
            case "get_midgame_decision" -> getDecision(requestId);
            case "submit_midgame_decision" -> submitDecision(requestId, request);
            case "complete_midgame_arrival" -> completeMidgameArrival(requestId, request);
            case "get_midgame_state" -> getState(requestId, request);
            case "get_legal_actions" -> getLegalActions(requestId);
            case "submit_action" -> submitAction(requestId, request);
            case "get_midgame_result" -> getResult(requestId);
            case "get_concede_offer" -> getConcedeOffer(requestId, request);
            case "submit_concede" -> submitConcede(requestId, request);
            case "shutdown_engine" -> success(requestId, shutdownPayload(), true);
            default -> error(
                    requestId,
                    "unsupported_message",
                    "Mid-game XMage lane does not support message type: " + messageType,
                    false
            );
        };
    }

    /**
     * Builds the restoration's materialisation vehicle from the plan's own
     * requested objects. The vehicle exists only so the engine seam can place
     * real cards; it is never a fixture content source and never a game deck.
     */
    private static XmageNativeStateRestoration restorationFor(
            XmageNativeStateRestoration.Plan plan) {
        List<String> identities = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedObject object : plan.objects()) {
            identities.add(object.cardIdentity());
        }
        for (XmageNativeStateRestoration.RequestedCommander commander : plan.commanders()) {
            identities.add(commander.cardIdentity());
        }
        return new XmageNativeStateRestoration(
                plan,
                XmageNativeStateRestoration.materializeCards(identities)
        );
    }

    /**
     * Commander colours are read from the engine's own card registry rather
     * than a Lab-side table, so the scaffolding filler stays a construction
     * vehicle that tracks the real card's mana colours.
     */
    private static Set<String> engineCommanderColors(String commanderName) {
        CardInfo cardInfo = CardRepository.instance.findCard(commanderName, true);
        if (cardInfo == null) {
            throw new XmageNativeStateRestoration.RestorationException(
                    "UNKNOWN_COMMANDER_CARD", commanderName);
        }
        var color = cardInfo.getColor();
        Set<String> colors = new HashSet<>();
        if (color.isWhite()) {
            colors.add("W");
        }
        if (color.isBlue()) {
            colors.add("U");
        }
        if (color.isBlack()) {
            colors.add("B");
        }
        if (color.isRed()) {
            colors.add("R");
        }
        if (color.isGreen()) {
            colors.add("G");
        }
        if (colors.isEmpty()) {
            throw new XmageNativeStateRestoration.RestorationException(
                    "UNSUPPORTED_COMMANDER_COLOR", commanderName);
        }
        return colors;
    }

    private List<String> importScaffolding(
            XmageNativeStateRestoration.Plan plan, String deckTag) {
        // Commander colours come from the engine's own card registry, so the
        // repository must be in the same ready state every other resolution
        // path observes.
        XmageDeckImporter.ensureRepositoryReady();
        Map<String, List<String>> commandersByOwner = new LinkedHashMap<>();
        for (XmageNativeStateRestoration.RequestedCommander commander : plan.commanders()) {
            commandersByOwner
                    .computeIfAbsent(commander.owner(), owner -> new ArrayList<>())
                    .add(commander.cardIdentity());
        }
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : plan.players()) {
            List<String> commanders = commandersByOwner.getOrDefault(player.playerId(), List.of());
            if (commanders.isEmpty() || commanders.size() > 2) {
                throw new XmageNativeStateRestoration.RestorationException(
                        "UNSUPPORTED_COMMANDER_RELATION",
                        player.playerId() + " commanders=" + commanders.size());
            }
            Set<String> colors = new HashSet<>();
            for (String commander : commanders) {
                colors.addAll(engineCommanderColors(commander));
            }
            List<String> mainboard = XmageNativeStateRestoration.scaffoldingFiller(
                    100 - commanders.size(), colors);
            handles.add(deckImporter.importCommanderDeck(
                    deckTag + "-" + player.playerId(),
                    deckTag + "-hash",
                    mainboard,
                    commanders).deckHandle());
        }
        return handles;
    }

    private Result importDeck(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(request, "IMPORT_DECK requires payload");
            if (!payload.has("deck") || !payload.get("deck").isJsonObject()) {
                return error(requestId, "invalid_deck_payload", "IMPORT_DECK requires payload.deck", false);
            }
            JsonObject deck = payload.getAsJsonObject("deck");
            List<String> sideboard = optionalStringArray(deck, "sideboard");
            if (!sideboard.isEmpty()) {
                return error(
                        requestId,
                        "unsupported_deck_sideboard",
                        "Mid-game lane does not support nonempty sideboard",
                        false
                );
            }
            XmageDeckImporter.ImportResult imported = deckImporter.importCommanderDeck(
                    requiredText(deck, "deck_id"),
                    requiredText(deck, "deck_hash"),
                    requiredStringArray(deck, "mainboard"),
                    requiredStringArray(deck, "commander_names")
            );
            JsonObject handle = new JsonObject();
            handle.addProperty("backend", XmageProvider.ENGINE);
            handle.addProperty("handle_id", imported.deckHandle());
            handle.addProperty("deck_id", imported.deckId());
            handle.addProperty("deck_hash", imported.deckHash());
            handle.addProperty("accepted_cards",
                    imported.mainboardCount() + imported.commanderCount());
            handle.addProperty("commander_count", imported.commanderCount());
            JsonObject result = new JsonObject();
            result.add("deck_handle", handle);
            return success(requestId, result, false);
        } catch (Exception exc) {
            return error(requestId, "deck_import_failed", exceptionMessage(exc), false);
        }
    }

    private Result createMidgameGame(String requestId, JsonObject request) {
        try {
            if (session != null) {
                return error(
                        requestId,
                        "midgame_process_already_used",
                        "Mid-game lane permits exactly one game per JVM process",
                        false
                );
            }
            JsonObject payload = requireObjectPayload(
                    request, "CREATE_MIDGAME_GAME requires an object payload");
            String gameId = requiredText(payload, "game_id");
            if (!payload.has("requested_starting_state")
                    || !payload.get("requested_starting_state").isJsonObject()) {
                return error(
                        requestId,
                        "missing_requested_starting_state",
                        "CREATE_MIDGAME_GAME requires payload.requested_starting_state; "
                                + "the mid-game lane never infers a starting position",
                        false
                );
            }
            if (!payload.has("seed") || payload.get("seed").isJsonNull()) {
                return error(
                        requestId,
                        "seed_required",
                        "Mid-game lane requires an explicit scenario seed",
                        false
                );
            }
            long seed = requiredLong(payload, "seed");
            String planTag = stringValue(payload, "plan_id").isBlank()
                    ? gameId
                    : stringValue(payload, "plan_id");
            int startingPlayerSeat = optionalInt(payload, "starting_player_seat", 0);
            int startingLife = optionalInt(payload, "starting_life", 40);

            XmageNativeStateRestoration.Plan plan =
                    XmageNativeStateRestoration.planFromFrozenRecord(
                            payload.getAsJsonObject("requested_starting_state"), planTag, seed);
            // Fail closed before any game mutation: the plan validator rejects
            // every unsupported dimension with a coded reason.
            XmageNativeStateRestoration.validatePlan(plan);

            List<String> handles = importScaffolding(plan, planTag);
            this.restoration = restorationFor(plan);
            this.planId = planTag;
            this.session = new XmageFullGameSession(
                    gameId,
                    handles,
                    startingPlayerSeat,
                    startingLife,
                    seed,
                    deckImporter,
                    restoration
            );

            JsonObject response = new JsonObject();
            response.addProperty("game_id", gameId);
            response.addProperty("plan_id", planTag);
            response.addProperty("player_count", session.playerCount());
            response.addProperty("starting_player_seat", startingPlayerSeat);
            response.addProperty("starting_life", startingLife);
            response.addProperty("seed", seed);
            response.addProperty("seed_controlled", true);
            response.add("rules_seed_binding", session.rulesSeedBindingPayload());
            response.addProperty("seed_scope", "single_isolated_jvm_process");
            response.addProperty("decision_protocol_version",
                    XmageFullGameDecisionController.PROTOCOL_VERSION);
            response.addProperty("evidence_class", XmageFullGameSession.EVIDENCE_CLASS);
            response.addProperty("scaffolding_decks_are_game_decks", false);
            response.add("starting_state_dimensions_manifest",
                    XmageNativeStateRestoration.dimensionsPayload());
            return success(requestId, response, false);
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            return error(
                    requestId,
                    "midgame_starting_state_rejected",
                    exceptionMessage(exc),
                    false
            );
        } catch (Exception exc) {
            return error(requestId, "midgame_creation_failed", exceptionMessage(exc), false);
        }
    }

    private Result startMidgameGame(String requestId) {
        try {
            requireSession();
            return success(requestId, session.start(), false);
        } catch (Exception exc) {
            return error(requestId, "midgame_start_failed", exceptionMessage(exc), false);
        }
    }

    private Result getDecision(String requestId) {
        try {
            return success(requestId, requireSession().pendingDecisionPayload(), false);
        } catch (Exception exc) {
            return error(requestId, "midgame_decision_failed", exceptionMessage(exc), false);
        }
    }

    private Result submitDecision(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request, "SUBMIT_MIDGAME_DECISION requires an object payload");
            if (!payload.has("response") || !payload.get("response").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_midgame_decision",
                        "SUBMIT_MIDGAME_DECISION requires payload.response",
                        false
                );
            }
            return success(
                    requestId,
                    requireSession().submit(payload.getAsJsonObject("response")),
                    false
            );
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            return error(
                    requestId,
                    "external_pilot_decision_rejected",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(requestId, "invalid_midgame_decision", exceptionMessage(exc), false);
        }
    }

    /**
     * Engine-side post-arrival completion plus the engine's own construction
     * verdict. This performs no player decision at all.
     */
    private Result completeMidgameArrival(String requestId, JsonObject request) {
        try {
            requireSession();
            if (restoration == null) {
                return error(
                        requestId,
                        "no_starting_state_plan",
                        "This lane only completes an explicitly requested starting state",
                        false
                );
            }
            Map<String, Player> seats = requireSession().restorationSeats();
            restoration.restoreCommanderCasts(requireSession().restorationGame(), seats);
            XmageNativeStateRestoration.revalidate(requireSession().restorationGame());
            JsonObject observed =
                    XmageNativeStateRestoration.readback(requireSession().restorationGame(), seats);
            XmageNativeStateRestoration.CompareVerdict verdict = restoration.compare(observed, seats);

            JsonObject response = new JsonObject();
            response.addProperty("plan_id", planId);
            response.addProperty("construction_match", verdict.match());
            response.addProperty("requested_state_digest", verdict.requestedDigest());
            response.addProperty("constructed_state_digest", verdict.constructedDigest());
            JsonArray mismatches = new JsonArray();
            verdict.mismatches().forEach(mismatches::add);
            response.add("mismatches", mismatches);
            response.add("readback", observed);
            response.add("pending_decision", requireSession().pendingDecisionPayload());
            return success(requestId, response, false);
        } catch (Exception exc) {
            return error(requestId, "midgame_arrival_failed", exceptionMessage(exc), false);
        }
    }

    private Result getState(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(request, "GET_MIDGAME_STATE requires payload");
            String principalId = requiredText(payload, "actor_id");
            UUID actorId = resolvePrincipal(principalId);
            JsonObject state = new JsonObject();
            state.addProperty("actor_id", principalId);
            state.add("zone_counts", requireSession().zoneCountsPayload(actorId));
            state.addProperty("observation_scope", "principal_scoped");
            state.add("seed_binding", requireSession().rulesSeedBindingPayload());
            return success(requestId, state, false);
        } catch (Exception exc) {
            return error(requestId, "midgame_state_failed", exceptionMessage(exc), false);
        }
    }

    /**
     * Seat order is public information, so resolving a real principal id to
     * its engine uuid uses the session's own seat map rather than recovering
     * an identity from an observation.
     */
    private UUID resolvePrincipal(String principalId) {
        XmageFullGameSession current = requireSession();
        for (int seat = 0; seat < current.playerCount(); seat++) {
            if (principalId.equals(current.principalIdAtSeat(seat))) {
                return UUID.fromString(principalId);
            }
        }
        throw new IllegalArgumentException("unknown principal: " + principalId);
    }

    private Result getLegalActions(String requestId) {
        try {
            return success(requestId, requireSession().legalActionsPayload(), false);
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            return error(requestId, "legal_actions_unavailable", exc.getMessage(), false);
        } catch (Exception exc) {
            return error(requestId, "legal_actions_failed", exceptionMessage(exc), false);
        }
    }

    private Result submitAction(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(request, "SUBMIT_ACTION requires payload");
            if (!payload.has("proposal") || !payload.get("proposal").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_action_proposal",
                        "SUBMIT_ACTION requires payload.proposal",
                        false
                );
            }
            return success(
                    requestId,
                    requireSession().submitAction(payload.getAsJsonObject("proposal")),
                    false
            );
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            return error(requestId, "action_proposal_rejected", exc.getMessage(), false);
        } catch (Exception exc) {
            return error(requestId, "action_submission_failed", exceptionMessage(exc), false);
        }
    }

    private Result getResult(String requestId) {
        try {
            return success(requestId, requireSession().resultPayload(), false);
        } catch (Exception exc) {
            return error(requestId, "midgame_result_failed", exceptionMessage(exc), false);
        }
    }

    private Result getConcedeOffer(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(request, "GET_CONCEDE_OFFER requires payload");
            return success(
                    requestId,
                    requireSession().concedeOfferPayload(requiredText(payload, "actor_id")),
                    false
            );
        } catch (Exception exc) {
            return error(requestId, "concede_offer_failed", exceptionMessage(exc), false);
        }
    }

    private Result submitConcede(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(request, "SUBMIT_CONCEDE requires payload");
            return success(
                    requestId,
                    requireSession().submitConcede(payload.getAsJsonObject("payload")),
                    false
            );
        } catch (Exception exc) {
            return error(requestId, "concede_submission_failed", exceptionMessage(exc), false);
        }
    }

    private XmageFullGameSession requireSession() {
        if (session == null) {
            throw new IllegalStateException("MIDGAME_NOT_CREATED");
        }
        return session;
    }

    private static JsonObject capabilitiesPayload() {
        JsonObject capabilities = new JsonObject();
        capabilities.addProperty("commander_supported", true);
        capabilities.addProperty("partner_supported", true);
        capabilities.addProperty("multiplayer_supported", true);
        capabilities.addProperty("min_players", XmageFullGameSession.MIN_PLAYERS);
        capabilities.addProperty("max_players", XmageFullGameSession.MAX_PLAYERS);
        capabilities.addProperty("headless_supported", true);
        capabilities.addProperty("seed_supported", true);
        capabilities.addProperty("deck_import_supported", true);
        capabilities.addProperty("legal_actions_supported", false);
        capabilities.addProperty("action_submission_supported", false);
        capabilities.addProperty("event_log_supported", false);
        capabilities.addProperty("replay_supported", false);
        capabilities.addProperty("stack_visible", true);
        capabilities.addProperty("priority_visible", true);
        capabilities.addProperty("target_selection_supported", true);
        capabilities.addProperty("mode_selection_supported", true);
        capabilities.addProperty("trigger_order_supported", true);
        capabilities.addProperty("mulligan_supported", true);
        capabilities.addProperty("concede_supported", true);
        capabilities.addProperty("engine_shutdown_supported", true);
        capabilities.addProperty("runtime_kind", "external_rules_engine");
        // The global coarse flag stays false by design: it describes a
        // globally complete injection of arbitrary states, which this lane
        // does not claim. The per-dimension manifest is the truthful
        // capability statement and is what a consumer must classify against.
        capabilities.addProperty("starting_state_injection_supported", false);
        capabilities.addProperty("starting_state_dimensions_supported", true);
        capabilities.add(
                "starting_state_dimensions",
                XmageNativeStateRestoration.dimensionsPayload()
        );

        JsonArray notes = new JsonArray();
        notes.add("Explicit requested starting state is materialised by the engine-native "
                + "XmageNativeStateRestoration seam; no new Rules semantics are introduced");
        notes.add("Every post-arrival action, cost, target, mode, division, trigger, replacement "
                + "and state-based action is produced by the running XMage engine");
        notes.add("Every discretionary decision, including the arrival transport, is submitted by "
                + "the external pilot over this protocol; there is no default or fallback here");
        notes.add("Construction credit requires an exact engine-native readback match with "
                + "field-level digests; a mismatch fails the request closed");
        notes.add("Rules randomness remains XMage-owned through the explicitly bound per-game seed");
        notes.add("Scaffolding decks are harness construction vehicles and are never game decks");
        capabilities.add("notes", notes);

        JsonObject lane = new JsonObject();
        lane.addProperty("lane", "xmage_midgame_native_starting_state");
        lane.addProperty("decision_protocol_version",
                XmageFullGameDecisionController.PROTOCOL_VERSION);
        lane.addProperty("min_players", XmageFullGameSession.MIN_PLAYERS);
        lane.addProperty("max_players", XmageFullGameSession.MAX_PLAYERS);
        lane.addProperty("evidence_class", XmageFullGameSession.EVIDENCE_CLASS);
        lane.addProperty("one_game_per_process", true);
        lane.addProperty("global_starting_state_injection_claimed", false);
        lane.addProperty("per_dimension_starting_state_claimed", true);
        capabilities.addProperty("runtime_kind", "external_rules_engine");
        JsonObject result = new JsonObject();
        result.add("capabilities", capabilities);
        result.add("midgame_lane", lane);
        return result;
    }

    private static JsonObject startedPayload() {
        XmageProvider.verifyRuntimeLoaded();
        JsonObject result = new JsonObject();
        result.addProperty("engine", XmageProvider.ENGINE);
        result.addProperty("engine_version", XmageProvider.ENGINE_VERSION);
        result.addProperty("engine_commit", XmageProvider.ENGINE_COMMIT);
        result.addProperty("protocol_version", XmageProvider.PROTOCOL_VERSION);
        result.addProperty("lane", "xmage_midgame_native_starting_state");
        return result;
    }

    private static JsonObject shutdownPayload() {
        JsonObject result = new JsonObject();
        result.addProperty("engine", XmageProvider.ENGINE);
        result.addProperty("shutdown", true);
        return result;
    }

    private static JsonObject requireObjectPayload(JsonObject request, String message) {
        if (!request.has("payload") || !request.get("payload").isJsonObject()) {
            throw new IllegalArgumentException(message);
        }
        return request.getAsJsonObject("payload");
    }

    private static String requiredText(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            throw new IllegalArgumentException("missing required field: " + property);
        }
        String value = object.get(property).getAsString();
        if (value.isBlank()) {
            throw new IllegalArgumentException("blank required field: " + property);
        }
        return value;
    }

    private static List<String> requiredStringArray(JsonObject object, String property) {
        if (!object.has(property) || !object.get(property).isJsonArray()) {
            throw new IllegalArgumentException("missing required array: " + property);
        }
        List<String> values = new ArrayList<>();
        for (JsonElement element : object.getAsJsonArray(property)) {
            values.add(element.getAsString());
        }
        if (values.isEmpty()) {
            throw new IllegalArgumentException("empty required array: " + property);
        }
        return values;
    }

    private static List<String> optionalStringArray(JsonObject object, String property) {
        if (!object.has(property) || !object.get(property).isJsonArray()) {
            return List.of();
        }
        List<String> values = new ArrayList<>();
        for (JsonElement element : object.getAsJsonArray(property)) {
            values.add(element.getAsString());
        }
        return values;
    }

    private static long requiredLong(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            throw new IllegalArgumentException("missing required number: " + property);
        }
        return object.get(property).getAsLong();
    }

    private static int optionalInt(JsonObject object, String property, int defaultValue) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return defaultValue;
        }
        return object.get(property).getAsInt();
    }

    private static Result success(String requestId, JsonObject payload, boolean shutdown) {
        JsonObject response = baseResponse(requestId);
        response.addProperty("success", true);
        response.addProperty("status", "ok");
        response.add("payload", payload);
        response.addProperty("engine_event_offset", 0);
        return new Result(response.toString(), shutdown);
    }

    private static Result error(
            String requestId, String code, String message, boolean retryable) {
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
        return exc.getClass().getSimpleName() + ": "
                + (message == null ? "<no message>" : message);
    }
}

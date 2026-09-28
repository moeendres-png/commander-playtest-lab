package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.util.ArrayList;
import java.util.List;

/**
 * Dedicated JSONL surface for one isolated full Commander game.
 *
 * <p>This class is intentionally separate from {@link JsonlBridge}. The B3/B4
 * compatibility bridge keeps its previously validated capability semantics;
 * full-game conformance must be selected explicitly by launching Main with the
 * {@code full-game} subcommand.</p>
 */
final class XmageFullGameJsonlBridge {

    private final XmageDeckImporter deckImporter = new XmageDeckImporter();
    private XmageFullGameSession session;
    private XmageNativeStateRestoration nativeRestoration;
    private String nativeFixtureId;
    private boolean nativeRestorationFinalized;

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
                    "Expected protocol " + XmageProvider.PROTOCOL_VERSION
                            + " but received " + protocolVersion,
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
            case "get_capabilities" -> success(requestId, capabilitiesPayload(), false);
            case "import_deck" -> importDeck(requestId, request);
            case "create_full_game" -> createFullGame(requestId, request);
            case "create_native_state_game" -> createNativeStateGame(requestId, request);
            case "start_full_game" -> startFullGame(requestId);
            case "get_native_state_restoration_receipt" -> getNativeStateRestorationReceipt(requestId);
            case "get_full_game_decision" -> getDecision(requestId);
            case "submit_full_game_decision" -> submitDecision(requestId, request);
            case "get_full_game_result" -> getResult(requestId);
            case "get_legal_actions" -> getLegalActions(requestId);
            case "submit_action" -> submitAction(requestId, request);
            case "get_concede_offer" -> getConcedeOffer(requestId, request);
            case "submit_concede" -> submitConcede(requestId, request);
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
                return error(
                        requestId,
                        "invalid_deck_payload",
                        "IMPORT_DECK requires payload.deck",
                        false
                );
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
            handle.addProperty(
                    "accepted_cards",
                    imported.mainboardCount() + imported.commanderCount()
            );
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
            return error(
                    requestId,
                    "invalid_deck_payload",
                    exceptionMessage(exc),
                    false
            );
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
            JsonObject payload = requireObjectPayload(
                    request,
                    "CREATE_FULL_GAME requires an object payload"
            );
            String gameId = requiredText(payload, "game_id");
            List<String> deckHandles = requiredStringArray(payload, "deck_handles");
            if (deckHandles.size() < XmageFullGameSession.MIN_PLAYERS
                    || deckHandles.size() > XmageFullGameSession.MAX_PLAYERS) {
                return error(
                        requestId,
                        "invalid_player_count",
                        "Full-game conformance supports "
                                + XmageFullGameSession.MIN_PLAYERS + ".."
                                + XmageFullGameSession.MAX_PLAYERS
                                + " players; observed "
                                + deckHandles.size(),
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
            // WS213: binding proof is available immediately at creation: the
            // explicit seed is bound in the session constructor, before start.
            responsePayload.add("rules_seed_binding", session.rulesSeedBindingPayload());
            responsePayload.addProperty(
                    "seed_scope",
                    "single_isolated_jvm_process"
            );
            responsePayload.addProperty(
                    "decision_protocol_version",
                    XmageFullGameDecisionController.PROTOCOL_VERSION
            );
            responsePayload.addProperty(
                    "evidence_class",
                    XmageFullGameSession.EVIDENCE_CLASS
            );
            responsePayload.addProperty("holdout_consumed", false);
            responsePayload.addProperty("official_campaign_eligible", false);
            return success(requestId, responsePayload, false);
        } catch (Exception exc) {
            return error(
                    requestId,
                    "full_game_creation_failed",
                    exceptionMessage(exc),
                    false
            );
        }
    }


    /**
     * PB-03 bounded native-state qualification entrypoint.
     *
     * <p>This is deliberately not generic starting-state injection. The record is
     * parsed by {@link XmageNativeStateRestoration}, which rejects every
     * unsupported dimension before mutation. The frozen requested-state digest is
     * recomputed and must match before any session exists. No discretionary
     * decision is taken here; after start, an external caller must drive the
     * ordinary full-game decision boundary.</p>
     */
    private Result createNativeStateGame(String requestId, JsonObject request) {
        try {
            if (session != null) {
                return error(
                        requestId,
                        "full_game_process_already_used",
                        "Full-game lane permits exactly one game per JVM process",
                        false
                );
            }
            JsonObject payload = requireObjectPayload(
                    request,
                    "CREATE_NATIVE_STATE_GAME requires an object payload"
            );
            if (!payload.has("record") || !payload.get("record").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_native_state_record",
                        "CREATE_NATIVE_STATE_GAME requires payload.record",
                        false
                );
            }
            JsonObject record = payload.getAsJsonObject("record").deepCopy();
            String gameId = requiredText(payload, "game_id");
            long seed = requiredLong(payload, "seed");
            String fixtureId = requiredText(record, "fixture_id");
            String frozenDigest = requiredText(record, "requested_state_digest");
            String computedDigest = XmageNativeStateRestoration.requestedDigest(record);
            if (!frozenDigest.equals(computedDigest)) {
                return error(
                        requestId,
                        "native_state_digest_mismatch",
                        "requested_state_digest mismatch for " + fixtureId,
                        false
                );
            }

            XmageNativeStateRestoration.Plan plan =
                    XmageNativeStateRestoration.planFromFrozenRecord(
                            record, "protocol2-" + fixtureId, seed);

            List<String> identities = new ArrayList<>();
            for (XmageNativeStateRestoration.RequestedObject object : plan.objects()) {
                identities.add(object.cardIdentity());
            }
            nativeRestoration = new XmageNativeStateRestoration(
                    plan,
                    XmageNativeStateRestoration.materializeCards(identities)
            );

            List<String> handles = new ArrayList<>();
            for (XmageNativeStateRestoration.RequestedPlayer player : plan.players()) {
                List<String> commanders = new ArrayList<>();
                for (XmageNativeStateRestoration.RequestedCommander commander : plan.commanders()) {
                    if (commander.owner().equals(player.playerId())) {
                        commanders.add(commander.cardIdentity());
                    }
                }
                if (commanders.isEmpty() || commanders.size() > 2) {
                    throw new XmageNativeStateRestoration.RestorationException(
                            "INVALID_COMMANDER_SET",
                            player.playerId() + " commanders=" + commanders.size()
                    );
                }
                List<String> mainboard = new ArrayList<>();
                for (int index = commanders.size(); index < 100; index++) {
                    mainboard.add("Wastes");
                }
                XmageDeckImporter.ImportResult imported = deckImporter.importCommanderDeck(
                        gameId + "-" + player.playerId(),
                        gameId + "-" + player.playerId() + "-scaffold",
                        mainboard,
                        commanders
                );
                handles.add(imported.deckHandle());
            }

            int startingPlayerSeat = 0;
            boolean activeSeatFound = false;
            for (XmageNativeStateRestoration.RequestedPlayer player : plan.players()) {
                if (player.playerId().equals(plan.activePlayer())) {
                    startingPlayerSeat = player.seat() - 1;
                    activeSeatFound = true;
                    break;
                }
            }
            if (!activeSeatFound) {
                throw new XmageNativeStateRestoration.RestorationException(
                        "UNKNOWN_ACTIVE_PLAYER", plan.activePlayer());
            }

            session = new XmageFullGameSession(
                    gameId,
                    handles,
                    startingPlayerSeat,
                    40,
                    seed,
                    deckImporter,
                    nativeRestoration
            );
            nativeFixtureId = fixtureId;
            nativeRestorationFinalized = false;

            JsonObject responsePayload = new JsonObject();
            responsePayload.addProperty("game_id", gameId);
            responsePayload.addProperty("fixture_id", fixtureId);
            responsePayload.addProperty("player_count", plan.playerCount());
            responsePayload.addProperty("starting_player_seat", startingPlayerSeat);
            responsePayload.addProperty("seed", seed);
            responsePayload.addProperty("requested_state_digest", frozenDigest);
            responsePayload.addProperty("native_state_transport", true);
            responsePayload.addProperty("generic_starting_state_capability_promoted", false);
            responsePayload.add("state_restoration_dimensions",
                    XmageNativeStateRestoration.dimensionsPayload());
            return success(requestId, responsePayload, false);
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            return error(
                    requestId,
                    "native_state_restoration_rejected",
                    exceptionMessage(exc),
                    false
            );
        } catch (XmageDeckImporter.ImportException exc) {
            return error(
                    requestId,
                    "native_state_scaffolding_rejected",
                    exceptionMessage(exc),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "native_state_creation_failed",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    /**
     * Evidence-only completion receipt for the bounded native restoration.
     *
     * <p>The caller must first reach the requested temporal checkpoint through
     * the ordinary external decision surface. This method never chooses an
     * action. Once parked at the exact target it restores native Commander
     * history, revalidates XMage state, performs strict readback comparison, and
     * returns only non-hidden evidence fields.</p>
     */
    private Result getNativeStateRestorationReceipt(String requestId) {
        try {
            XmageFullGameSession active = requireSession();
            if (nativeRestoration == null || nativeFixtureId == null) {
                return error(
                        requestId,
                        "native_state_session_required",
                        "No bounded native-state qualification session exists",
                        false
                );
            }
            var seats = active.restorationSeats();
            JsonObject observed = XmageNativeStateRestoration.readback(
                    active.restorationGame(), seats);
            XmageNativeStateRestoration.Plan plan = nativeRestoration.plan();
            if (!nativeTemporalTargetReached(observed, plan)) {
                return error(
                        requestId,
                        "native_state_target_not_reached",
                        "External decisions have not reached the requested temporal checkpoint",
                        false
                );
            }
            if (!nativeRestorationFinalized) {
                nativeRestoration.restoreCommanderCasts(active.restorationGame(), seats);
                XmageNativeStateRestoration.revalidate(active.restorationGame());
                nativeRestorationFinalized = true;
            }
            observed = XmageNativeStateRestoration.readback(active.restorationGame(), seats);
            XmageNativeStateRestoration.CompareVerdict verdict =
                    nativeRestoration.compare(observed, seats);

            JsonObject payload = new JsonObject();
            payload.addProperty("fixture_id", nativeFixtureId);
            payload.addProperty("match", verdict.match());
            payload.addProperty("mismatch_count", verdict.mismatches().size());
            payload.addProperty("requested_state_digest", verdict.requestedDigest());
            payload.addProperty("constructed_state_digest", verdict.constructedDigest());
            payload.addProperty("turn_number", observed.get("turn_number").getAsInt());
            payload.addProperty("phase", observed.get("phase").getAsString());
            payload.addProperty("step", observed.get("step").getAsString());
            payload.addProperty("active_player", observed.get("active_player").getAsString());
            payload.addProperty("priority_player", observed.get("priority_player").getAsString());
            payload.add("rules_seed_binding", active.rulesSeedBindingPayload());
            payload.addProperty("native_state_transport", true);
            payload.addProperty("hidden_identity_emitted", false);
            payload.addProperty("generic_starting_state_capability_promoted", false);
            return success(requestId, payload, false);
        } catch (Exception exc) {
            return error(
                    requestId,
                    "native_state_receipt_failed",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private static boolean nativeTemporalTargetReached(
            JsonObject observed,
            XmageNativeStateRestoration.Plan plan
    ) {
        return observed.get("turn_number").getAsInt() == plan.turnNumber()
                && plan.phase().name().equals(observed.get("phase").getAsString())
                && plan.step().name().equals(observed.get("step").getAsString())
                && plan.activePlayer().equals(observed.get("active_player").getAsString())
                && plan.priorityPlayer().equals(observed.get("priority_player").getAsString());
    }

    private Result startFullGame(String requestId) {
        try {
            return success(requestId, requireSession().start(), false);
        } catch (Exception exc) {
            return error(
                    requestId,
                    "full_game_start_failed",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private Result getDecision(String requestId) {
        try {
            return success(requestId, requireSession().pendingDecisionPayload(), false);
        } catch (Exception exc) {
            return error(
                    requestId,
                    "full_game_decision_failed",
                    exceptionMessage(exc),
                    false
            );
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
            return error(
                    requestId,
                    "external_pilot_decision_rejected",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "invalid_full_game_decision",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private Result getResult(String requestId) {
        try {
            return success(requestId, requireSession().resultPayload(), false);
        } catch (Exception exc) {
            return error(
                    requestId,
                    "full_game_result_failed",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    /**
     * WS204 B4-D decision-scoped generic projection. Returns only the exact
     * currently pending native decision as generic actions. Flags remain
     * unpromoted: this is not a globally complete free-standing API.
     */
    private Result getLegalActions(String requestId) {
        try {
            return success(requestId, requireSession().legalActionsPayload(), false);
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            return error(
                    requestId,
                    "external_pilot_decision_rejected",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "full_game_decision_failed",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    /**
     * WS204 B4-D generic submission: validates a generic proposal against the
     * exact current decision and routes only the selected authoritative option
     * to the native controller.
     */
    private Result submitAction(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "SUBMIT_ACTION requires an object payload"
            );
            if (!payload.has("proposal") || !payload.get("proposal").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_full_game_decision",
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
            return error(
                    requestId,
                    "external_pilot_decision_rejected",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "invalid_full_game_decision",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    private XmageFullGameSession requireSession() {
        if (session == null) {
            throw new IllegalStateException("FULL_GAME_NOT_CREATED");
        }
        return session;
    }

    /**
     * WS213 authoritative concession offer. Availability originates in native
     * {@code Game.canConcede(exactPrincipal)}; the bridge never synthesizes
     * availability. Requires payload.player_id (exact native player UUID).
     */
    private Result getConcedeOffer(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "GET_CONCEDE_OFFER requires an object payload"
            );
            String playerId = requiredText(payload, "player_id");
            return success(requestId, requireSession().concedeOfferPayload(playerId), false);
        } catch (XmageFullGameDecisionController.DecisionException exc) {
            return error(
                    requestId,
                    "external_pilot_decision_rejected",
                    exc.getMessage(),
                    false
            );
        } catch (Exception exc) {
            return error(
                    requestId,
                    "full_game_decision_failed",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    /**
     * WS213 authoritative concession submission. Requires
     * payload.proposal.{actor_id, player_id} with actor == subject == the
     * exact native session player UUID. Execution is native
     * {@code Game.concede} for that principal; stale/foreign proposals fail
     * closed without touching game state.
     */
    private Result submitConcede(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(
                    request,
                    "SUBMIT_CONCEDE requires an object payload"
            );
            if (!payload.has("proposal") || !payload.get("proposal").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_full_game_decision",
                        "SUBMIT_CONCEDE requires payload.proposal",
                        false
                );
            }
            return success(
                    requestId,
                    requireSession().submitConcede(payload.getAsJsonObject("proposal")),
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
            return error(
                    requestId,
                    "invalid_full_game_decision",
                    exceptionMessage(exc),
                    false
            );
        }
    }

    /** Package-private so the capability payload can be asserted directly in tests. */
    static JsonObject capabilitiesPayload() {
        JsonObject capabilities = new JsonObject();
        capabilities.addProperty("commander_supported", true);
        capabilities.addProperty("partner_supported", true);
        capabilities.addProperty("multiplayer_supported", true);
        capabilities.addProperty("min_players", XmageFullGameSession.MIN_PLAYERS);
        capabilities.addProperty("max_players", XmageFullGameSession.MAX_PLAYERS);
        capabilities.addProperty("headless_supported", true);
        // WS213: seed_supported is true only because every session binds the
        // explicit orchestration seed to the native per-game Rules RNG
        // (setRulesSeed + requireExplicitSeed before start) and every status
        // payload carries the live binding proof (rules_seed_binding).
        capabilities.addProperty("seed_supported", true);
        capabilities.addProperty("deck_import_supported", true);

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
        // WS213: CONCEDE is an authoritative LegalAction on the WS212 pin.
        // Availability is per-principal native Game.canConcede (no heuristic);
        // offers via get_concede_offer, execution via submit_concede for the
        // exact principal. Every status payload carries the live per-player
        // can_concede vector as proof.
        capabilities.addProperty("concede_supported", true);
        capabilities.addProperty("game_shutdown_supported", false);
        capabilities.addProperty("engine_shutdown_supported", true);
        capabilities.addProperty("runtime_kind", "external_rules_engine");

        JsonArray notes = new JsonArray();
        notes.add("Dedicated full-game lane; existing B3/B4 JsonlBridge capability truth is unchanged");
        notes.add("Operational scope is 2..5-player Commander Free-for-All with one authoritative cardinality contract");
        notes.add("XMage is rules authority; Commander Lab external pilots are discretionary decision authority");
        notes.add("No Tactical, Structural, XMage-AI, random or default discretionary fallback is permitted");
        notes.add("Rules randomness remains XMage-owned and uses the explicit per-game Rules seed bound before start (setRulesSeed + requireExplicitSeed; RandomUtil retired as authority)");
        notes.add("One isolated JVM process is required per game as defense in depth for credited runs");
        notes.add("Full-game runs are technical conformance only and may not consume gameplay evidence or holdouts");
        notes.add("Bit-exact replay remains unclaimed until a duplicate-run gate proves it");
        notes.add("WS204 B4-D decision-scoped get_legal_actions/submit_action project only the exact current pending native decision; global legal_actions/action_submission promotion remains false");
        capabilities.add("notes", notes);

        JsonObject lane = new JsonObject();
        lane.addProperty("lane", "xmage_full_game_external_pilots");
        lane.addProperty("decision_protocol_version", XmageFullGameDecisionController.PROTOCOL_VERSION);
        lane.addProperty("min_players", XmageFullGameSession.MIN_PLAYERS);
        lane.addProperty("max_players", XmageFullGameSession.MAX_PLAYERS);
        lane.addProperty("evidence_class", XmageFullGameSession.EVIDENCE_CLASS);
        lane.addProperty("generic_capability_promotion", false);
        lane.addProperty("one_game_per_process", true);
        lane.addProperty("bit_exact_replay_validated", false);
        // Itemised, live capability truth for bounded native state restoration.
        // The global generic-injection flag deliberately remains false.
        lane.add("state_restoration_dimensions", XmageNativeStateRestoration.dimensionsPayload());

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
        payload.addProperty("min_players", XmageFullGameSession.MIN_PLAYERS);
        payload.addProperty("max_players", XmageFullGameSession.MAX_PLAYERS);
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
            if (!array.get(index).isJsonPrimitive()
                    || !array.get(index).getAsJsonPrimitive().isString()) {
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
        if (!object.get(property).isJsonPrimitive()
                || !object.get(property).getAsJsonPrimitive().isNumber()) {
            throw new IllegalArgumentException(property + " must be an integer");
        }
        String raw = object.get(property).getAsString();
        if (!raw.matches("-?\\d+")) {
            throw new IllegalArgumentException(property + " must be an integer");
        }
        return Long.parseLong(raw);
    }

    private static int optionalInt(JsonObject object, String property, int defaultValue) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            return defaultValue;
        }
        long value = requiredLong(object, property);
        if (value < Integer.MIN_VALUE || value > Integer.MAX_VALUE) {
            throw new IllegalArgumentException(property + " outside integer range");
        }
        return (int) value;
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

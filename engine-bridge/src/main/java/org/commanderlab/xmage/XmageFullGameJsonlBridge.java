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
            case "start_full_game" -> startFullGame(requestId);
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

            // PB-03: a REQUESTED starting state, not an injected outcome. The
            // engine-native restoration engine already exists and assembles state
            // through public engine APIs only; what was missing was any protocol
            // verb that could reach it, so the mechanism existed but nothing could
            // arrive. The request below is a frozen semantic record, which the
            // engine validates, materialises natively, and then READS BACK. The
            // Lab never interprets Magic state and never fabricates a post-state.
            //
            // Failure is closed at every step: an unsupported dimension, a plan the
            // engine refuses, or a readback that does not match all abort game
            // creation rather than leaving a partially materialised game.
            XmageNativeStateRestoration restoration = null;
            String requestedStartingStateDigest = null;
            if (payload.has("starting_state")
                    && !payload.get("starting_state").isJsonNull()) {
                if (!payload.get("starting_state").isJsonObject()) {
                    return error(
                            requestId,
                            "invalid_starting_state",
                            "starting_state must be an object when present",
                            false
                    );
                }
                JsonObject frozenRecord = payload.getAsJsonObject("starting_state");
                String planId = frozenRecord.has("plan_id")
                                && frozenRecord.get("plan_id").isJsonPrimitive()
                                && !frozenRecord.get("plan_id").getAsString().isBlank()
                        ? frozenRecord.get("plan_id").getAsString()
                        : "lab-requested";
                XmageNativeStateRestoration.Plan plan;
                try {
                    plan = XmageNativeStateRestoration.planFromFrozenRecord(
                            frozenRecord,
                            planId,
                            seed
                    );
                    XmageNativeStateRestoration.validatePlan(plan);
                } catch (XmageNativeStateRestoration.RestorationException exc) {
                    // The engine declined. Nothing has been materialised yet, so
                    // this is a refusal, not a partial success.
                    return error(
                            requestId,
                            "starting_state_unsupported",
                            "the engine refused the requested starting state: "
                                    + exc.getMessage(),
                            false
                    );
                } catch (RuntimeException exc) {
                    // A partially specified record currently makes the plan parser
                    // throw an unchecked failure rather than report which field was
                    // missing. It still must not be reported as a game-creation
                    // failure, because the cause was the requested state, not the
                    // game. The parser's unchecked throw is a robustness gap in the
                    // engine and is recorded as such; it is contained here, not
                    // silently absorbed.
                    return error(
                            requestId,
                            "starting_state_unsupported",
                            "the requested starting state was not accepted by the engine: "
                                    + exc.getClass().getSimpleName()
                                    + (exc.getMessage() == null ? "" : ": " + exc.getMessage()),
                            false
                    );
                }
                try {
                    List<String> identities = plan.objects().stream()
                            .map(XmageNativeStateRestoration.RequestedObject::cardIdentity)
                            .toList();
                    restoration = new XmageNativeStateRestoration(
                            plan,
                            XmageNativeStateRestoration.materializeCards(identities));
                } catch (RuntimeException exc) {
                    // Card materialisation is part of restoration. A refusal here is
                    // a restoration refusal, and reporting it as a generic creation
                    // failure would misattribute a capability gap to game creation.
                    return error(
                            requestId,
                            "starting_state_unsupported",
                            "the engine could not materialise the requested starting "
                                    + "state: " + exc.getMessage(),
                            false
                    );
                }
                requestedStartingStateDigest =
                        XmageNativeStateRestoration.digestJson(frozenRecord);
            }

            try {
                session = new XmageFullGameSession(
                        gameId,
                        new ArrayList<>(deckHandles),
                        startingPlayerSeat,
                        startingLife,
                        seed,
                        deckImporter,
                        restoration
                );
            } catch (RuntimeException exc) {
                if (restoration != null) {
                    // Pre-start assembly is part of restoration, so a failure here is
                    // a restoration refusal rather than a deck or creation failure.
                    session = null;
                    return error(
                            requestId,
                            "starting_state_rejected_by_engine",
                            "the engine rejected the requested starting state during "
                                    + "pre-start assembly: " + exc.getMessage(),
                            false
                    );
                }
                throw exc;
            }

            // VERIFY, do not assume. The authoritative state is read back from the
            // engine and digested. A mismatch means the engine did not materialise
            // what was requested, which is a defect, not a partial pass.
            String observedStartingStateDigest = null;
            if (restoration != null) {
                JsonObject readback = XmageNativeStateRestoration.readback(
                        session.restorationGame(), session.restorationSeats());
                observedStartingStateDigest =
                        XmageNativeStateRestoration.digestJson(readback);
                try {
                    // Lets the engine accept its OWN materialised state. An illegal
                    // materialisation throws here, which is how the engine refuses.
                    // It does NOT compare against the request: the request is a frozen
                    // semantic record and the readback is authoritative state, so
                    // comparing them is the Lab's verification, using the fixture the
                    // Lab already owns. Claiming a match here would be a check that
                    // never ran.
                    XmageNativeStateRestoration.revalidate(session.restorationGame());
                } catch (RuntimeException exc) {
                    session = null;
                    return error(
                            requestId,
                            "starting_state_rejected_by_engine",
                            "the engine rejected its own materialised state: "
                                    + exc.getMessage(),
                            false
                    );
                }
            }

            JsonObject responsePayload = new JsonObject();
            responsePayload.addProperty("game_id", gameId);
            responsePayload.addProperty("player_count", session.playerCount());
            responsePayload.addProperty("starting_player_seat", startingPlayerSeat);
            responsePayload.addProperty("starting_life", startingLife);
            responsePayload.addProperty("seed", seed);
            responsePayload.addProperty("seed_controlled", true);
            // PB-03 binding. requested/observed digests are both present only when
            // a starting state was actually requested and actually restored, so an
            // absent pair can never be read as a successful restoration.
            responsePayload.addProperty(
                    "starting_state_requested", restoration != null);
            responsePayload.addProperty(
                    "requested_starting_state_digest", requestedStartingStateDigest);
            responsePayload.addProperty(
                    "observed_starting_state_digest", observedStartingStateDigest);
            // True only when the ENGINE produced an authoritative readback. It does
            // NOT mean the readback matches the request; that comparison belongs to
            // the Lab, which owns the fixture, and is reported separately by the
            // qualification layer rather than asserted here.
            responsePayload.addProperty(
                    "starting_state_readback_observed",
                    restoration != null && observedStartingStateDigest != null);
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
    /**
     * Every decision class the full-game lane can present to an external pilot.
     *
     * <p>This is the enumerated external decision surface, kept next to the
     * capability payload that publishes it. It is verified against every
     * {@code decision_class} literal {@link XmageFullGamePlayer} can actually
     * request by {@code XmageFullGameDecisionSurfaceTest}, so a new class added
     * to the player without being declared here fails the build instead of
     * silently shrinking what the capability claims.
     */
    static final java.util.Set<String> LEGAL_ACTION_DECISION_CLASSES = java.util.Set.of(
            "priority",
            "target",
            "choose_object",
            "target_amount",
            "mulligan",
            "choose_use",
            "choice",
            "pile",
            "mana_payment",
            "announce_x",
            "amount",
            "multi_amount",
            "replacement_effect",
            "trigger_order",
            "mode",
            "declare_attacker",
            "declare_blocker");

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

        // What IS actually implemented on this lane, named precisely so it can be
        // consumed without overstating the global flags above.
        //
        // The engine enumerates the legal options for the decision it is
        // currently asking about, and accepts a submission of exactly those
        // options. That is a real, complete external decision surface for this
        // lane, and it is NOT what the two global flags mean: they mean a
        // free-standing legal-action API queryable at any time, which this lane
        // does not offer (get_legal_actions fails closed with STALE_DECISION
        // when no decision is pending). Both truths are published together and
        // the drift between them is the point, not an inconsistency to hide.
        //
        // legal_action_decision_classes is the enumerated surface. It is
        // asserted against every decision class XmageFullGamePlayer can
        // actually request by XmageFullGameDecisionSurfaceTest, so the two
        // cannot drift apart silently.
        capabilities.addProperty("decision_scoped_legal_actions_supported", true);
        capabilities.addProperty("decision_scoped_action_submission_supported", true);
        capabilities.addProperty(
                "legal_action_global_enumeration_supported", false);
        com.google.gson.JsonArray declaredClasses = new com.google.gson.JsonArray();
        for (String decisionClass : LEGAL_ACTION_DECISION_CLASSES) {
            declaredClasses.add(decisionClass);
        }
        capabilities.add("legal_action_decision_classes", declaredClasses);
        capabilities.addProperty(
                "legal_action_decision_class_count", LEGAL_ACTION_DECISION_CLASSES.size());

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
        // Why starting_state_injection_supported is false, itemised. A bare
        // boolean cannot support per-obligation admission: a qualifier that must
        // decide whether ONE frozen mid-game row is executable needs to know
        // WHICH dimensions the native restore path covers. The manifest was
        // already computed but never left the JVM, so it could not inform any
        // admission decision. It is published here verbatim, next to the flag it
        // qualifies, and is derived from the same restoration code that performs
        // the restore; it is never authored independently of that code.
        lane.add("state_restoration_dimensions", XmageNativeStateRestoration.dimensionsPayload());
        // PB-03 transport reachability, published as its own fact rather than
        // inferred from the dimension list. A dimension can be listed as supported
        // while nothing can actually deliver it, which is exactly the seam this
        // closes; the caller must be able to check reachability separately.
        lane.addProperty("starting_state_request_supported", true);
        lane.addProperty("starting_state_request_field", "starting_state");
        lane.addProperty("starting_state_request_message", "create_full_game");

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

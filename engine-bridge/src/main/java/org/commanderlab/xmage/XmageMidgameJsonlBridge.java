package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.repository.CardInfo;
import mage.cards.repository.CardRepository;
import mage.players.Player;

import java.util.ArrayList;
import java.util.HashMap;
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

    /** Placeholder that replaces a hand identity withheld from a wrong principal. */
    private static final String REDACTED_HAND_IDENTITY = "<hand-identity-redacted>";

    private final XmageDeckImporter deckImporter = new XmageDeckImporter();

    private XmageFullGameSession session;
    private XmageNativeStateRestoration restoration;
    private String planId;
    private String entryMode = "placement";
    private XmageMidgameCausalBridge.CausalStackPlan causalStackPlan;
    /** Commander stack sources published with the causal plan, by semantic id. */
    private Map<String, UUID> causalCommanderSources = Map.of();
    private XmageMidgameCausalBridge.CausalEliminationPlan causalEliminationPlan;

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
            case "complete_causal_reconstruction" ->
                    completeCausalReconstruction(requestId, request);
            case "get_midgame_state" -> getState(requestId, request);
            case "get_rules_rng_tape" -> getRulesRngTape(requestId);
            case "get_midgame_projection" -> getProjection(requestId, request);
            case "get_midgame_events" -> getEvents(requestId, request);
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
        return restorationFor(plan, XmageLosslessHiddenPlan.EMPTY);
    }

    private static XmageNativeStateRestoration restorationFor(
            XmageNativeStateRestoration.Plan plan, XmageLosslessHiddenPlan lossless) {
        List<String> identities = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedObject object : plan.objects()) {
            identities.add(object.cardIdentity());
        }
        for (XmageNativeStateRestoration.RequestedCommander commander : plan.commanders()) {
            identities.add(commander.cardIdentity());
        }
        // SLOT-04 library objects are placed after arrival from the same vehicle.
        identities.addAll(lossless.vehicleIdentities());
        return new XmageNativeStateRestoration(
                plan,
                XmageNativeStateRestoration.materializeCards(identities),
                lossless
        );
    }

    /**
     * Commander colours are read from the engine's own card registry rather
     * than a Lab-side table, so the scaffolding filler stays a construction
     * vehicle that tracks the real card's mana colours.
     */
    /**
     * The engine's own colored identity for a commander, from the card registry.
     *
     * <p>An empty set is a legitimate answer, not an error: a colorless
     * Commander (for example Karn, Silver Golem) really has no colored
     * component in its identity. The caller must scaffold such a deck with a
     * colorless basic land instead of a fabricated colored one. Commander
     * legality itself is decided by the engine's real-cards-only import, never
     * by this projection.</p>
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
        return colors;
    }

    private List<String> importScaffolding(
            XmageNativeStateRestoration.Plan plan, String deckTag) {
        return importScaffolding(plan, deckTag, XmageLosslessHiddenPlan.EMPTY);
    }

    private List<String> importScaffolding(
            XmageNativeStateRestoration.Plan plan, String deckTag, XmageLosslessHiddenPlan lossless) {
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
            // A declared lossless deck template must be exactly this scaffolding.
            lossless.validateScaffolding(player.playerId(), mainboard);
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
            String requestedEntryMode = stringValue(payload, "entry_mode");
            String resolvedEntryMode = requestedEntryMode.isBlank()
                    ? "placement"
                    : requestedEntryMode;
            if (!resolvedEntryMode.equals("placement")
                    && !resolvedEntryMode.equals("causal_stack")
                    && !resolvedEntryMode.equals("causal_elimination")) {
                return error(
                        requestId,
                        "unsupported_entry_mode",
                        "CREATE_MIDGAME_GAME supports entry_mode placement, causal_stack or "
                                + "causal_elimination; observed " + requestedEntryMode,
                        false
                );
            }

            return createForEntryMode(
                    requestId,
                    payload.getAsJsonObject("requested_starting_state"),
                    gameId,
                    planTag,
                    seed,
                    startingPlayerSeat,
                    startingLife,
                    resolvedEntryMode,
                    payload);
        } catch (XmageNativeStateRestoration.RestorationException exc) {
            return error(
                    requestId,
                    "midgame_starting_state_rejected",
                    exceptionMessage(exc),
                    false
            );
        } catch (XmageMidgameCausalBridge.CausalException exc) {
            return error(
                    requestId,
                    "midgame_causal_preparation_rejected",
                    exceptionMessage(exc),
                    false
            );
        } catch (Exception exc) {
            return error(requestId, "midgame_creation_failed", exceptionMessage(exc), false);
        }
    }

    /**
     * Builds the session for one entry mode and answers with the success
     * payload or a coded rejection. Unsupported causal preparations fail
     * closed here, before any game exists.
     */
    private Result createForEntryMode(
            String requestId,
            JsonObject requestedState,
            String gameId,
            String planTag,
            long seed,
            int startingPlayerSeat,
            int startingLife,
            String resolvedEntryMode,
            JsonObject payload) {
        try {
            if ("causal_stack".equals(resolvedEntryMode)) {
                return success(requestId, createCausalStack(
                        requestedState, gameId, planTag, seed,
                        startingPlayerSeat, startingLife, payload), false);
            }
            if ("causal_elimination".equals(resolvedEntryMode)) {
                return success(requestId, createCausalElimination(
                        requestedState, gameId, planTag, seed,
                        startingPlayerSeat, startingLife, payload), false);
            }
            return success(requestId, createPlacement(
                    requestedState, gameId, planTag, seed,
                    startingPlayerSeat, startingLife), false);
        } catch (XmageMidgameCausalBridge.CausalException exc) {
            return error(
                    requestId,
                    "midgame_causal_preparation_rejected",
                    exceptionMessage(exc),
                    false);
        }
    }

    private JsonObject createPlacement(
            JsonObject requestedState,
            String gameId,
            String planTag,
            long seed,
            int startingPlayerSeat,
            int startingLife) {
        XmageNativeStateRestoration.Plan plan =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        requestedState, planTag, seed);
        // Fail closed before any game mutation: the plan validator rejects
        // every unsupported dimension with a coded reason.
        XmageNativeStateRestoration.validatePlan(plan);
        XmageLosslessHiddenPlan lossless = XmageLosslessHiddenPlan.fromRecord(requestedState);
        Set<String> requestedPlayers = new HashSet<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : plan.players()) {
            requestedPlayers.add(player.playerId());
        }
        lossless.validatePlayers(requestedPlayers);

        List<String> handles = importScaffolding(plan, planTag, lossless);
        this.restoration = restorationFor(plan, lossless);
        this.planId = planTag;
        this.entryMode = "placement";
        this.session = new XmageFullGameSession(
                gameId,
                handles,
                startingPlayerSeat,
                startingLife,
                seed,
                deckImporter,
                restoration
        );

        JsonObject response = createdResponse(
                gameId, planTag, startingPlayerSeat, startingLife, seed);
        response.addProperty("entry_mode", "placement");
        // The pilot matches the engine's own offers (a cast, a mana ability, a
        // target) against the record's objects. Placed-object and commander ids
        // already appear in every offered action's metadata, so publishing the
        // maps adds no exposure; hand objects are the requesting record's own.
        response.add("placed_objects",
                XmageMidgameCausalBridge.placedObjectsPayload(restoration, plan.objects()));
        response.add("commander_objects",
                restoration.commanderCardIds(session.restorationGame(), session.restorationSeats()));
        return response;
    }

    /**
     * Causal-stack entry: the record's stack frames become a pre-causal
     * position (source cards in hand, declared fuel on the battlefield) and
     * the published causal plan tells the external pilot exactly which engine
     * transitions to cause. The engine casts, targets, pays and resolves;
     * this method places nothing on the stack itself.
     */
    private JsonObject createCausalStack(
            JsonObject requestedState,
            String gameId,
            String planTag,
            long seed,
            int startingPlayerSeat,
            int startingLife,
            JsonObject payload) {
        List<XmageMidgameCausalBridge.DeclaredCard> fuel =
                parseDeclaredCards(payload, "fuel");
        XmageMidgameCausalBridge.CausalStackPlan stackPlan =
                XmageMidgameCausalBridge.prepareCausalStack(
                        requestedState, fuel, planTag, seed);

        // A declared lossless deck template must be exactly the scaffolding,
        // on this entry as on placement.
        List<String> handles = importScaffolding(
                stackPlan.prepared().preStackPlan(), planTag,
                stackPlan.prepared().restoration().losslessHidden());
        this.restoration = stackPlan.prepared().restoration();
        this.planId = planTag;
        this.entryMode = "causal_stack";
        this.causalStackPlan = stackPlan;
        this.session = new XmageFullGameSession(
                gameId,
                handles,
                startingPlayerSeat,
                startingLife,
                seed,
                deckImporter,
                restoration
        );

        JsonObject response = createdResponse(
                gameId, planTag, startingPlayerSeat, startingLife, seed);
        response.addProperty("entry_mode", "causal_stack");
        this.causalCommanderSources = Map.copyOf(
                commanderStackSources(requestedState, stackPlan.prepared()));
        response.add("causal_plan", XmageMidgameCausalBridge.causalStackPayload(
                stackPlan, restoration, causalCommanderSources));
        return response;
    }

    /**
     * The stack sources that are commanders, bound to the game's own commander
     * card (the one the owner casts from the command zone), by semantic id.
     */
    private Map<String, UUID> commanderStackSources(
            JsonObject requestedState, XmageCausalStackReconstruction.Prepared prepared) {
        // The prepared frames, not the request: preparation clears the
        // record's stack once it has turned it into frames.
        Map<String, UUID> sources = new HashMap<>();
        Set<String> stackSources = new HashSet<>();
        for (XmageCausalStackReconstruction.StackFrame frame : prepared.bottomToTop()) {
            stackSources.add(frame.semanticId());
        }
        JsonObject commanderIds = restoration.commanderCardIds(
                session.restorationGame(), session.restorationSeats());
        for (JsonElement element : requestedState.getAsJsonArray("semantic_objects")) {
            JsonObject object = element.getAsJsonObject();
            String semanticId = object.get("semantic_id").getAsString();
            if (!stackSources.contains(semanticId) || !object.has("commander_id")
                    || object.get("commander_id").isJsonNull()) {
                continue;
            }
            String commanderId = object.get("commander_id").getAsString();
            if (commanderIds.has(commanderId)) {
                sources.put(semanticId, UUID.fromString(commanderIds.get(commanderId).getAsString()));
            }
        }
        return sources;
    }

    /**
     * Causal-elimination entry: the record's placeable dimensions plus the
     * declared instruments (damage spells in the actor's hand, mana on the
     * actor's battlefield). A victim life the engine cannot honour at
     * placement is substituted openly with the recorded starting life; the
     * recorded value is then reachable only by causing real damage. The engine
     * damages, resolves, applies SBAs and eliminates; this method sets no
     * life total and no lost/left flag itself.
     */
    private JsonObject createCausalElimination(
            JsonObject requestedState,
            String gameId,
            String planTag,
            long seed,
            int startingPlayerSeat,
            int startingLife,
            JsonObject payload) {
        if (!payload.has("elimination") || !payload.get("elimination").isJsonObject()) {
            throw new XmageMidgameCausalBridge.CausalException(
                    "MISSING_ELIMINATION_SPEC",
                    "CREATE_MIDGAME_GAME with entry_mode causal_elimination requires "
                            + "payload.elimination {actor, victim, instruments}; the lane never "
                            + "infers whom to eliminate or with what");
        }
        JsonObject spec = payload.getAsJsonObject("elimination");
        String actor = requiredTextIn(spec, "actor");
        String victim = requiredTextIn(spec, "victim");
        List<XmageMidgameCausalBridge.DeclaredCard> instruments =
                parseDeclaredCards(spec, "instruments");
        XmageMidgameCausalBridge.CausalEliminationPlan elimPlan =
                XmageMidgameCausalBridge.planCausalElimination(
                        requestedState, actor, victim, instruments, planTag, seed);

        List<String> handles = importScaffolding(elimPlan.plan(), planTag);
        this.restoration = restorationFor(elimPlan.plan());
        this.planId = planTag;
        this.entryMode = "causal_elimination";
        this.causalEliminationPlan = elimPlan;
        this.session = new XmageFullGameSession(
                gameId,
                handles,
                startingPlayerSeat,
                startingLife,
                seed,
                deckImporter,
                restoration
        );

        JsonObject response = createdResponse(
                gameId, planTag, startingPlayerSeat, startingLife, seed);
        response.addProperty("entry_mode", "causal_elimination");
        response.add("elimination_plan", XmageMidgameCausalBridge.eliminationPlanPayload(
                elimPlan, restoration));
        return response;
    }

    private JsonObject createdResponse(
            String gameId,
            String planTag,
            int startingPlayerSeat,
            int startingLife,
            long seed) {
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
        return response;
    }

    private static List<XmageMidgameCausalBridge.DeclaredCard> parseDeclaredCards(
            JsonObject holder, String property) {
        List<XmageMidgameCausalBridge.DeclaredCard> cards = new ArrayList<>();
        if (!holder.has(property) || holder.get(property).isJsonNull()) {
            return cards;
        }
        if (!holder.get(property).isJsonArray()) {
            throw new IllegalArgumentException(
                    property + " must be an array of {semantic_id, card_identity, owner, zone}");
        }
        for (JsonElement element : holder.getAsJsonArray(property)) {
            JsonObject card = element.getAsJsonObject();
            cards.add(new XmageMidgameCausalBridge.DeclaredCard(
                    requiredTextIn(card, "semantic_id"),
                    requiredTextIn(card, "card_identity"),
                    requiredTextIn(card, "owner"),
                    requiredTextIn(card, "zone")));
        }
        return cards;
    }

    private static String requiredTextIn(JsonObject object, String property) {
        if (!object.has(property) || object.get(property).isJsonNull()) {
            throw new IllegalArgumentException("missing required field: " + property);
        }
        String value = object.get(property).getAsString();
        if (value.isBlank()) {
            throw new IllegalArgumentException("blank required field: " + property);
        }
        return value;
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
    /**
     * Completes the explicitly requested arrival and reports the engine's own
     * construction verdict.
     *
     * <p><b>Hidden information.</b> The internal comparison stays authoritative
     * and complete: it runs against the engine's full field-level readback,
     * including every seat's hand, and its verdict and mismatch list are exactly
     * what the engine reported. The response, however, carries only externally
     * observable information. The raw readback is never returned; a
     * principal-scoped {@code observation} is returned instead, which follows the
     * same policy as {@code XmageFullGameStateRedactor}: a named requester sees
     * its own hand, every other principal's hand is present only as its count,
     * and when no requester is named no hand identities appear at all. The
     * reported {@code constructed_state_digest} is taken over that redacted
     * observation so a digest exposed to a wrong principal never commits to a
     * hidden hand identity. Mismatch strings carry the requester's own requested
     * plan content and observed counts, never another principal's card
     * identities.</p>
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
            String requesterPrincipal = optionalRequesterPrincipal(request);
            Map<String, Player> seats = requireSession().restorationSeats();
            restoration.restoreAfterArrival(requireSession().restorationGame(), seats);
            if (!"trigger_order".equals(requireSession().parkedDecisionClass())) {
                // XMage asks trigger_order from inside GameImpl.checkTriggered: the
                // engine thread is in the middle of its own state-based-action and
                // trigger check. A nested checkStateAndTriggered from this thread
                // would re-enter it and ask the same ordering again (a concurrent
                // pending decision). There the completion is a pure readback.
                XmageNativeStateRestoration.revalidate(requireSession().restorationGame());
            }
            JsonObject observed =
                    XmageNativeStateRestoration.readback(requireSession().restorationGame(), seats);
            XmageNativeStateRestoration.CompareVerdict verdict = restoration.compare(observed, seats);
            // SLOT-04 lossless dimensions are verified engine-direct with coded
            // mismatches only; they never enter the readback the observation
            // below is projected from.
            XmageLosslessHiddenPlan.Verification lossless = restoration.losslessHiddenVerification(
                    requireSession().restorationGame(), seats);
            List<String> allMismatches = new ArrayList<>(verdict.mismatches());
            allMismatches.addAll(lossless.mismatches());
            boolean constructionMatch = allMismatches.isEmpty();

            JsonObject observation = principalScopedObservation(observed, requesterPrincipal);
            JsonObject response = new JsonObject();
            response.addProperty("plan_id", planId);
            response.addProperty("construction_match", constructionMatch);
            response.addProperty("requested_state_digest", verdict.requestedDigest());
            response.addProperty(
                    "constructed_state_digest",
                    XmageNativeStateRestoration.digestJson(observation));
            response.addProperty(
                    "constructed_state_digest_scope", "principal_scoped_observation");
            JsonArray mismatches = new JsonArray();
            for (String mismatch : allMismatches) {
                mismatches.add(redactNativeIds(redactMismatch(mismatch, requesterPrincipal)));
            }
            response.add("mismatches", mismatches);
            // How many SLOT-04 lossless checks of each kind ran, so a consumer
            // can tell a passed check from one that never ran. Counts only: a
            // check names the player or object whose library order or face-down
            // state it verified, and this observation goes to a requester who
            // may not be entitled to know that such a state was requested.
            JsonObject losslessChecks = new JsonObject();
            for (String check : lossless.checks()) {
                String kind = check.substring(0, check.indexOf(':'));
                int ran = losslessChecks.has(kind) ? losslessChecks.get(kind).getAsInt() : 0;
                losslessChecks.addProperty(kind, ran + 1);
            }
            response.add("lossless_hidden_checks", losslessChecks);
            response.add("observation", observation);
            response.addProperty(
                    "observation_scope",
                    requesterPrincipal == null
                            ? "principal_neutral_opponent_hands_counts_only"
                            : "principal_scoped");
            // Deliberately no embedded decision frame. This payload is an
            // observation; a pending decision belongs to an acting principal
            // whose legal-option labels can name that principal's own hand, so
            // it must not ride inside another principal's response. The only
            // decision channel remains get_midgame_decision.
            return success(requestId, response, false);
        } catch (Exception exc) {
            return error(requestId, "midgame_arrival_failed", exceptionMessage(exc), false);
        }
    }

    /**
     * The optional requester binding for an arrival observation, resolved to the
     * requested-state principal label the observation's seats are keyed by.
     *
     * <p>A caller may name either the requested-state label ({@code P1}) or the
     * native session principal id for the same seat; both resolve to the same
     * seat, so a caller cannot accidentally receive a fully redacted observation
     * while believing it asked for its own. An absent or blank binding means no
     * principal is named, which is answered with the principal-neutral projection.
     * An unrecognized binding fails closed rather than silently over-redacting.</p>
     */
    private String optionalRequesterPrincipal(JsonObject request) {
        if (request == null || !request.has("payload") || !request.get("payload").isJsonObject()) {
            return null;
        }
        JsonObject payload = request.getAsJsonObject("payload");
        if (!payload.has("actor_id") || !payload.get("actor_id").isJsonPrimitive()) {
            return null;
        }
        String actorId = payload.get("actor_id").getAsString();
        if (actorId == null || actorId.isBlank()) {
            return null;
        }
        XmageFullGameSession current = requireSession();
        for (int seat = 0; seat < current.playerCount(); seat++) {
            String planLabel = "P" + (seat + 1);
            if (planLabel.equals(actorId) || actorId.equals(current.principalIdAtSeat(seat))) {
                return planLabel;
            }
        }
        throw new IllegalArgumentException("unknown requester principal: " + actorId);
    }

    /**
     * Removes a hand card identity from one of the engine's mismatch messages
     * unless the hand belongs to the requester.
     *
     * <p>{@code XmageNativeStateRestoration.compare} reports a missing requested
     * hand card as {@code hand subset <owner>|HAND|<cardIdentity>|tapped=...: requested
     * N observed M}. The count and the owning seat are public, but the card
     * identity is that principal's hidden information, so a mismatch list handed
     * to a different principal (or to an unbound caller) must not carry it. Every
     * other mismatch the engine produces names only public zones, seats,
     * commanders or counts and is returned unchanged.</p>
     */
    static String redactMismatch(String mismatch, String requesterPrincipal) {
        final String handMarker = "|HAND|";
        if (mismatch == null) {
            return null;
        }
        int marker = mismatch.indexOf(handMarker);
        if (marker < 0) {
            return mismatch;
        }
        int ownerStart = mismatch.lastIndexOf(' ', marker) + 1;
        String owner = mismatch.substring(ownerStart, marker);
        if (requesterPrincipal != null && requesterPrincipal.equals(owner)) {
            // The requester's own hand identity is legitimately observable to them.
            return mismatch;
        }
        int tapped = mismatch.indexOf("|tapped=", marker);
        int identityEnd = tapped >= 0 ? tapped : mismatch.indexOf(": ", marker);
        if (identityEnd < 0) {
            identityEnd = mismatch.length();
        }
        return mismatch.substring(0, marker) + REDACTED_HAND_IDENTITY + mismatch.substring(identityEnd);
    }

    /**
     * Removes the opaque native id the engine attaches to a hidden hand card.
     *
     * <p>When a restored hand card has left its owner's hand before arrival the
     * compare reports {@code hand injected object missing: <owner> native_id=<uuid>}.
     * The owner is public and the fact is diagnosable without the id, and the
     * uuid is a stable per-game handle to a hidden card, so the id is replaced
     * for every requester including the owner. No card name is involved.</p>
     */
    static String redactNativeIds(String mismatch) {
        int index = mismatch.indexOf("native_id=");
        if (index < 0) {
            return mismatch;
        }
        int end = index + "native_id=".length();
        while (end < mismatch.length() && !Character.isWhitespace(mismatch.charAt(end))) {
            end++;
        }
        return mismatch.substring(0, index)
                + "native_id=" + REDACTED_HAND_IDENTITY
                + mismatch.substring(end);
    }

    /**
     * Projects the engine's readback onto what one requester may legitimately
     * observe. This is a projection of the readback the engine already produced
     * for construction verification; it is not a second observation layer and it
     * computes no game fact.
     *
     * <p>Public dimensions are preserved verbatim (temporal point, seed binding,
     * seat life/lost/left/poison, hand and library counts, command zone, public
     * battlefield and public graveyard/exile contents). The only field removed is
     * a seat's {@code hand} identity list, which is re-attached solely for the
     * named requester's own seat. With no named requester no seat carries a hand
     * identity list, so an unbound caller cannot observe any principal's hand.</p>
     */
    private static JsonObject principalScopedObservation(
            JsonObject readback, String requesterPrincipal) {
        JsonObject redacted = new JsonObject();
        for (Map.Entry<String, JsonElement> entry : readback.entrySet()) {
            if (!"seats".equals(entry.getKey())) {
                redacted.add(entry.getKey(), entry.getValue());
            }
        }
        JsonArray seats = new JsonArray();
        for (JsonElement element : readback.getAsJsonArray("seats")) {
            JsonObject seat = element.getAsJsonObject();
            JsonObject projected = new JsonObject();
            boolean isRequester = requesterPrincipal != null
                    && seat.has("player_id")
                    && seat.get("player_id").isJsonPrimitive()
                    && requesterPrincipal.equals(seat.get("player_id").getAsString());
            for (Map.Entry<String, JsonElement> entry : seat.entrySet()) {
                if ("hand".equals(entry.getKey()) && !isRequester) {
                    // Opponent (and unbound) hands stay counts-only. hand_count
                    // is already present separately and is public.
                    continue;
                }
                projected.add(entry.getKey(), entry.getValue());
            }
            if (!isRequester) {
                projected.remove("hand");
            }
            seats.add(projected);
        }
        redacted.add("seats", seats);
        return redacted;
    }

    /**
     * Verifies a causal route against live engine state. This performs no
     * player decision at all: it reads the engine's stack (for the stack
     * route) or the engine's loss/leave flags plus survivor set (for the
     * elimination route) and reports the engine's own verdict. A route whose
     * causal outcome the engine has not produced fails closed with the
     * verification mismatches, never with a pass.
     */
    private Result completeCausalReconstruction(String requestId, JsonObject request) {
        try {
            requireSession();
            JsonObject payload = requireObjectPayload(
                    request, "COMPLETE_CAUSAL_RECONSTRUCTION requires an object payload");
            String mode = stringValue(payload, "mode");
            if (!"stack".equals(mode) && !"elimination".equals(mode)) {
                return error(
                        requestId,
                        "unknown_causal_mode",
                        "COMPLETE_CAUSAL_RECONSTRUCTION requires payload.mode stack or "
                                + "elimination",
                        false
                );
            }
            JsonObject verdict;
            if ("stack".equals(mode)) {
                if (!"causal_stack".equals(entryMode) || causalStackPlan == null) {
                    return error(
                            requestId,
                            "no_causal_stack_plan",
                            "This lane holds no causal-stack plan; create the game with "
                                    + "entry_mode causal_stack first",
                            false
                    );
                }
                verdict = XmageMidgameCausalBridge.verifyCausalStack(
                        requireSession(),
                        requireSession().restorationSeats(),
                        causalStackPlan.prepared(),
                        causalCommanderSources);
            } else {
                if (!"causal_elimination".equals(entryMode)
                        || causalEliminationPlan == null) {
                    return error(
                            requestId,
                            "no_causal_elimination_plan",
                            "This lane holds no causal-elimination plan; create the game with "
                                    + "entry_mode causal_elimination first",
                            false
                    );
                }
                verdict = XmageMidgameCausalBridge.verifyCausalElimination(
                        requireSession(),
                        requireSession().restorationSeats(),
                        causalEliminationPlan.victimPid(),
                        causalEliminationPlan.expectedSurvivors());
            }
            JsonObject response = new JsonObject();
            response.addProperty("plan_id", planId);
            response.addProperty("entry_mode", entryMode);
            response.add("verdict", verdict);
            // Deliberately no embedded decision frame (see
            // completeMidgameArrival): observations only, decisions only via
            // get_midgame_decision.
            return success(requestId, response, false);
        } catch (Exception exc) {
            return error(
                    requestId, "causal_reconstruction_failed", exceptionMessage(exc), false);
        }
    }

    /**
     * AF09: the engine's Rules-RNG results and a privileged state digest for the
     * clean-process replay twin. Refused unless the launch carries an
     * orchestration key; HMAC digests under that key only, never a principal's
     * observation, no card identity and no native id.
     */
    private Result getRulesRngTape(String requestId) {
        try {
            return success(requestId, requireSession().rulesRngTapePayload(), false);
        } catch (Exception exc) {
            return error(requestId, "rules_rng_tape_failed", exceptionMessage(exc), false);
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
     * The actor-entitled knowledge projection of the live game (AF05).
     *
     * <p>This is the qualified principal-scoped view of the full-game lane,
     * {@link XmageFullGameStateRedactor#actorView}, exposed on this lane for one
     * named principal: its own hand and mana, every other player's hand and
     * library as counts only, face-up exile and the battlefield publicly, a
     * face-down object's identity only where the engine entitles the viewer
     * (CR 708.5, LOOK_AT_FACE_DOWN, CR 723.4), and the engine's own look and
     * reveal log for that viewer. No principal-neutral or omniscient variant
     * exists: an absent or unknown requester fails closed.</p>
     */
    private Result getProjection(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(request, "GET_MIDGAME_PROJECTION requires payload");
            String requested = requiredText(payload, "actor_id");
            XmageFullGameSession current = requireSession();
            String label = null;
            UUID nativeId = null;
            for (int seat = 0; seat < current.playerCount(); seat++) {
                String planLabel = "P" + (seat + 1);
                String principal = current.principalIdAtSeat(seat);
                if (planLabel.equals(requested) || requested.equals(principal)) {
                    label = planLabel;
                    nativeId = UUID.fromString(principal);
                }
            }
            if (label == null) {
                throw new IllegalArgumentException("unknown requester principal");
            }
            mage.game.Game game = current.restorationGame();
            Player actor = game.getPlayer(nativeId);
            if (actor == null) {
                throw new IllegalArgumentException("requester principal has no live player");
            }
            // The view names other principals by opaque token and seat only. The
            // seat-to-label map lets a verifier bind each projected seat to its
            // requested-state principal without guessing. It is read from the
            // engine's own turn-order ring and must be a bijection.
            String[] labelBySeat = new String[current.playerCount()];
            for (Map.Entry<String, Player> entry : current.restorationSeats().entrySet()) {
                int engineSeat = XmageSeating.seat(game, entry.getValue().getId());
                if (engineSeat < 0 || engineSeat >= labelBySeat.length || labelBySeat[engineSeat] != null) {
                    throw new IllegalStateException("projected seats are not a bijection over the table");
                }
                labelBySeat[engineSeat] = entry.getKey();
            }
            JsonArray seatLabels = new JsonArray();
            for (String seatLabel : labelBySeat) {
                seatLabels.add(seatLabel);
            }
            JsonObject response = new JsonObject();
            response.addProperty("actor_id", label);
            response.addProperty("observation_scope", "principal_scoped");
            response.addProperty("projection_kind", "actor_entitled_knowledge_projection");
            response.add("seat_labels", seatLabels);
            response.add("view", XmageFullGameStateRedactor.actorView(game, actor));
            return success(requestId, response, false);
        } catch (Exception exc) {
            return error(requestId, "midgame_projection_failed", exceptionMessage(exc), false);
        }
    }

    /**
     * The public semantic event tape after {@code after_offset} events.
     *
     * <p>Every event is the engine's own {@link mage.game.events.GameEvent},
     * recorded by {@link XmagePublicEventWatcher} as part of the game state.
     * Players are named by requested-state seat label, objects by semantic id
     * when the restoration placed them; no native id is emitted. An object
     * whose identity was hidden at the event (a draw) carries no identity.</p>
     */
    private Result getEvents(String requestId, JsonObject request) {
        try {
            XmageFullGameSession current = requireSession();
            if (restoration == null) {
                return error(requestId, "no_starting_state_plan",
                        "This lane only records events for an explicitly requested starting state", false);
            }
            int afterOffset = 0;
            JsonObject payload = request.has("payload") && request.get("payload").isJsonObject()
                    ? request.getAsJsonObject("payload") : new JsonObject();
            if (payload.has("after_offset") && !payload.get("after_offset").isJsonNull()) {
                afterOffset = payload.get("after_offset").getAsInt();
            }
            XmagePublicEventWatcher watcher = current.restorationGame().getState()
                    .getWatcher(XmagePublicEventWatcher.class);
            if (watcher == null) {
                return error(requestId, "event_tape_unavailable", "no public event tape is registered", false);
            }
            if (afterOffset < 0 || afterOffset > watcher.size()) {
                return error(requestId, "invalid_event_offset",
                        "after_offset must be between 0 and " + watcher.size(), false);
            }
            Map<String, String> seatByPlayer = new HashMap<>();
            current.restorationSeats().forEach((label, player) -> seatByPlayer.put(player.getId().toString(), label));
            JsonArray events = new JsonArray();
            // A move into exile is named only once its face is known, and only
            // while the engine thread is parked on a decision: then no effect is
            // half done (a card exiled and not yet turned face down).
            if (current.parkedDecisionClass() != null) {
                watcher.settle(current.restorationGame());
            }
            for (JsonObject raw : watcher.eventsAfter(afterOffset)) {
                events.add(publicEvent(raw, seatByPlayer));
            }
            JsonObject response = new JsonObject();
            response.addProperty("after_offset", afterOffset);
            response.addProperty("latest_offset", watcher.size());
            response.addProperty("observation_scope", "public");
            response.add("events", events);
            return success(requestId, response, false);
        } catch (Exception exc) {
            return error(requestId, "midgame_events_failed", exceptionMessage(exc), false);
        }
    }

    private JsonObject publicEvent(JsonObject raw, Map<String, String> seatByPlayer) {
        JsonObject event = new JsonObject();
        for (String key : List.of("sequence", "type", "turn", "step", "amount", "flag", "data",
                "from", "to", "combat", "new_object", "last_power", "last_toughness", "coin_result", "coin_won",
                "public_identity", "target_name", "source_name")) {
            if (raw.has(key)) {
                event.add(key, raw.get(key));
            }
        }
        boolean publicIdentity = raw.get("public_identity").getAsBoolean();
        for (String key : List.of("player", "target", "source")) {
            if (!raw.has(key)) {
                continue;
            }
            String nativeId = raw.get(key).getAsString();
            String seat = seatByPlayer.get(nativeId);
            if (seat != null) {
                event.addProperty(key + "_player", seat);
            } else if (!"player".equals(key) && !hiddenOnTape(raw, key, publicIdentity)) {
                String semanticId = restoration.semanticIdOf(UUID.fromString(nativeId));
                if (semanticId != null) {
                    event.addProperty(key + "_object", semanticId);
                }
            }
        }
        return event;
    }

    /**
     * Whether the tape withholds this object: its own recorded flag decides, and
     * an event recorded without one names its objects only with a public identity.
     */
    private static boolean hiddenOnTape(JsonObject raw, String key, boolean publicIdentity) {
        String flag = key + "_hidden";
        return raw.has(flag) ? raw.get(flag).getAsBoolean() : !publicIdentity;
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

    /**
     * The native principal id at a seat, for a direct engine driver that must
     * address a principal in the native namespace (the concession contract's
     * {@code player_id}) rather than by requested-state label.
     *
     * <p>Package-private and never projected onto the wire: observations mask
     * every non-viewer id, so this cannot be reached through the protocol and
     * discloses nothing a pilot could not already address by seat.</p>
     */
    String nativePrincipalIdAtSeat(int seat) {
        return requireSession().principalIdAtSeat(seat);
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

    /**
     * Concession offer, using the exact Protocol-2 schema the full-game lane and
     * the external consumer already use: {@code payload.player_id}. There is no
     * second schema for this lane.
     */
    private Result getConcedeOffer(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(request, "GET_CONCEDE_OFFER requires payload");
            return success(
                    requestId,
                    requireSession().concedeOfferPayload(requiredText(payload, "player_id")),
                    false
            );
        } catch (Exception exc) {
            return error(requestId, "concede_offer_failed", exceptionMessage(exc), false);
        }
    }

    /**
     * Concession submission, using the exact Protocol-2 schema the full-game lane
     * and the external consumer already use:
     * {@code payload.proposal.{actor_id, player_id}} with actor == subject. The
     * proposal is bound and executed by the session's authoritative concede path,
     * so a stale or foreign proposal fails closed without touching game state.
     */
    private Result submitConcede(String requestId, JsonObject request) {
        try {
            JsonObject payload = requireObjectPayload(request, "SUBMIT_CONCEDE requires payload");
            if (!payload.has("proposal") || !payload.get("proposal").isJsonObject()) {
                return error(
                        requestId,
                        "invalid_midgame_decision",
                        "SUBMIT_CONCEDE requires payload.proposal",
                        false
                );
            }
            return success(
                    requestId,
                    requireSession().submitConcede(payload.getAsJsonObject("proposal")),
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
        capabilities.addProperty("event_log_supported", true);
        capabilities.addProperty("event_log_scope", "public_semantic_event_tape");
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
        // AF05: every observation this lane answers, with its scope. There is no
        // principal-neutral full state and no omniscient or raw-object message:
        // the principal-scoped ones require a known requester and fail closed.
        // The one orchestration channel (get_rules_rng_tape, AF09) is not an
        // observation: it is refused on every launch without an orchestration
        // key and answers HMAC digests under that key only.
        capabilities.addProperty("knowledge_projection_supported", true);
        JsonObject observationScopes = new JsonObject();
        observationScopes.addProperty("get_midgame_projection", "principal_scoped_required_requester");
        observationScopes.addProperty("get_midgame_state", "principal_scoped_required_requester_counts_only");
        observationScopes.addProperty("get_midgame_decision", "acting_principal_frame");
        observationScopes.addProperty("get_legal_actions", "acting_principal_frame");
        observationScopes.addProperty("get_midgame_events", "public_semantic_event_tape");
        // Not an observation: an orchestration channel for the replay twin, refused
        // unless the launch carries an orchestration key, and HMAC digests only.
        observationScopes.addProperty("get_rules_rng_tape",
                "orchestration_keyed_digests_refused_without_launch_key");
        capabilities.addProperty("orchestration_channel_enabled", XmageRulesRngResultTape.enabled());
        observationScopes.addProperty("complete_midgame_arrival",
                "principal_scoped_or_principal_neutral_opponent_hands_counts_only");
        capabilities.add("observation_scopes", observationScopes);
        capabilities.addProperty("omniscient_state_api", false);
        capabilities.addProperty("raw_engine_object_graph_api", false);

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

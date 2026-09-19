package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.cards.decks.Deck;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.game.CommanderFreeForAll;
import mage.game.GameOptions;
import mage.game.events.TableEvent;
import mage.game.mulligan.MulliganType;
import mage.players.Player;
import mage.util.ThreadUtils;
import mage.util.XmageThreadFactory;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

/**
 * One-process/one-game full Commander session for external pilot conformance.
 *
 * <p>Every credited session binds the orchestration seed to the authoritative
 * per-game Rules RNG ({@code game.setRulesSeed(seed)} plus
 * {@code game.setRequireExplicitSeed(true)}) immediately after game
 * construction and before any Rules-random consumption (initial shuffle,
 * choosing-player pick, opening hands). The legacy process-global
 * {@code RandomUtil} seed is retired: it is not Rules-RNG authority and no
 * non-Rules purpose for it remains in this session. The one-game-per-process
 * discipline is retained as defense in depth. JVM UUIDs are deliberately not
 * treated as seeded replay identity.</p>
 */
final class XmageFullGameSession {

    /** WS215 variable-player contract: Commander Free-for-All for 2..5 principals. */
    static final int MIN_PLAYERS = 2;
    static final int MAX_PLAYERS = 5;
    static final String EVIDENCE_CLASS = "technical_conformance_only";

    private final String protocolGameId;
    private final long seed;
    private final int playerCount;
    private final CommanderFreeForAll game;
    private final List<XmageFullGamePlayer> players;
    private final XmageFullGameDecisionController controller;
    private final int startingPlayerSeat;
    private final AtomicReference<Throwable> engineFailure = new AtomicReference<>();
    private final List<String> engineErrorDiagnostics =
            Collections.synchronizedList(new ArrayList<>());

    private Thread engineThread;
    private boolean started;

    XmageFullGameSession(
            String protocolGameId,
            List<String> deckHandles,
            int startingPlayerSeat,
            int startingLife,
            long seed,
            XmageDeckImporter deckImporter
    ) {
        if (protocolGameId == null || protocolGameId.isBlank()) {
            throw new IllegalArgumentException("game_id must be nonblank");
        }
        if (deckHandles == null || deckHandles.size() < MIN_PLAYERS
                || deckHandles.size() > MAX_PLAYERS) {
            throw new IllegalArgumentException(
                    "FULL_GAME_INVALID_PLAYER_COUNT: observed "
                            + (deckHandles == null ? "null" : deckHandles.size())
                            + " (supported " + MIN_PLAYERS + ".." + MAX_PLAYERS + ")"
            );
        }
        int sessionsPlayers = deckHandles.size();
        if (startingPlayerSeat < 0 || startingPlayerSeat >= sessionsPlayers) {
            throw new IllegalArgumentException("invalid starting_player_seat");
        }
        if (startingLife < 1) {
            throw new IllegalArgumentException("starting_life must be positive");
        }
        if (deckImporter == null) {
            throw new IllegalArgumentException("deckImporter must not be null");
        }

        this.protocolGameId = protocolGameId;
        this.seed = seed;
        this.playerCount = sessionsPlayers;
        this.startingPlayerSeat = startingPlayerSeat;
        this.controller = new XmageFullGameDecisionController(Duration.ofMinutes(2));

        List<Deck> decks = new ArrayList<>(playerCount);
        for (String deckHandle : deckHandles) {
            decks.add(deckImporter.requireDeck(deckHandle));
        }

        this.game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                startingLife,
                7
        );
        // WS213 authoritative Rules-RNG binding (WS212 engine contract): the
        // explicit orchestration seed replaces the per-game Rules stream and
        // arms the fail-closed explicit-seed requirement. This lands after
        // construction and before any Rules-random consumption: construction,
        // deck loading and player setup consume zero Rules randomness on the
        // pinned engine, while game.start/init performs the initial shuffle,
        // choosing-player pick and opening hands. The legacy process-global
        // seed call is retired here: it never was Rules-RNG authority.
        game.setRulesSeed(seed);
        game.setRequireExplicitSeed(true);
        game.setNumPlayers(playerCount);
        GameOptions options = new GameOptions();
        options.rollbackTurnsAllowed = false;
        game.setGameOptions(options);
        game.addTableEventListener(event -> {
            if (event.getEventType() != TableEvent.EventType.ERROR) {
                return;
            }
            Exception exception = event.getException();
            String exceptionClass = exception == null
                    ? "unknown"
                    : exception.getClass().getName();
            String exceptionMessage = exception == null ? "" : safeMessage(exception);
            String eventMessage = event.getMessage() == null ? "" : event.getMessage();
            engineErrorDiagnostics.add(
                    exceptionClass + ": " + exceptionMessage + " [event=" + eventMessage + "]"
            );
        });

        List<XmageFullGamePlayer> createdPlayers = new ArrayList<>(playerCount);
        for (int index = 0; index < playerCount; index++) {
            Deck deck = decks.get(index);
            XmageFullGamePlayer player = new XmageFullGamePlayer(
                    "Full Game Seat " + (index + 1),
                    RangeOfInfluence.ALL,
                    controller
            );
            player.init(game);
            game.loadCards(deck.getCards(), player.getId());
            game.loadCards(deck.getSideboard(), player.getId());
            game.addPlayer(player, deck);
            createdPlayers.add(player);
        }
        if (game.getPlayers().size() != playerCount) {
            throw new IllegalStateException(
                    "XMAGE_PLAYER_SETUP_FAILED: expected " + playerCount
                            + ", observed " + game.getPlayers().size()
            );
        }
        this.players = List.copyOf(createdPlayers);
    }

    int playerCount() {
        return playerCount;
    }

    synchronized JsonObject start() {
        if (started) {
            throw new IllegalStateException("FULL_GAME_ALREADY_STARTED");
        }
        started = true;
        Player startingPlayer = players.get(startingPlayerSeat);
        XmageThreadFactory gameThreadFactory = new XmageThreadFactory(
                ThreadUtils.THREAD_PREFIX_GAME + " full-game " + protocolGameId,
                true
        );
        engineThread = gameThreadFactory.newThread(() -> runEngine(startingPlayer.getId()));
        engineThread.start();
        controller.awaitPendingOrTerminal(Duration.ofSeconds(20));
        return statusPayload();
    }

    JsonObject pendingDecisionPayload() {
        ensureStarted();
        controller.awaitPendingOrTerminal(Duration.ofSeconds(20));
        JsonObject payload = statusPayload();
        JsonObject pending = controller.pendingDecision();
        payload.add("decision", pending == null ? JsonNull.INSTANCE : pending);
        return payload;
    }

    JsonObject submit(JsonObject response) {
        ensureStarted();
        controller.submit(response);
        String submittedDecisionId = response.get("decision_id").getAsString();
        awaitDecisionAdvance(submittedDecisionId, Duration.ofSeconds(20));
        return pendingDecisionPayload();
    }

    /**
     * WS204 B4-D generic decision-scoped legal-action projection.
     *
     * <p>Returns only the exact currently pending native decision projected
     * through {@link XmageFullGameActionProjection}. Never synthesizes options;
     * fails closed when no decision is pending. The payload is decision-scoped,
     * not a globally complete free-standing legal-actions API.</p>
     */
    synchronized JsonObject legalActionsPayload() {
        ensureStarted();
        controller.awaitPendingOrTerminal(Duration.ofSeconds(20));
        JsonObject pending = controller.pendingDecision();
        if (pending == null) {
            if (controller.terminalFailure() != null) {
                throw controller.terminalFailure();
            }
            throw new XmageFullGameDecisionController.DecisionException(
                    "STALE_DECISION: no pending decision"
            );
        }
        JsonArray actions;
        try {
            actions = XmageFullGameActionProjection.project(pending);
        } catch (XmageFullGameActionProjection.ProjectionException exc) {
            throw new XmageFullGameDecisionController.DecisionException(exc.getMessage(), exc);
        }
        JsonObject payload = statusPayload();
        payload.addProperty("decision_offset", pending.get("decision_offset").getAsLong());
        payload.addProperty("decision_id", pending.get("decision_id").getAsString());
        payload.addProperty("actor_id", pending.get("actor_id").getAsString());
        payload.addProperty("decision_class", pending.get("decision_class").getAsString());
        payload.addProperty("decision_scoped", true);
        payload.addProperty("global_capability_promoted", false);
        payload.addProperty("complete", true);
        payload.add("actions", actions);
        payload.add("decision", pending);
        return payload;
    }

    /**
     * WS204 B4-D generic submission: validates a generic proposal against the
     * exact current pending decision, translates only the selected authoritative
     * option into the native controller response, and lets XMage execute.
     */
    JsonObject submitAction(JsonObject proposal) {
        ensureStarted();
        controller.awaitPendingOrTerminal(Duration.ofSeconds(20));
        JsonObject pending = controller.pendingDecision();
        if (pending == null) {
            if (controller.terminalFailure() != null) {
                throw controller.terminalFailure();
            }
            throw new XmageFullGameDecisionController.DecisionException(
                    "STALE_DECISION: no pending decision"
            );
        }
        JsonObject response;
        try {
            response = XmageFullGameActionProjection.toDecisionResponse(pending, proposal);
        } catch (XmageFullGameActionProjection.ProjectionException exc) {
            throw new XmageFullGameDecisionController.DecisionException(exc.getMessage(), exc);
        }
        String legalActionId = proposal.has("legal_action_id")
                && !proposal.get("legal_action_id").isJsonNull()
                ? proposal.get("legal_action_id").getAsString() : "";
        String proposalType = proposal.has("action_type")
                && !proposal.get("action_type").isJsonNull()
                ? proposal.get("action_type").getAsString() : "";
        controller.submit(response);
        awaitDecisionAdvance(pending.get("decision_id").getAsString(), Duration.ofSeconds(20));
        JsonObject result = pendingDecisionPayload();
        result.addProperty("executed_decision_id", pending.get("decision_id").getAsString());
        result.addProperty("executed_actor_id", pending.get("actor_id").getAsString());
        result.addProperty("executed_action_id", legalActionId);
        result.addProperty("executed_action_type", proposalType);
        result.addProperty("decision_scoped", true);
        result.addProperty("global_capability_promoted", false);
        try {
            JsonObject next = controller.pendingDecision();
            if (next != null) {
                result.add("next_actions", XmageFullGameActionProjection.project(next));
            } else {
                result.add("next_actions", new JsonArray());
            }
        } catch (XmageFullGameActionProjection.ProjectionException exc) {
            result.add("next_actions", new JsonArray());
        }
        return result;
    }

    /**
     * WS213 live Rules-seed binding proof. Every field is read from the native
     * game at payload time; nothing is cached from construction. {@code
     * seed_supported} is true only when this proof holds for the run.
     */
    synchronized JsonObject rulesSeedBindingPayload() {
        JsonObject binding = new JsonObject();
        binding.addProperty("explicit_seed", seed);
        binding.addProperty("rules_seed", game.getRulesSeed());
        binding.addProperty("rules_seed_matches", game.getRulesSeed() == seed);
        binding.addProperty("rules_seed_explicit", game.isRulesSeedExplicit());
        binding.addProperty("require_explicit_seed", true);
        binding.addProperty("rules_random_calls", game.getRulesRandomCalls());
        binding.addProperty("seed_scope", "authoritative_per_game_rules_rng");
        binding.addProperty(
                "binding_model",
                "EXPLICIT_RULES_SEED: game.setRulesSeed(seed) + "
                        + "game.setRequireExplicitSeed(true) after construction, "
                        + "before game.start/init"
        );
        binding.addProperty(
                "seed_supported",
                game.getRulesSeed() == seed && game.isRulesSeedExplicit()
        );
        return binding;
    }

    /**
     * WS213 authoritative concession offer (WS211 engine contract).
     *
     * <p>Availability originates exclusively in {@code
     * game.canConcede(exactPrincipal)}: true if and only if the game has not
     * ended and the actor is a player still in this game. No Lab-side legality
     * heuristic exists. The offer is per-principal and carries no priority,
     * stack, step or turn-control requirement (CR 104.3a, CR 723.6).</p>
     */
    synchronized JsonObject concedeOfferPayload(String principalId) {
        ensureStarted();
        UUID principal = requireSessionPlayer(principalId);
        boolean available = game.canConcede(principal);
        JsonObject payload = statusPayload();
        payload.addProperty("concede_available", available);
        payload.addProperty("concede_actor_id", principal.toString());
        if (available) {
            JsonObject action = new JsonObject();
            action.addProperty("action_id", "concede:" + principal);
            action.addProperty("actor_id", principal.toString());
            action.addProperty("action_type", "concede");
            action.add("source_object_id", com.google.gson.JsonNull.INSTANCE);
            action.add("target_ids", new JsonArray());
            action.add("allowed_target_ids", new JsonArray());
            action.add("modes", new JsonArray());
            JsonObject metadata = new JsonObject();
            metadata.addProperty("availability", "Game.canConcede(exactPrincipal)");
            metadata.addProperty("rules_authority", "xmage");
            action.add("metadata", metadata);
            payload.add("concede_action", action);
        } else {
            payload.add("concede_action", com.google.gson.JsonNull.INSTANCE);
        }
        return payload;
    }

    /**
     * WS213 authoritative concession execution (WS211 engine contract).
     *
     * <p>Binding order: the proposal must name the exact native session player
     * UUID as both actor and subject (actor == subject == exact principal).
     * A controller UUID named for a controlled player is rejected: execution
     * always submits the named principal itself to native {@code
     * game.concede}, so one principal can never be conceded for another.
     * Availability is re-checked live; stale requests fail closed. Execution
     * is native (one-shot principal-bound authorization releases the player's
     * exact native concede path; no Lab-side outcome is synthesized).</p>
     */
    synchronized JsonObject submitConcede(JsonObject proposal) {
        ensureStarted();
        if (proposal == null) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: concede proposal is null"
            );
        }
        String actor = textOrEmpty(proposal, "actor_id");
        String subject = textOrEmpty(proposal, "player_id");
        if (actor.isBlank() || subject.isBlank()) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: concede proposal requires actor_id and player_id"
            );
        }
        if (!actor.equals(subject)) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: concede actor must be the conceding principal itself"
            );
        }
        UUID principal = requireSessionPlayer(actor);
        if (!game.canConcede(principal)) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "CONCEDE_UNAVAILABLE: Game.canConcede rejects this principal now"
            );
        }
        XmageFullGamePlayer player = playerById(principal);
        player.armConcession(principal);
        try {
            game.concede(principal);
        } finally {
            player.disarmConcession(principal);
        }
        JsonObject result = pendingDecisionPayload();
        result.addProperty("conceded_actor_id", principal.toString());
        result.addProperty("concede_available_before", true);
        result.addProperty("concede_available_after", game.canConcede(principal));
        return result;
    }

    private UUID requireSessionPlayer(String principalId) {
        UUID principal;
        try {
            principal = UUID.fromString(principalId == null ? "" : principalId.trim());
        } catch (IllegalArgumentException exc) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: unknown concede principal", exc
            );
        }
        for (XmageFullGamePlayer player : players) {
            if (player.getId().equals(principal)) {
                return principal;
            }
        }
        throw new XmageFullGameDecisionController.DecisionException(
                "PILOT_RESPONSE_INVALID: unknown concede principal"
        );
    }

    private XmageFullGamePlayer playerById(UUID principal) {
        for (XmageFullGamePlayer player : players) {
            if (player.getId().equals(principal)) {
                return player;
            }
        }
        throw new XmageFullGameDecisionController.DecisionException(
                "PILOT_RESPONSE_INVALID: unknown concede principal"
        );
    }

    private static String textOrEmpty(JsonObject proposal, String property) {
        if (!proposal.has(property) || proposal.get(property).isJsonNull()) {
            return "";
        }
        try {
            return proposal.get(property).getAsString().trim();
        } catch (RuntimeException exc) {
            throw new XmageFullGameDecisionController.DecisionException(
                    "PILOT_RESPONSE_INVALID: " + property + " must be a string", exc
            );
        }
    }

    JsonObject resultPayload() {
        ensureStarted();
        JsonObject payload = statusPayload();
        payload.add("transcript", controller.transcript());
        payload.addProperty("decision_count", controller.decisionCount());
        payload.addProperty("evidence_class", EVIDENCE_CLASS);
        payload.addProperty("consumed_gameplay_evidence", false);
        payload.addProperty("holdout_consumed", false);
        payload.addProperty("official_campaign_eligible", false);
        payload.addProperty("rules_authority", "xmage");
        payload.addProperty("decision_policy_authority", "commander_lab_external_pilot");
        payload.addProperty("seed", seed);
        payload.addProperty("seed_scope", "single_isolated_jvm_process");
        payload.add("rules_seed_binding", rulesSeedBindingPayload());
        payload.addProperty("bit_exact_replay_validated", false);
        return payload;
    }

    boolean isTerminal() {
        return controller.terminalFailure() != null || controller.pendingDecision() == null
                && engineThread != null && !engineThread.isAlive();
    }

    private void awaitDecisionAdvance(String submittedDecisionId, Duration timeout) {
        long deadlineNanos = System.nanoTime() + timeout.toNanos();
        while (true) {
            if (controller.terminalFailure() != null || isEngineTerminal()) {
                return;
            }
            JsonObject pending = controller.pendingDecision();
            if (pending == null) {
                return;
            }
            String pendingDecisionId = pending.get("decision_id").getAsString();
            if (!submittedDecisionId.equals(pendingDecisionId)) {
                return;
            }
            if (System.nanoTime() >= deadlineNanos) {
                throw new XmageFullGameDecisionController.DecisionException(
                        "DECISION_ADVANCE_TIMEOUT: engine did not consume " + submittedDecisionId
                );
            }
            try {
                Thread.sleep(1L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                throw new XmageFullGameDecisionController.DecisionException(
                        "DECISION_ADVANCE_TIMEOUT: interrupted while advancing "
                                + submittedDecisionId,
                        exc
                );
            }
        }
    }

    private void runEngine(UUID startingPlayerId) {
        try {
            game.start(startingPlayerId);
            if (game.getTotalErrorsCount() != 0) {
                throw new IllegalStateException(
                        "XMAGE_INTERNAL_ERRORS: " + game.getTotalErrorsCount()
                                + "; diagnostics=" + diagnosticSummary()
                );
            }
        } catch (Throwable exc) {
            engineFailure.compareAndSet(null, exc);
            controller.failClosed(
                    "XMAGE_FULL_GAME_FAILED",
                    exc.getClass().getSimpleName() + ": " + safeMessage(exc)
            );
        } finally {
            controller.markTerminal();
        }
    }

    private synchronized void ensureStarted() {
        if (!started) {
            throw new IllegalStateException("FULL_GAME_NOT_STARTED");
        }
    }

    private JsonObject statusPayload() {
        JsonObject payload = new JsonObject();
        payload.addProperty("game_id", protocolGameId);
        payload.addProperty("engine_game_id", game.getId().toString());
        payload.addProperty("player_count", game.getPlayers().size());
        payload.addProperty("starting_player_seat", startingPlayerSeat);
        payload.addProperty("seed", seed);
        payload.addProperty("started", started);
        payload.addProperty("terminal", isEngineTerminal());
        payload.addProperty("engine_thread_alive", engineThread != null && engineThread.isAlive());
        payload.addProperty(
                "engine_thread_name",
                engineThread == null ? "" : engineThread.getName()
        );
        payload.addProperty("decision_count", controller.decisionCount());
        payload.addProperty("engine_error_count", game.getTotalErrorsCount());
        payload.add("engine_error_diagnostics", diagnosticPayload());
        payload.addProperty("evidence_class", EVIDENCE_CLASS);
        payload.addProperty("consumed_gameplay_evidence", false);
        payload.addProperty("holdout_consumed", false);
        payload.addProperty("operational_pod_size", playerCount);

        Throwable failure = engineFailure.get();
        if (failure == null && controller.terminalFailure() == null) {
            payload.add("failure", JsonNull.INSTANCE);
        } else {
            JsonObject error = new JsonObject();
            if (failure != null) {
                error.addProperty("type", failure.getClass().getName());
                error.addProperty("message", safeMessage(failure));
            } else {
                error.addProperty("type", "decision_controller");
                error.addProperty("message", controller.terminalFailure().getMessage());
            }
            payload.add("failure", error);
        }

        JsonArray outcomes = new JsonArray();
        int seat = 0;
        for (Player player : game.getPlayers().values()) {
            JsonObject item = new JsonObject();
            item.addProperty("seat", seat++);
            item.addProperty("player_id", player.getId().toString());
            item.addProperty("life", player.getLife());
            item.addProperty("won", player.hasWon());
            item.addProperty("lost", player.hasLost());
            item.addProperty("left", player.hasLeft());
            // WS213 live authoritative availability per principal (WS211):
            // proof, not heuristic; re-evaluated on every payload.
            item.addProperty("can_concede", game.canConcede(player.getId()));
            outcomes.add(item);
        }
        payload.add("outcomes", outcomes);
        payload.add("rules_seed_binding", rulesSeedBindingPayload());
        payload.addProperty("turn_number", game.getState().getTurnNum());
        return payload;
    }

    private JsonArray diagnosticPayload() {
        JsonArray payload = new JsonArray();
        synchronized (engineErrorDiagnostics) {
            for (String diagnostic : engineErrorDiagnostics) {
                payload.add(diagnostic);
            }
        }
        return payload;
    }

    private String diagnosticSummary() {
        synchronized (engineErrorDiagnostics) {
            if (engineErrorDiagnostics.isEmpty()) {
                return "[]";
            }
            int limit = Math.min(5, engineErrorDiagnostics.size());
            return engineErrorDiagnostics.subList(0, limit).toString();
        }
    }

    private boolean isEngineTerminal() {
        return started
                && engineThread != null
                && !engineThread.isAlive();
    }

    private static String safeMessage(Throwable exc) {
        String message = exc.getMessage();
        return message == null || message.isBlank() ? exc.getClass().getName() : message;
    }
}
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
import mage.util.RandomUtil;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

/**
 * One-process/one-game full Commander session for external pilot conformance.
 *
 * <p>XMage 1.4.61 exposes a process-global RNG. This session therefore refuses
 * to host a second game and expects the Python runner to launch a fresh bridge
 * JVM per game. The supplied seed is applied before any game shuffle. JVM UUIDs
 * are deliberately not treated as seeded replay identity.</p>
 */
final class XmageFullGameSession {

    static final int PLAYER_COUNT = 4;
    static final String EVIDENCE_CLASS = "technical_conformance_only";

    private final String protocolGameId;
    private final long seed;
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
        if (deckHandles == null || deckHandles.size() != PLAYER_COUNT) {
            throw new IllegalArgumentException(
                    "FULL_GAME_REQUIRES_EXACTLY_FOUR_PLAYERS: observed "
                            + (deckHandles == null ? "null" : deckHandles.size())
            );
        }
        if (startingPlayerSeat < 0 || startingPlayerSeat >= PLAYER_COUNT) {
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
        this.startingPlayerSeat = startingPlayerSeat;
        this.controller = new XmageFullGameDecisionController(Duration.ofMinutes(2));

        List<Deck> decks = new ArrayList<>(PLAYER_COUNT);
        for (String deckHandle : deckHandles) {
            decks.add(deckImporter.requireDeck(deckHandle));
        }

        // Pinned XMage 1.4.61 uses one static RandomUtil RNG. Per-process game
        // isolation is therefore a correctness requirement, not an optimization.
        RandomUtil.setSeed(seed);

        this.game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                startingLife,
                7
        );
        game.setNumPlayers(PLAYER_COUNT);
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

        List<XmageFullGamePlayer> createdPlayers = new ArrayList<>(PLAYER_COUNT);
        for (int index = 0; index < PLAYER_COUNT; index++) {
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
        if (game.getPlayers().size() != PLAYER_COUNT) {
            throw new IllegalStateException(
                    "XMAGE_PLAYER_SETUP_FAILED: expected 4, observed " + game.getPlayers().size()
            );
        }
        this.players = List.copyOf(createdPlayers);
    }

    synchronized JsonObject start() {
        if (started) {
            throw new IllegalStateException("FULL_GAME_ALREADY_STARTED");
        }
        started = true;
        Player startingPlayer = players.get(startingPlayerSeat);
        engineThread = new Thread(
                () -> runEngine(startingPlayer.getId()),
                "xmage-full-game-" + protocolGameId
        );
        engineThread.setDaemon(true);
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
        payload.addProperty("decision_count", controller.decisionCount());
        payload.addProperty("engine_error_count", game.getTotalErrorsCount());
        payload.add("engine_error_diagnostics", diagnosticPayload());
        payload.addProperty("evidence_class", EVIDENCE_CLASS);
        payload.addProperty("consumed_gameplay_evidence", false);
        payload.addProperty("holdout_consumed", false);
        payload.addProperty("operational_pod_size", PLAYER_COUNT);

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
            outcomes.add(item);
        }
        payload.add("outcomes", outcomes);
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
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
 * <p>XMage 1.4.61 exposes a process-global RNG. This session therefore refuses
 * to host a second game and expects the caller to launch a fresh bridge JVM per
 * game. The supplied seed is applied before any game shuffle. Raw JVM UUIDs are
 * not part of the production observation/replay identity.</p>
 */
final class XmageFullGameSession {

    static final int MIN_PLAYER_COUNT = 2;
    static final int MAX_PLAYER_COUNT = 5;
    static final String EVIDENCE_CLASS = "technical_conformance_only";

    private final String protocolGameId;
    private final long seed;
    private final CommanderFreeForAll game;
    private final List<XmageFullGamePlayer> players;
    private final XmageFullGameDecisionController controller;
    private final XmageKnowledgeLedger knowledgeLedger;
    private final int startingPlayerSeat;
    private final int configuredPlayerCount;
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
        int observedPlayers = deckHandles == null ? -1 : deckHandles.size();
        if (!supportsPlayerCount(observedPlayers)) {
            throw new IllegalArgumentException(
                    "FULL_GAME_REQUIRES_2_TO_5_PLAYERS: observed "
                            + (deckHandles == null ? "null" : observedPlayers)
            );
        }
        if (startingPlayerSeat < 0 || startingPlayerSeat >= observedPlayers) {
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
        this.configuredPlayerCount = observedPlayers;
        this.controller = new XmageFullGameDecisionController(Duration.ofMinutes(2));
        this.knowledgeLedger = new XmageKnowledgeLedger();

        List<Deck> decks = new ArrayList<>(configuredPlayerCount);
        for (String deckHandle : deckHandles) {
            decks.add(deckImporter.requireDeck(deckHandle));
        }
        for (int index = 0; index < decks.size(); index++) {
            knowledgeLedger.registerDeck(index, decks.get(index));
        }

        RandomUtil.setSeed(seed);

        this.game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                startingLife,
                7
        );
        game.setNumPlayers(configuredPlayerCount);
        GameOptions options = new GameOptions();
        options.rollbackTurnsAllowed = false;
        game.setGameOptions(options);
        XmageFullGameStateRedactor.registerKnowledgeLedger(game, knowledgeLedger);
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

        List<XmageFullGamePlayer> createdPlayers = new ArrayList<>(configuredPlayerCount);
        for (int index = 0; index < configuredPlayerCount; index++) {
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
        if (game.getPlayers().size() != configuredPlayerCount) {
            throw new IllegalStateException(
                    "XMAGE_PLAYER_SETUP_FAILED: expected " + configuredPlayerCount
                            + ", observed " + game.getPlayers().size()
            );
        }
        this.players = List.copyOf(createdPlayers);
        XmageFullGameStateRedactor.registerSeats(game, this.players);
    }

    static boolean supportsPlayerCount(int playerCount) {
        return playerCount >= MIN_PLAYER_COUNT && playerCount <= MAX_PLAYER_COUNT;
    }

    int playerCount() {
        return configuredPlayerCount;
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

    JsonObject observationPayload(int viewerSeat, int decisionSubjectSeat) {
        ensureStarted();
        if (viewerSeat < 0 || viewerSeat >= players.size()) {
            throw new IllegalArgumentException("invalid viewer_seat");
        }
        if (decisionSubjectSeat < 0 || decisionSubjectSeat >= players.size()) {
            throw new IllegalArgumentException("invalid decision_subject_seat");
        }
        Player viewer = players.get(viewerSeat);
        Player subject = players.get(decisionSubjectSeat);
        JsonObject payload = new JsonObject();
        payload.addProperty("viewer_player_id", knowledgeLedger.playerRef(viewer.getId()));
        payload.addProperty("decision_subject_player_id", knowledgeLedger.playerRef(subject.getId()));
        payload.addProperty("viewer_seat", viewerSeat);
        payload.addProperty("decision_subject_seat", decisionSubjectSeat);
        payload.add("observation", knowledgeLedger.snapshot(game, viewer, subject));
        payload.addProperty("terminal", isEngineTerminal());
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
        payload.addProperty("player_count", configuredPlayerCount);
        payload.addProperty("live_player_count", game.getPlayers().size());
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
        payload.addProperty("operational_pod_size", configuredPlayerCount);
        payload.add("live_player_order", XmageFullGameStateRedactor.livePlayerOrder(game));

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
        for (int seat = 0; seat < players.size(); seat++) {
            Player player = players.get(seat);
            JsonObject item = new JsonObject();
            item.addProperty("seat", seat);
            item.addProperty("player_id", knowledgeLedger.playerRef(player.getId()));
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

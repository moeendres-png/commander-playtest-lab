package org.commanderlab.xmage;

import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.cards.decks.Deck;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
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
import java.util.concurrent.atomic.AtomicReference;

/** One-game XMage WS-26 qualification session. Never used as a production provider surface. */
final class XmageWs26QualificationSession {

    static final String LANE = "xmage_ws26_qualification";
    static final String EVIDENCE_CLASS = "runtime_qualification_only";

    private final String protocolGameId;
    private final long seed;
    private final XmageQualificationCommanderGame game;
    private final List<XmageFullGamePlayer> players;
    private final List<Deck> decks;
    private final XmageFullGameDecisionController controller;
    private final XmageKnowledgeLedger knowledgeLedger;
    private final int startingPlayerSeat;
    private final AtomicReference<Throwable> engineFailure = new AtomicReference<>();
    private final List<String> engineErrorDiagnostics = Collections.synchronizedList(new ArrayList<>());

    private Thread engineThread;
    private boolean started;
    private volatile XmageWs26Scenario.Applied appliedScenario;
    private volatile XmageWs26ReplayRecorder replayRecorder;
    private JsonObject configuredScenario;
    private String executionEntryMode;

    XmageWs26QualificationSession(
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
        int playerCount = deckHandles == null ? -1 : deckHandles.size();
        if (!XmageFullGameSession.supportsPlayerCount(playerCount)) {
            throw new IllegalArgumentException("FULL_GAME_REQUIRES_2_TO_5_PLAYERS: observed " + playerCount);
        }
        if (startingPlayerSeat < 0 || startingPlayerSeat >= playerCount) {
            throw new IllegalArgumentException("invalid starting_player_seat");
        }
        if (startingLife < 1) {
            throw new IllegalArgumentException("starting_life must be positive");
        }
        this.protocolGameId = protocolGameId;
        this.seed = seed;
        this.startingPlayerSeat = startingPlayerSeat;
        this.controller = new XmageFullGameDecisionController(Duration.ofMinutes(2));
        this.knowledgeLedger = new XmageKnowledgeLedger();

        List<Deck> loadedDecks = new ArrayList<>(playerCount);
        for (String handle : deckHandles) {
            loadedDecks.add(deckImporter.requireDeck(handle));
        }
        this.decks = List.copyOf(loadedDecks);
        for (int index = 0; index < decks.size(); index++) {
            knowledgeLedger.registerDeck(index, decks.get(index));
        }

        RandomUtil.setSeed(seed);
        XmageWs26RulesRngTape.begin();

        this.game = new XmageQualificationCommanderGame(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                MulliganType.LONDON.getMulligan(1),
                startingLife,
                7
        );
        game.setNumPlayers(playerCount);
        GameOptions options = new GameOptions();
        options.rollbackTurnsAllowed = false;
        game.setGameOptions(options);
        XmageFullGameStateRedactor.registerKnowledgeLedger(game, knowledgeLedger);
        game.addTableEventListener(event -> {
            if (event.getEventType() == TableEvent.EventType.ERROR) {
                Exception exception = event.getException();
                String exceptionClass = exception == null ? "unknown" : exception.getClass().getName();
                String exceptionMessage = exception == null ? "" : safeMessage(exception);
                String eventMessage = event.getMessage() == null ? "" : event.getMessage();
                engineErrorDiagnostics.add(exceptionClass + ": " + exceptionMessage + " [event=" + eventMessage + "]");
            }
        });

        List<XmageFullGamePlayer> created = new ArrayList<>(playerCount);
        for (int index = 0; index < playerCount; index++) {
            Deck deck = decks.get(index);
            XmageFullGamePlayer player = new XmageFullGamePlayer(
                    "WS26 Seat " + (index + 1), RangeOfInfluence.ALL, controller
            );
            player.init(game);
            game.loadCards(deck.getCards(), player.getId());
            game.loadCards(deck.getSideboard(), player.getId());
            game.addPlayer(player, deck);
            created.add(player);
        }
        this.players = List.copyOf(created);
        XmageFullGameStateRedactor.registerSeats(game, players);
    }

    synchronized JsonObject configureScenario(JsonObject scenario) {
        if (started) throw new IllegalStateException("SCENARIO_AFTER_GAME_START");
        if (configuredScenario != null) throw new IllegalStateException("SCENARIO_ALREADY_CONFIGURED");
        GameOptions options = new GameOptions();
        options.rollbackTurnsAllowed = false;
        String executionEntryMode = scenario.has("execution_entry_mode")
                ? scenario.get("execution_entry_mode").getAsString()
                : XmageWs26Scenario.NATIVE_STATE_LOAD;
        options.testMode = !XmageWs26Scenario.NATURAL_GAME_START.equals(executionEntryMode);
        options.skipInitShuffling = !XmageWs26Scenario.NATURAL_GAME_START.equals(executionEntryMode);
        game.setGameOptions(options);
        this.executionEntryMode = executionEntryMode;
        this.configuredScenario = scenario.deepCopy();
        if (XmageWs26Scenario.NATURAL_GAME_START.equals(executionEntryMode)) {
            appliedScenario = XmageWs26Scenario.apply(
                    scenario, game, players, decks, knowledgeLedger, seed, startingPlayerSeat
            );
            replayRecorder = new XmageWs26ReplayRecorder(
                    game, players, knowledgeLedger, appliedScenario.semanticObjectIds()
            );
        }
        JsonObject payload = new JsonObject();
        payload.addProperty("scenario_id", scenario.get("scenario_id").getAsString());
        payload.addProperty("execution_entry_mode", executionEntryMode);
        if (appliedScenario == null) {
            JsonObject deferred = new JsonObject();
            deferred.addProperty("status", "DEFERRED_UNTIL_NATIVE_ENGINE_INITIALIZATION");
            deferred.addProperty("fail_closed", true);
            payload.add("native_validation", deferred);
        } else {
            payload.addProperty("scenario_sha256", appliedScenario.scenarioSha256());
            payload.add("native_validation", appliedScenario.validation().deepCopy());
        }
        payload.addProperty("configured", true);
        return payload;
    }

    synchronized JsonObject start() {
        if (started) throw new IllegalStateException("FULL_GAME_ALREADY_STARTED");
        if (configuredScenario == null || executionEntryMode == null) {
            throw new IllegalStateException("QUALIFICATION_SCENARIO_REQUIRED");
        }
        started = true;
        Player startingPlayer = players.get(startingPlayerSeat);
        XmageThreadFactory factory = new XmageThreadFactory(
                ThreadUtils.THREAD_PREFIX_GAME + " ws26 " + protocolGameId, true
        );
        engineThread = factory.newThread(() -> runEngine(startingPlayer.getId()));
        engineThread.start();
        controller.awaitPendingOrTerminal(Duration.ofSeconds(20));
        failIfEngineFailed();
        if (replayRecorder == null) throw new IllegalStateException("NATIVE_STATE_LOAD_RECORDER_NOT_INITIALIZED");
        replayRecorder.checkpoint("game_started_or_first_decision");
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

    JsonObject observationPayload(int viewerSeat, int subjectSeat) {
        ensureStarted();
        if (viewerSeat < 0 || viewerSeat >= players.size() || subjectSeat < 0 || subjectSeat >= players.size()) {
            throw new IllegalArgumentException("invalid observation seat");
        }
        Player viewer = players.get(viewerSeat);
        Player subject = players.get(subjectSeat);
        JsonObject payload = new JsonObject();
        payload.addProperty("viewer_seat", viewerSeat + 1);
        payload.addProperty("decision_subject_seat", subjectSeat + 1);
        payload.add("observation", XmageFullGameStateRedactor.actorView(game, viewer, subject));
        payload.addProperty("terminal", isEngineTerminal());
        return payload;
    }

    JsonObject submit(JsonObject response) {
        ensureStarted();
        JsonObject pending = controller.pendingDecision();
        if (pending == null) throw new IllegalStateException("STALE_DECISION: no pending decision");
        XmageWs26ReplayRecorder.Checkpoint before = replayRecorder.checkpoint("before_decision");
        String submittedDecisionId = pending.get("decision_id").getAsString();
        try {
            controller.submit(response);
        } catch (RuntimeException exc) {
            replayRecorder.recordRejectedDecision(pending, response, safeMessage(exc));
            throw exc;
        }
        awaitDecisionAdvance(submittedDecisionId, Duration.ofSeconds(20));
        XmageWs26ReplayRecorder.Checkpoint after = replayRecorder.checkpoint("after_decision");
        replayRecorder.recordAcceptedDecision(pending, response, before, after);
        return pendingDecisionPayload();
    }

    JsonObject qualificationStatePayload() {
        ensureStarted();
        JsonObject payload = new JsonObject();
        payload.add("semantic_state", replayRecorder.currentState());
        payload.add("rules_rng_tape", XmageWs26RulesRngTape.snapshot(seed));
        return payload;
    }

    JsonObject resultPayload() {
        ensureStarted();
        JsonObject payload = statusPayload();
        payload.addProperty("scenario_id", appliedScenario.scenarioId());
        payload.addProperty("scenario_sha256", appliedScenario.scenarioSha256());
        payload.add("scenario_validation", appliedScenario.validation().deepCopy());
        payload.add("replay", replayRecorder.evidence(seed));
        payload.add("durable_transcript", XmageAuditSurfaceRedactor.redactTranscript(controller.transcript()));
        payload.addProperty("rules_authority", "xmage");
        payload.addProperty("decision_policy_authority", "commander_lab_external_pilot");
        payload.addProperty("evidence_class", EVIDENCE_CLASS);
        payload.addProperty("candidate_patch_required", true);
        payload.addProperty("bit_exact_replay_claimed", false);
        return payload;
    }

    private JsonObject statusPayload() {
        failIfEngineFailed();
        JsonObject payload = new JsonObject();
        payload.addProperty("lane", LANE);
        payload.addProperty("game_id", protocolGameId);
        payload.addProperty("player_count", players.size());
        payload.addProperty("started", started);
        payload.addProperty("terminal", isEngineTerminal());
        payload.addProperty("turn", game.getState().getTurnNum());
        payload.addProperty("active_player_seat", seatOneBased(game.getActivePlayerId()));
        payload.addProperty("priority_player_seat", seatOneBased(game.getPriorityPlayerId()));
        payload.addProperty("phase", game.getTurnPhaseType() == null ? "unknown" : game.getTurnPhaseType().name().toLowerCase());
        payload.addProperty("step", game.getTurnStepType() == null ? "unknown" : game.getTurnStepType().name().toLowerCase());
        payload.addProperty("engine_error_count", game.getTotalErrorsCount());
        if (game.getTotalErrorsCount() > 0 || !engineErrorDiagnostics.isEmpty()) {
            throw new IllegalStateException("XMAGE_RULES_ENGINE_ERROR: " + String.join(" | ", engineErrorDiagnostics));
        }
        return payload;
    }

    private int seatOneBased(java.util.UUID playerId) {
        if (playerId == null) return -1;
        int zero = knowledgeLedger.seat(playerId);
        return zero < 0 ? -1 : zero + 1;
    }

    private void runEngine(java.util.UUID startingPlayerId) {
        try {
            if (XmageWs26Scenario.NATIVE_STATE_LOAD.equals(executionEntryMode)) {
                game.initializeForNativeStateLoad(startingPlayerId);
                appliedScenario = XmageWs26Scenario.apply(
                        configuredScenario, game, players, decks, knowledgeLedger, seed, startingPlayerSeat
                );
                JsonObject temporal = XmageWs26Scenario.applyTemporalState(configuredScenario, game, players);
                appliedScenario.validation().add("temporal_state", temporal);
                replayRecorder = new XmageWs26ReplayRecorder(
                        game, players, knowledgeLedger, appliedScenario.semanticObjectIds()
                );
                replayRecorder.checkpoint("after_native_setup_validation");
                int prioritySeat = XmageWs26Scenario.requestedPrioritySeat(configuredScenario, players.size());
                game.resumeNativePriority(players.get(prioritySeat - 1).getId());
            } else {
                game.start(startingPlayerId);
            }
        } catch (Throwable throwable) {
            engineFailure.compareAndSet(null, throwable);
            controller.failClosed("XMAGE_FULL_GAME_ENGINE_FAILURE", safeMessage(throwable));
        } finally {
            controller.markTerminal();
        }
    }

    private void awaitDecisionAdvance(String submittedDecisionId, Duration timeout) {
        long deadline = System.nanoTime() + timeout.toNanos();
        while (true) {
            failIfEngineFailed();
            if (controller.terminalFailure() != null || isEngineTerminal()) return;
            JsonObject pending = controller.pendingDecision();
            if (pending == null) {
                controller.awaitPendingOrTerminal(Duration.ofMillis(25));
            } else if (!submittedDecisionId.equals(pending.get("decision_id").getAsString())) {
                return;
            }
            if (System.nanoTime() >= deadline) throw new IllegalStateException("DECISION_ADVANCE_TIMEOUT");
            try {
                Thread.sleep(2L);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("DECISION_ADVANCE_INTERRUPTED", exc);
            }
        }
    }

    private boolean isEngineTerminal() {
        return controller.terminalFailure() != null
                || (engineThread != null && !engineThread.isAlive() && controller.pendingDecision() == null);
    }

    private void ensureStarted() {
        if (!started) throw new IllegalStateException("FULL_GAME_NOT_STARTED");
        failIfEngineFailed();
    }

    private void failIfEngineFailed() {
        Throwable failure = engineFailure.get();
        if (failure != null) {
            throw new IllegalStateException("XMAGE_FULL_GAME_ENGINE_FAILURE: " + safeMessage(failure), failure);
        }
    }

    private static String safeMessage(Throwable throwable) {
        String message = throwable == null ? null : throwable.getMessage();
        return throwable == null ? "unknown" : throwable.getClass().getSimpleName()
                + (message == null || message.isBlank() ? "" : ": " + message);
    }
}

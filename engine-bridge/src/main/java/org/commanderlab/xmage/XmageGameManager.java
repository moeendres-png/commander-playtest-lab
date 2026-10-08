package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.MageItem;
import mage.cards.decks.Deck;
import mage.constants.CommanderCardType;
import mage.constants.ManaType;
import mage.constants.PhaseStep;
import mage.constants.RangeOfInfluence;
import mage.constants.TurnPhase;
import mage.counters.CounterType;
import mage.game.GameCommanderImpl;
import mage.game.Game;
import mage.game.GameOptions;
import mage.game.mulligan.MulliganType;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;
import mage.util.ThreadUtils;
import mage.util.XmageThreadFactory;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

final class XmageGameManager {

    record CreateResult(
            String gameHandle,
            String gameId,
            String engineGameId,
            int playerCount,
            int startingPlayerSeat,
            boolean externalControl,
            JsonObject rulesSeedBinding
    ) {

        /** Engine-readback Rules seed, or null when the game is uncontrolled. */
        Long rulesSeed() {
            return rulesSeedBinding == null
                    ? null
                    : rulesSeedBinding.get("rules_seed").getAsLong();
        }
    }

    record StartResult(
            String gameHandle,
            String gameId,
            String engineGameId,
            int playerCount,
            String startingPlayerId,
            String startingPlayerChooserId,
            String startingPlayerChosenId,
            int turnNumber,
            boolean paused,
            boolean externalControl,
            JsonObject rulesSeedBinding
    ) {
    }

    record StateSnapshot(
            String gameId,
            String engineGameId,
            long stateObservationOffset,
            String observerPlayerId,
            String observerEnginePlayerId,
            int observerSeat,
            JsonObject state
    ) {
    }

    private record ObserverResolution(
            String requestedId,
            Player player,
            int seat
    ) {
    }

    record LegalActionsSnapshot(
            String gameId,
            String engineGameId,
            long decisionOffset,
            String decisionId,
            String actorId,
            String decisionKind,
            JsonObject context,
            boolean complete,
            List<JsonObject> actions
    ) {
    }

    record EventLogSnapshot(
            String gameId,
            String engineGameId,
            long latestEventOffset,
            int totalEvents,
            JsonObject log
    ) {
    }

    record ShutdownResult(
            String gameId,
            String engineGameId,
            long finalEventOffset,
            int releasedDeckHandleCount,
            int storedGameCount,
            JsonObject finalLog
    ) {
    }

    static final class GameException extends RuntimeException {

        GameException(String message) {
            super(message);
        }

        GameException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    private enum Lifecycle {
        CREATED,
        STARTED,
        FAILED
    }

    private static final class ManagedGame {

        private final String gameId;
        private final GameCommanderImpl game;
        private final List<Player> players;
        private final List<String> deckHandles;
        private final int startingPlayerSeat;
        private final int startingLife;
        private final boolean externalControl;
        private final ExternalDecisionController externalDecisionController;
        private final XmageStartingPlayerPrompt startingPlayerPrompt;
        private final XmageAuditEventLog eventLog;
        /* Explicit orchestration seed bound to the native Rules RNG, or null. */
        private final Long explicitRulesSeed;

        private volatile Thread engineThread;
        private volatile Throwable engineFailure;
        private Lifecycle lifecycle = Lifecycle.CREATED;
        private long stateObservationOffset = 0L;

        private ManagedGame(
                String gameId,
                GameCommanderImpl game,
                List<Player> players,
                List<String> deckHandles,
                int startingPlayerSeat,
                int startingLife,
                boolean externalControl,
                ExternalDecisionController externalDecisionController,
                XmageStartingPlayerPrompt startingPlayerPrompt,
                Long explicitRulesSeed
        ) {
            this.gameId = gameId;
            this.game = game;
            this.players = players;
            this.deckHandles = deckHandles;
            this.startingPlayerSeat = startingPlayerSeat;
            this.startingLife = startingLife;
            this.externalControl = externalControl;
            this.externalDecisionController = externalDecisionController;
            this.startingPlayerPrompt = startingPlayerPrompt;
            this.explicitRulesSeed = explicitRulesSeed;
            this.eventLog = new XmageAuditEventLog(gameId, game.getId().toString());
        }
    }

    private final XmageDeckImporter deckImporter;
    private final Map<String, ManagedGame> gamesByHandle = new ConcurrentHashMap<>();

    /*
     * XMage Deck contains mutable concrete Card objects.
     * One imported deck handle therefore belongs to at most one live game.
     * B4-D releases those claims only after explicit per-game shutdown/cleanup.
     */
    private final Set<String> claimedDeckHandles = ConcurrentHashMap.newKeySet();

    XmageGameManager(XmageDeckImporter deckImporter) {
        if (deckImporter == null) {
            throw new IllegalArgumentException("deckImporter must not be null");
        }
        this.deckImporter = deckImporter;
    }

    CreateResult createCommanderGame(
            String gameId,
            List<String> requestedDeckHandles,
            int startingPlayerSeat,
            int startingLife
    ) {
        return createCommanderGame(
                gameId,
                requestedDeckHandles,
                startingPlayerSeat,
                startingLife,
                false
        );
    }

    CreateResult createCommanderGame(
            String gameId,
            List<String> requestedDeckHandles,
            int startingPlayerSeat,
            int startingLife,
            boolean externalControl
    ) {
        return createCommanderGame(
                gameId,
                requestedDeckHandles,
                startingPlayerSeat,
                startingLife,
                externalControl,
                null
        );
    }

    /**
     * Creates a Commander game. When {@code rulesSeed} is non-null it is bound
     * to the engine's authoritative per-game Rules RNG before start (see
     * {@link XmageRulesSeedBinding}); otherwise the game runs on the engine's
     * non-credited default seed and is reported as uncontrolled.
     */
    CreateResult createCommanderGame(
            String gameId,
            List<String> requestedDeckHandles,
            int startingPlayerSeat,
            int startingLife,
            boolean externalControl,
            Long rulesSeed
    ) {
        String validatedGameId = requireText(gameId, "game_id");

        if (requestedDeckHandles == null) {
            throw new GameException("INVALID_GAME: deck_handles must not be null");
        }

        List<String> deckHandles = new ArrayList<>(requestedDeckHandles);

        if (deckHandles.size() < 2 || deckHandles.size() > 6) {
            throw new GameException(
                    "INVALID_PLAYER_COUNT: expected 2 to 6 players; observed "
                            + deckHandles.size()
            );
        }

        if (startingPlayerSeat < 0 || startingPlayerSeat >= deckHandles.size()) {
            throw new GameException(
                    "INVALID_STARTING_PLAYER_SEAT: " + startingPlayerSeat
            );
        }

        if (startingLife < 1) {
            throw new GameException("INVALID_STARTING_LIFE: " + startingLife);
        }

        Set<String> distinct = new HashSet<>();
        for (int index = 0; index < deckHandles.size(); index++) {
            String handle = requireText(
                    deckHandles.get(index),
                    "deck_handles[" + index + "]"
            );
            deckHandles.set(index, handle);
            if (!distinct.add(handle)) {
                throw new GameException("DUPLICATE_DECK_HANDLE: " + handle);
            }
        }

        List<Deck> decks = new ArrayList<>(deckHandles.size());
        try {
            for (String handle : deckHandles) {
                decks.add(deckImporter.requireDeck(handle));
            }
        } catch (XmageDeckImporter.ImportException exc) {
            throw new GameException(
                    "DECK_HANDLE_RESOLUTION_FAILED: " + exc.getMessage(),
                    exc
            );
        }

        synchronized (claimedDeckHandles) {
            for (String handle : deckHandles) {
                if (claimedDeckHandles.contains(handle)) {
                    throw new GameException("DECK_HANDLE_ALREADY_IN_USE: " + handle);
                }
            }
            claimedDeckHandles.addAll(deckHandles);
        }

        boolean createdSuccessfully = false;

        try {
            // Two-player tables use the engine's own two-player Commander type
            // so the engine applies CR 103.8a (see XmageCommanderGames).
            // The first mulligan in a multiplayer game is free (CR 103.5c;
            // multiplayer = more than two players, CR 102.1), exactly as the
            // full-game session configures it: a London mulligan with no free
            // mulligan here made a 3..6P player who mulliganed once bottom a
            // card the rules do not require.
            int freeMulligans = deckHandles.size() > 2 ? 1 : 0;
            GameCommanderImpl game = XmageCommanderGames.create(
                    deckHandles.size(),
                    MulliganType.LONDON.getMulligan(freeMulligans),
                    startingLife
            );
            if (rulesSeed != null) {
                try {
                    XmageRulesSeedBinding.bind(game, rulesSeed);
                } catch (IllegalStateException exc) {
                    throw new GameException(exc.getMessage(), exc);
                }
            }
            GameOptions options = new GameOptions();
            options.rollbackTurnsAllowed = false;
            game.setGameOptions(options);

            ExternalDecisionController decisionController = externalControl
                    ? new ExternalDecisionController()
                    : null;
            /*
             * Shared per game: the players record the CR 103.2 prompt each
             * actually answered, and startGame publishes those identities so a
             * readback can never be mistaken for an answer (#572).
             */
            XmageStartingPlayerPrompt startingPlayerPrompt = new XmageStartingPlayerPrompt();

            List<Player> players = new ArrayList<>(decks.size());
            for (int index = 0; index < decks.size(); index++) {
                Deck deck = decks.get(index);
                XmageBridgePlayer player = new XmageBridgePlayer(
                        "Bridge Seat " + (index + 1),
                        RangeOfInfluence.ALL,
                        decisionController,
                        startingPlayerPrompt
                );

                player.init(game);
                game.loadCards(deck.getCards(), player.getId());
                game.loadCards(deck.getSideboard(), player.getId());
                players.add(player);
            }
            // F-41: seat order is turn order (see XmageSeating).
            List<Player> seated = XmageSeating.additionOrder(players);
            List<Deck> seatedDecks = XmageSeating.additionOrder(decks);
            for (int index = 0; index < seated.size(); index++) {
                game.addPlayer(seated.get(index), seatedDecks.get(index));
            }

            if (game.getPlayers().size() != deckHandles.size()) {
                throw new GameException(
                        "XMAGE_PLAYER_SETUP_FAILED: expected "
                                + deckHandles.size()
                                + " players but observed "
                                + game.getPlayers().size()
                );
            }

            ManagedGame managed = new ManagedGame(
                    validatedGameId,
                    game,
                    List.copyOf(players),
                    List.copyOf(deckHandles),
                    startingPlayerSeat,
                    startingLife,
                    externalControl,
                    decisionController,
                    startingPlayerPrompt,
                    rulesSeed
            );

            String gameHandle;
            do {
                gameHandle = "xmage-game-" + UUID.randomUUID();
            } while (gamesByHandle.putIfAbsent(gameHandle, managed) != null);

            JsonObject createdPayload = new JsonObject();
            createdPayload.addProperty("player_count", game.getPlayers().size());
            createdPayload.addProperty("starting_player_seat", startingPlayerSeat);
            createdPayload.addProperty("external_control", externalControl);
            createdPayload.addProperty("seed_controlled", rulesSeed != null);
            managed.eventLog.record(
                    "game_created",
                    null,
                    null,
                    null,
                    null,
                    null,
                    createdPayload
            );

            createdSuccessfully = true;

            return new CreateResult(
                    gameHandle,
                    validatedGameId,
                    game.getId().toString(),
                    game.getPlayers().size(),
                    startingPlayerSeat,
                    externalControl,
                    rulesSeedBinding(managed)
            );
        } finally {
            if (!createdSuccessfully) {
                synchronized (claimedDeckHandles) {
                    claimedDeckHandles.removeAll(deckHandles);
                }
            }
        }
    }

    StartResult startGame(String gameHandle) {
        ManagedGame managed = requireManagedGame(gameHandle);

        synchronized (managed) {
            if (managed.lifecycle == Lifecycle.STARTED) {
                throw new GameException(
                        "GAME_ALREADY_STARTED: " + requireText(gameHandle, "game_handle")
                );
            }
            if (managed.lifecycle == Lifecycle.FAILED) {
                throw new GameException(
                        "GAME_START_PREVIOUSLY_FAILED: "
                                + requireText(gameHandle, "game_handle")
                );
            }

            Player choosingPlayer = managed.players.get(managed.startingPlayerSeat);

            if (managed.externalControl) {
                if (managed.externalDecisionController == null) {
                    managed.lifecycle = Lifecycle.FAILED;
                    throw new GameException(
                            "XMAGE_EXTERNAL_CONTROL_START_FAILED: controller is unavailable"
                    );
                }

                /*
                 * Mulligan is a synchronous Player callback inside game.start().
                 * Running the engine on this dedicated thread lets the callback
                 * block in ExternalDecisionController while the JSONL thread
                 * returns the authoritative decision domain to the pilot.
                 */
                managed.lifecycle = Lifecycle.STARTED;
                XmageThreadFactory gameThreadFactory = new XmageThreadFactory(
                        ThreadUtils.THREAD_PREFIX_GAME + " generic-external " + managed.gameId,
                        true
                );
                managed.engineThread = gameThreadFactory.newThread(
                        () -> runExternalStart(managed, choosingPlayer.getId())
                );
                managed.engineThread.start();

                ExternalDecisionController.Decision decision;
                try {
                    decision = managed.externalDecisionController.awaitCurrentDecision(
                            managed.game.getId().toString(),
                            Duration.ofSeconds(20)
                    );
                } catch (RuntimeException exc) {
                    managed.lifecycle = Lifecycle.FAILED;
                    throw new GameException(
                            "XMAGE_EXTERNAL_CONTROL_START_FAILED: " + exc.getMessage(),
                            exc
                    );
                }

                if (managed.engineFailure != null) {
                    managed.lifecycle = Lifecycle.FAILED;
                    throw new GameException(
                            "XMAGE_GAME_START_FAILED: " + managed.engineFailure.getMessage(),
                            managed.engineFailure
                    );
                }
                if (managed.game.getStartingPlayerId() == null) {
                    managed.lifecycle = Lifecycle.FAILED;
                    throw new GameException(
                            "XMAGE_GAME_START_FAILED: starting player was not established"
                    );
                }
                for (Player player : managed.game.getPlayers().values()) {
                    if (player.getLife() != managed.startingLife) {
                        managed.lifecycle = Lifecycle.FAILED;
                        throw new GameException(
                                "XMAGE_GAME_START_FAILED: "
                                        + player.getName()
                                        + " has unexpected life "
                                        + player.getLife()
                        );
                    }
                }

                JsonObject startedPayload = new JsonObject();
                startedPayload.addProperty(
                        "starting_player_id",
                        managed.game.getStartingPlayerId().toString()
                );
                addStartingPlayerPrompt(startedPayload, managed.startingPlayerPrompt);
                startedPayload.addProperty("turn_number", managed.game.getState().getTurnNum());
                startedPayload.addProperty("external_control", true);
                startedPayload.addProperty("seed_controlled", managed.explicitRulesSeed != null);
                startedPayload.addProperty("initial_decision_kind", decision.decisionKind());
                /*
                 * At the first mulligan callback XMage has chosen the starting
                 * player but has not yet established a turn phase/step. A
                 * full semantic state hash is therefore not defined yet.
                 * Recording null here is honest; the first post-mulligan
                 * action event carries the first complete state hash.
                 */
                managed.eventLog.record(
                        "game_started",
                        managed.game.getStartingPlayerId().toString(),
                        decision.decisionId(),
                        null,
                        null,
                        null,
                        startedPayload
                );

                return new StartResult(
                        requireText(gameHandle, "game_handle"),
                        managed.gameId,
                        managed.game.getId().toString(),
                        managed.game.getPlayers().size(),
                        managed.game.getStartingPlayerId().toString(),
                        managed.startingPlayerPrompt.chooserId(),
                        managed.startingPlayerPrompt.chosenId(),
                        managed.game.getState().getTurnNum(),
                        managed.game.isPaused(),
                        true,
                        rulesSeedBinding(managed)
                );
            }

            /* Validated B3 bounded lifecycle path. */
            GameOptions options = managed.game.getOptions();
            options.stopOnTurn = 1;
            options.stopAtStep = PhaseStep.UPKEEP;

            try {
                managed.game.getState().addWatcher(new XmageLibraryShuffleWatcher());
                managed.game.start(choosingPlayer.getId());
            } catch (RuntimeException | Error exc) {
                managed.lifecycle = Lifecycle.FAILED;
                if (exc instanceof GameException gameException) {
                    throw gameException;
                }
                throw new GameException(
                        "XMAGE_GAME_START_FAILED: " + exc.getMessage(),
                        exc
                );
            }

            if (managed.game.getTotalErrorsCount() != 0) {
                managed.lifecycle = Lifecycle.FAILED;
                throw new GameException(
                        "XMAGE_GAME_START_FAILED: XMage reported "
                                + managed.game.getTotalErrorsCount()
                                + " internal engine error(s)"
                );
            }
            if (managed.game.getStartingPlayerId() == null) {
                managed.lifecycle = Lifecycle.FAILED;
                throw new GameException(
                        "XMAGE_GAME_START_FAILED: starting player was not established"
                );
            }
            if (!managed.game.isPaused()) {
                managed.lifecycle = Lifecycle.FAILED;
                throw new GameException(
                        "XMAGE_GAME_START_FAILED: game did not pause at the requested handoff boundary"
                );
            }
            if (managed.game.getState().getTurnNum() != 1) {
                managed.lifecycle = Lifecycle.FAILED;
                throw new GameException(
                        "XMAGE_GAME_START_FAILED: unexpected turn number "
                                + managed.game.getState().getTurnNum()
                );
            }

            for (Player player : managed.game.getPlayers().values()) {
                if (player.getLife() != managed.startingLife) {
                    managed.lifecycle = Lifecycle.FAILED;
                    throw new GameException(
                            "XMAGE_GAME_START_FAILED: "
                                    + player.getName()
                                    + " has unexpected life "
                                    + player.getLife()
                    );
                }
                if (player.getHand().size() != 7) {
                    managed.lifecycle = Lifecycle.FAILED;
                    throw new GameException(
                            "XMAGE_GAME_START_FAILED: "
                                    + player.getName()
                                    + " has unexpected opening hand size "
                                    + player.getHand().size()
                    );
                }
            }

            managed.lifecycle = Lifecycle.STARTED;
            JsonObject startedPayload = new JsonObject();
            startedPayload.addProperty(
                    "starting_player_id",
                    managed.game.getStartingPlayerId().toString()
            );
            addStartingPlayerPrompt(startedPayload, managed.startingPlayerPrompt);
            startedPayload.addProperty("turn_number", managed.game.getState().getTurnNum());
            startedPayload.addProperty("external_control", false);
            startedPayload.addProperty("seed_controlled", managed.explicitRulesSeed != null);
            managed.eventLog.record(
                    "game_started",
                    managed.game.getStartingPlayerId().toString(),
                    null,
                    null,
                    null,
                    stateHash(managed),
                    startedPayload
            );

            return new StartResult(
                    requireText(gameHandle, "game_handle"),
                    managed.gameId,
                    managed.game.getId().toString(),
                    managed.game.getPlayers().size(),
                    managed.game.getStartingPlayerId().toString(),
                    managed.startingPlayerPrompt.chooserId(),
                    managed.startingPlayerPrompt.chosenId(),
                    managed.game.getState().getTurnNum(),
                    managed.game.isPaused(),
                    false,
                    rulesSeedBinding(managed)
            );
        }
    }

    /**
     * Adds the identities of the CR 103.2 prompt the bridge actually answered,
     * when it answered one. Absent means no prompt answer was recorded: the
     * established {@code starting_player_id} readback alone cannot distinguish
     * a real answer from GameImpl.init's first-player fallback in a pod of 3+
     * (#572).
     */
    private static void addStartingPlayerPrompt(
            JsonObject payload,
            XmageStartingPlayerPrompt prompt
    ) {
        String chooserId = prompt.chooserId();
        String chosenId = prompt.chosenId();
        if (chooserId == null || chosenId == null) {
            return;
        }
        payload.addProperty("starting_player_chooser_id", chooserId);
        payload.addProperty("starting_player_chosen_id", chosenId);
    }

    private static void runExternalStart(ManagedGame managed, UUID startingPlayerId) {
        try {
            managed.game.getState().addWatcher(new XmageLibraryShuffleWatcher());
            managed.game.start(startingPlayerId);
            if (managed.game.getTotalErrorsCount() != 0) {
                throw new IllegalStateException(
                        "XMAGE_INTERNAL_ERRORS: " + managed.game.getTotalErrorsCount()
                );
            }
        } catch (Throwable exc) {
            managed.engineFailure = exc;
            if (managed.externalDecisionController != null) {
                managed.externalDecisionController.failClosed(
                        "XMAGE_EXTERNAL_ENGINE_FAILED: "
                                + exc.getClass().getSimpleName()
                                + ": "
                                + String.valueOf(exc.getMessage()),
                        exc
                );
            }
        } finally {
            /*
             * A normal priority handoff returns from game.start() because
             * XmageBridgePlayer.priority() paused the game. That is not terminal:
             * subsequent priority passes resume XMage synchronously on the JSONL
             * control thread. Only a non-paused return is terminal here.
             */
            if (!managed.game.isPaused() && managed.externalDecisionController != null) {
                managed.externalDecisionController.markTerminal();
            }
        }
    }

    /**
     * Whether this game's Rules RNG is bound to an explicit orchestration seed
     * and the engine readback still confirms it. Carries no seed value, so it
     * is safe to report next to a principal-scoped observation.
     */
    boolean seedControlled(String gameHandle) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            return managed.explicitRulesSeed != null
                    && XmageRulesSeedBinding.holds(managed.game, managed.explicitRulesSeed);
        }
    }

    /** Orchestration-scoped seed binding proof, or null for uncontrolled games. */
    private static JsonObject rulesSeedBinding(ManagedGame managed) {
        if (managed.explicitRulesSeed == null) {
            return null;
        }
        return XmageRulesSeedBinding.payload(managed.game, managed.explicitRulesSeed);
    }

    LegalActionsSnapshot legalActions(String gameHandle) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            if (managed.lifecycle != Lifecycle.STARTED) {
                throw new GameException("LEGAL_ACTIONS_UNAVAILABLE: game must be started");
            }
            if (!managed.externalControl || managed.externalDecisionController == null) {
                throw new GameException(
                        "LEGAL_ACTIONS_UNAVAILABLE: game was not created with external_control=true"
                );
            }
            try {
                ExternalDecisionController.Decision decision =
                        managed.externalDecisionController.requireCurrentDecision(
                                managed.game.getId().toString()
                        );
                if ("priority".equals(decision.decisionKind()) && !managed.game.isPaused()) {
                    throw new GameException(
                            "LEGAL_ACTIONS_UNAVAILABLE: priority decision exists while game is not paused"
                    );
                }
                return new LegalActionsSnapshot(
                        managed.gameId,
                        managed.game.getId().toString(),
                        decision.decisionOffset(),
                        decision.decisionId(),
                        decision.actorId(),
                        decision.decisionKind(),
                        decision.context() == null
                                ? new JsonObject()
                                : decision.context().deepCopy(),
                        decision.complete(),
                        decision.actions()
                );
            } catch (IllegalStateException exc) {
                throw new GameException(
                        "LEGAL_ACTIONS_UNAVAILABLE: " + exc.getMessage(),
                        exc
                );
            }
        }
    }

    XmageActionExecutor.ExecutionResult resolveMulligan(
            String gameHandle,
            String decisionId,
            String actorId,
            boolean keep,
            List<String> bottomCardIds
    ) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            if (managed.lifecycle != Lifecycle.STARTED) {
                throw new GameException("MULLIGAN_UNAVAILABLE: game must be started");
            }
            if (!managed.externalControl || managed.externalDecisionController == null) {
                throw new GameException(
                        "MULLIGAN_UNAVAILABLE: game was not created with external_control=true"
                );
            }

            ExternalDecisionController.Decision before;
            String selectedActionId;
            try {
                before = managed.externalDecisionController.requireCurrentDecision(
                        managed.game.getId().toString()
                );
                selectedActionId = managed.externalDecisionController.submitMulligan(
                        managed.game.getId().toString(),
                        decisionId,
                        actorId,
                        keep,
                        bottomCardIds
                );
                managed.externalDecisionController.awaitDecisionAdvance(
                        managed.game.getId().toString(),
                        before.decisionId(),
                        Duration.ofSeconds(20)
                );
            } catch (RuntimeException exc) {
                throw new GameException(
                        "MULLIGAN_RESOLUTION_FAILED: " + exc.getMessage(),
                        exc
                );
            }
            awaitPriorityPause(managed, Duration.ofSeconds(20));

            if (managed.engineFailure != null) {
                throw new GameException(
                        "MULLIGAN_RESOLUTION_FAILED: "
                                + managed.engineFailure.getClass().getSimpleName()
                                + ": "
                                + String.valueOf(managed.engineFailure.getMessage()),
                        managed.engineFailure
                );
            }

            return new XmageActionExecutor.ExecutionResult(
                    before.decisionId(),
                    selectedActionId,
                    "mulligan",
                    before.actorId(),
                    null,
                    keep ? "keep" : "mulligan"
            );
        }
    }

    /**
     * Resolve the pending London bottom-card decision (CR 103.5) from an
     * explicit external card-id selection. The controller validates the
     * decision id, actor, exact distinct offered-count selection and offered
     * membership before waking the engine thread; nothing is picked here.
     */
    XmageActionExecutor.ExecutionResult resolveBottom(
            String gameHandle,
            String decisionId,
            String actorId,
            List<String> cardIds
    ) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            if (managed.lifecycle != Lifecycle.STARTED) {
                throw new GameException("BOTTOM_SELECTION_UNAVAILABLE: game must be started");
            }
            if (!managed.externalControl || managed.externalDecisionController == null) {
                throw new GameException(
                        "BOTTOM_SELECTION_UNAVAILABLE: game was not created with external_control=true"
                );
            }

            ExternalDecisionController.Decision before;
            try {
                before = managed.externalDecisionController.requireCurrentDecision(
                        managed.game.getId().toString()
                );
                managed.externalDecisionController.submitBottom(
                        managed.game.getId().toString(),
                        decisionId,
                        actorId,
                        cardIds
                );
                managed.externalDecisionController.awaitDecisionAdvance(
                        managed.game.getId().toString(),
                        before.decisionId(),
                        Duration.ofSeconds(20)
                );
            } catch (RuntimeException exc) {
                throw new GameException(
                        "BOTTOM_SELECTION_RESOLUTION_FAILED: " + exc.getMessage(),
                        exc
                );
            }
            awaitPriorityPause(managed, Duration.ofSeconds(20));

            if (managed.engineFailure != null) {
                throw new GameException(
                        "BOTTOM_SELECTION_RESOLUTION_FAILED: "
                                + managed.engineFailure.getClass().getSimpleName()
                                + ": "
                                + String.valueOf(managed.engineFailure.getMessage()),
                        managed.engineFailure
                );
            }

            /*
             * The resolution is a card-id set, not one engine action. The
             * engine decision id is reported as the executed action id so the
             * audit event names the resolved decision without republishing the
             * actor's own card identities.
             */
            return new XmageActionExecutor.ExecutionResult(
                    before.decisionId(),
                    before.decisionId(),
                    "london_bottom",
                    before.actorId(),
                    null,
                    null
            );
        }
    }

    /**
     * The last mulligan keep resumes XMage on the engine thread, and
     * XmageBridgePlayer.priority() publishes the priority decision before it
     * pauses the game. Return only once that handoff is complete, so the
     * caller never observes a published priority decision on a running game.
     * A handoff that does not complete fails closed.
     */
    private static void awaitPriorityPause(ManagedGame managed, Duration timeout) {
        long deadline = System.nanoTime() + timeout.toNanos();
        while (true) {
            if (managed.engineFailure != null || managed.game.isPaused()) {
                return;
            }
            ExternalDecisionController.Decision current;
            try {
                current = managed.externalDecisionController.requireCurrentDecision(
                        managed.game.getId().toString()
                );
            } catch (RuntimeException exc) {
                return;
            }
            if (!"priority".equals(current.decisionKind())) {
                return;
            }
            if (System.nanoTime() > deadline) {
                throw new GameException(
                        "MULLIGAN_RESOLUTION_FAILED: priority decision published but the game did not pause"
                );
            }
            try {
                Thread.sleep(2);
            } catch (InterruptedException exc) {
                Thread.currentThread().interrupt();
                throw new GameException("MULLIGAN_RESOLUTION_FAILED: interrupted awaiting priority pause", exc);
            }
        }
    }

    StateSnapshot snapshotState(String gameHandle, String observerPlayerId) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            if (managed.lifecycle != Lifecycle.STARTED) {
                throw new GameException("GAME_STATE_UNAVAILABLE: game must be started");
            }
            ObserverResolution observer = resolveObserver(managed, observerPlayerId);
            managed.stateObservationOffset++;
            return new StateSnapshot(
                    managed.gameId,
                    managed.game.getId().toString(),
                    managed.stateObservationOffset,
                    observer.requestedId(),
                    observer.player().getId().toString(),
                    observer.seat(),
                    buildPrincipalState(managed, observer.player())
            );
        }
    }

    String stateHash(String gameHandle) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            if (managed.lifecycle != Lifecycle.STARTED) {
                throw new GameException("GAME_STATE_UNAVAILABLE: game must be started");
            }
            return stateHash(managed);
        }
    }

    /**
     * Transitional audit hash for engine callbacks that legally occur before
     * XMage has established a turn phase (notably London mulligan).
     *
     * <p>Null means "no complete semantic state exists yet", not "hashing
     * failed". Any other state-hash failure remains fatal. Normal priority and
     * action submission continue to use {@link #stateHash(String)} and therefore
     * require a complete Rules state.</p>
     */
    String stateHashIfAvailable(String gameHandle) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            if (managed.lifecycle != Lifecycle.STARTED) {
                throw new GameException("GAME_STATE_UNAVAILABLE: game must be started");
            }
            if (managed.game.getTurnPhaseType() == null) {
                return null;
            }
            return stateHash(managed);
        }
    }

    void recordExternalAction(
            String gameHandle,
            XmageActionExecutor.ExecutionResult executed,
            String preStateHash,
            String postStateHash
    ) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            if (managed.lifecycle != Lifecycle.STARTED) {
                throw new GameException("EVENT_LOG_UNAVAILABLE: game must be started");
            }
            JsonObject payload = new JsonObject();
            payload.addProperty("action_type", executed.actionType());
            if (executed.sourceObjectId() == null) {
                payload.add("source_object_id", JsonNull.INSTANCE);
            } else {
                payload.addProperty("source_object_id", executed.sourceObjectId());
            }
            if (executed.sourceName() == null) {
                payload.add("source_name", JsonNull.INSTANCE);
            } else {
                payload.addProperty("source_name", executed.sourceName());
            }
            payload.addProperty("bounded_submission", true);
            String eventType = "pass_priority".equals(executed.actionType())
                    ? "priority_passed"
                    : "action_submitted";
            managed.eventLog.record(
                    eventType,
                    executed.actorId(),
                    executed.decisionId(),
                    executed.actionId(),
                    preStateHash,
                    postStateHash,
                    payload
            );
        }
    }

    EventLogSnapshot exportEventLog(String gameHandle, long afterOffset) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            JsonObject log;
            try {
                log = managed.eventLog.exportLog(afterOffset);
            } catch (IllegalArgumentException exc) {
                throw new GameException("INVALID_EVENT_OFFSET: " + exc.getMessage(), exc);
            }
            return new EventLogSnapshot(
                    managed.gameId,
                    managed.game.getId().toString(),
                    managed.eventLog.latestOffset(),
                    log.getAsJsonArray("events").size(),
                    log
            );
        }
    }

    long latestEventOffset(String gameHandle) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            return managed.eventLog.latestOffset();
        }
    }

    ShutdownResult shutdownGame(String gameHandle) {
        String validatedHandle = requireText(gameHandle, "game_handle");
        ManagedGame managed = requireManagedGame(validatedHandle);

        synchronized (managed) {
            String preStateHash = null;
            if (managed.lifecycle == Lifecycle.STARTED
                    && managed.game.getTurnPhaseType() != null) {
                preStateHash = stateHash(managed);
            }

            JsonObject payload = new JsonObject();
            payload.addProperty("lifecycle_before_shutdown", managed.lifecycle.name().toLowerCase());
            payload.addProperty("game_had_ended", managed.game.hasEnded());
            managed.eventLog.record(
                    "game_shutdown",
                    null,
                    null,
                    null,
                    preStateHash,
                    null,
                    payload
            );

            JsonObject finalLog = managed.eventLog.exportLog(0L);
            long finalOffset = managed.eventLog.latestOffset();
            RuntimeException cleanupFailure = null;
            try {
                if (managed.lifecycle == Lifecycle.STARTED && !managed.game.hasEnded()) {
                    managed.game.end();
                }
                managed.game.cleanUp();
            } catch (RuntimeException exc) {
                cleanupFailure = exc;
            } finally {
                gamesByHandle.remove(validatedHandle, managed);
                synchronized (claimedDeckHandles) {
                    claimedDeckHandles.removeAll(managed.deckHandles);
                }
            }

            if (cleanupFailure != null) {
                throw new GameException(
                        "XMAGE_GAME_SHUTDOWN_FAILED: " + cleanupFailure.getMessage(),
                        cleanupFailure
                );
            }

            return new ShutdownResult(
                    managed.gameId,
                    managed.game.getId().toString(),
                    finalOffset,
                    managed.deckHandles.size(),
                    gamesByHandle.size(),
                    finalLog
            );
        }
    }

    Game requireGame(String gameHandle) {
        return requireManagedGame(gameHandle).game;
    }

    int storedGameCount() {
        return gamesByHandle.size();
    }

    /** Schema of {@link #constructedState(String)}. */
    static final String CONSTRUCTED_STATE_SCHEMA = "commander-lab.generic-constructed-state/4";

    /**
     * The engine's normalized constructed state for the generic lane's
     * construction proof (Commander-Lab #441, decision (c)).
     *
     * <p>An orchestration channel, not an observation (the AF09 precedent of
     * {@link XmageRulesRngResultTape}): it exists only on a launch that carries
     * an orchestration key, and is refused on every other launch. Read from the
     * native game objects inside the Rules process. Seats are named by their
     * one-based seat number ({@code P1}..). Public facts are plain: life,
     * poison, loss, zone sizes, and each commander's identity, zone and
     * command-zone cast count. Hidden content never leaves in the clear: each
     * seat's library and hand together (its undrawn main deck plus its hand, a
     * name multiset with no order) leave only as an HMAC under the launch key,
     * so whoever does not hold the key can neither read a card out of it nor
     * test a guess against it. Public zones other than the command zone leave
     * as sizes only.</p>
     */
    JsonObject constructedState(String gameHandle) {
        if (!XmageRulesRngResultTape.enabled()) {
            String problem = XmageRulesRngResultTape.keyProblem();
            throw new GameException("ORCHESTRATION_CHANNEL_NOT_ENABLED: "
                    + (problem == null ? "this launch carries no orchestration key" : problem));
        }
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            Game game = managed.game;
            JsonObject root = new JsonObject();
            root.addProperty("schema", CONSTRUCTED_STATE_SCHEMA);
            root.addProperty("observation_scope", "orchestration_keyed_digests");
            root.addProperty("lifecycle", managed.lifecycle.name().toLowerCase());
            root.addProperty("turn_number", game.getState().getTurnNum());
            TurnPhase phase = game.getTurnPhaseType();
            if (phase == null) {
                root.add("phase", JsonNull.INSTANCE);
            } else {
                root.addProperty("phase", turnPhaseValue(phase));
            }
            root.add("active_player", seatName(managed, game.getActivePlayerId()));
            root.add("priority_player", seatName(managed, game.getPriorityPlayerId()));
            root.addProperty("stack_size", game.getStack().size());
            // Native rules state (schema /4), read from the engine, never inferred
            // by the Lab: the combat in progress, queued extra turns, triggered
            // abilities waiting to be put on the stack, the layered continuous
            // effects in force, and every revealed card.
            JsonObject rulesState = new JsonObject();
            rulesState.addProperty("combat_groups", game.getCombat().getGroups().size());
            rulesState.addProperty("combat_attackers", game.getCombat().getAttackers().size());
            int extraTurns = 0;
            for (mage.game.turn.TurnMod mod : game.getState().getTurnMods()) {
                if (mod.isExtraTurn()) {
                    extraTurns++;
                }
            }
            rulesState.addProperty("extra_turns", extraTurns);
            int pendingTriggers = 0;
            for (Player player : managed.players) {
                pendingTriggers += game.getState().getTriggered(player.getId()).size();
            }
            rulesState.addProperty("pending_triggers", pendingTriggers);
            rulesState.addProperty("continuous_effects",
                    game.getContinuousEffects().getLayeredEffects(game).size());
            int revealed = 0;
            for (mage.cards.Cards cards : game.getState().getRevealed().values()) {
                revealed += cards.size();
            }
            int topRevealed = 0;
            for (Player player : managed.players) {
                if (player.isTopCardRevealed()) {
                    topRevealed++;
                }
            }
            root.add("rules_state", rulesState);
            JsonArray players = new JsonArray();
            for (int seat = 0; seat < managed.players.size(); seat++) {
                Player player = managed.players.get(seat);
                String seatId = "P" + (seat + 1);
                JsonObject entry = new JsonObject();
                entry.addProperty("player_id", seatId);
                entry.addProperty("seat", seat + 1);
                entry.addProperty("life", player.getLife());
                entry.addProperty("poison", player.getCountersCount(CounterType.POISON));
                entry.addProperty("lost", player.hasLost());
                entry.addProperty("left", player.hasLeft());
                entry.addProperty("library_size", player.getLibrary().size());
                entry.addProperty("hand_size", player.getHand().size());
                List<mage.cards.Card> undrawnAndHand = new ArrayList<>(player.getLibrary().getCards(game));
                undrawnAndHand.addAll(player.getHand().getCards(game));
                entry.addProperty("library_and_hand_digest",
                        constructedZoneDigest(seatId, "library_and_hand", undrawnAndHand));
                entry.addProperty("graveyard_size", player.getGraveyard().size());
                entry.addProperty("exile_size", game.getExile().getCardsOwned(game, player.getId()).size());
                int battlefield = 0;
                for (Permanent permanent : game.getBattlefield().getAllPermanents()) {
                    if (player.getId().equals(permanent.getControllerId())) {
                        battlefield++;
                    }
                }
                entry.addProperty("battlefield_size", battlefield);
                // Native knowledge (schema /4): hidden cards this seat may see
                // beyond its own hand: cards it looked at, every revealed card,
                // and each library whose top card is played revealed.
                int lookedAt = 0;
                for (mage.cards.Cards cards : game.getState().getLookedAt(player.getId()).values()) {
                    lookedAt += cards.size();
                }
                JsonObject knowledge = new JsonObject();
                knowledge.addProperty("visible_hidden_cards", lookedAt + revealed + topRevealed);
                entry.add("knowledge", knowledge);
                // Commander damage this seat has taken (CR 903.10a), from each
                // commander's own damage watcher. Reported only when every
                // commander has its watcher: a missing watcher is no measurement,
                // and an absent readback is unsupported, never a measured 0.
                int commanderDamage = 0;
                boolean commanderDamageMeasured = true;
                for (Player owner : managed.players) {
                    for (UUID commanderId : game.getCommandersIds(
                            owner, CommanderCardType.COMMANDER_OR_OATHBREAKER, false)) {
                        mage.watchers.common.CommanderInfoWatcher damage = game.getState()
                                .getWatcher(mage.watchers.common.CommanderInfoWatcher.class, commanderId);
                        if (damage != null) {
                            commanderDamage += damage.getDamageToPlayer().getOrDefault(player.getId(), 0);
                        } else {
                            commanderDamageMeasured = false;
                        }
                    }
                }
                if (commanderDamageMeasured) {
                    entry.addProperty("commander_damage_taken", commanderDamage);
                }
                // The engine's own LIBRARY_SHUFFLED events for this seat's
                // library so far; absent when the game has no shuffle watcher.
                XmageLibraryShuffleWatcher shuffled =
                        game.getState().getWatcher(XmageLibraryShuffleWatcher.class);
                if (shuffled != null) {
                    entry.addProperty("library_shuffles", shuffled.shuffles(player.getId()));
                }
                mage.watchers.common.CommanderPlaysCountWatcher watcher = game.getState()
                        .getWatcher(mage.watchers.common.CommanderPlaysCountWatcher.class);
                JsonArray commanders = new JsonArray();
                for (UUID commanderId : game.getCommandersIds(
                        player, CommanderCardType.COMMANDER_OR_OATHBREAKER, false)) {
                    mage.cards.Card card = game.getCard(commanderId);
                    if (card == null) {
                        continue;
                    }
                    JsonObject commander = new JsonObject();
                    commander.addProperty("card_identity", card.getName());
                    commander.add("owner", seatName(managed, card.getOwnerId()));
                    commander.addProperty("zone",
                            String.valueOf(game.getState().getZone(commanderId)).toLowerCase());
                    // Native object attributes (schema /3), read from the engine:
                    // the controller of the commander's command object or of its
                    // permanent (null when it is neither, CR 108.4a); counters and
                    // face-down status of the card; tapped state and attachments
                    // exist only for a permanent (CR 110.5, 301.5c), so a card
                    // with no permanent is untapped and has none attached.
                    Permanent permanent = game.getPermanent(commanderId);
                    UUID controllerId = null;
                    if (permanent != null) {
                        controllerId = permanent.getControllerId();
                    } else {
                        for (mage.game.command.CommandObject object : game.getState().getCommand()) {
                            if (object instanceof mage.game.command.Commander
                                    && commanderId.equals(object.getSourceId())) {
                                controllerId = object.getControllerId();
                            }
                        }
                    }
                    commander.add("controller", controllerId == null
                            ? JsonNull.INSTANCE : seatName(managed, controllerId));
                    JsonObject counters = new JsonObject();
                    for (mage.counters.Counter counter : (permanent != null
                            ? permanent.getCounters(game) : card.getCounters(game)).values()) {
                        if (counter.getCount() > 0) {
                            // The engine's own counter name, lower-cased as the
                            // records and the Forge bridge name it ("+1/+1", "charge").
                            counters.addProperty(counter.getName().toLowerCase(java.util.Locale.ROOT),
                                    counter.getCount());
                        }
                    }
                    commander.add("counters", counters);
                    commander.addProperty("face_down",
                            permanent != null ? permanent.isFaceDown(game) : card.isFaceDown(game));
                    commander.addProperty("tapped", permanent != null && permanent.isTapped());
                    commander.addProperty("attachments",
                            permanent == null ? 0 : permanent.getAttachments().size());
                    if (watcher == null) {
                        commander.add("prior_command_zone_cast_count", JsonNull.INSTANCE);
                    } else {
                        commander.addProperty("prior_command_zone_cast_count",
                                watcher.getPlaysCount(commanderId));
                    }
                    commanders.add(commander);
                }
                entry.add("commanders", commanders);
                players.add(entry);
            }
            root.add("players", players);
            // No seed value: Rules seed control is acknowledged on game creation.
            return root;
        }
    }

    /**
     * HMAC under the launch's orchestration key over a seat's zone content as a
     * name multiset: the schema, the zone label, the seat, then one
     * {@code name<TAB>count} token per distinct name in {@link String} order.
     * The Lab, which generated the key, computes the same digest from the
     * record's requested deck and compares the two.
     */
    static String constructedZoneDigest(String seatId, String zone, Collection<? extends mage.cards.Card> cards) {
        java.util.TreeMap<String, Integer> counts = new java.util.TreeMap<>();
        for (mage.cards.Card card : cards) {
            counts.merge(card.getName(), 1, Integer::sum);
        }
        List<String> tokens = new ArrayList<>();
        tokens.add(CONSTRUCTED_STATE_SCHEMA);
        tokens.add(zone);
        tokens.add(seatId);
        counts.forEach((name, count) -> tokens.add(name + "\t" + count));
        return XmageRulesRngResultTape.digest(tokens);
    }

    private static JsonElement seatName(ManagedGame managed, UUID playerId) {
        if (playerId == null) {
            return JsonNull.INSTANCE;
        }
        for (int seat = 0; seat < managed.players.size(); seat++) {
            if (playerId.equals(managed.players.get(seat).getId())) {
                return new com.google.gson.JsonPrimitive("P" + (seat + 1));
            }
        }
        return new com.google.gson.JsonPrimitive("UNKNOWN_SEAT");
    }

    private ManagedGame requireManagedGame(String gameHandle) {
        String validatedHandle = requireText(gameHandle, "game_handle");
        ManagedGame managed = gamesByHandle.get(validatedHandle);
        if (managed == null) {
            throw new GameException("UNKNOWN_GAME_HANDLE: " + validatedHandle);
        }
        return managed;
    }

    private static String stateHash(ManagedGame managed) {
        // This full internal state is hashed inside the JVM for audit transition
        // identity only. It is never emitted as a principal observation.
        return XmageAuditEventLog.stateHash(buildState(managed));
    }

    private static ObserverResolution resolveObserver(
            ManagedGame managed,
            String observerPlayerId
    ) {
        String requested = requireText(observerPlayerId, "observer_player_id");

        if (requested.length() > 1 && requested.charAt(0) == 'p') {
            try {
                int oneBasedSeat = Integer.parseInt(requested.substring(1));
                int seat = oneBasedSeat - 1;
                if (seat >= 0 && seat < managed.players.size()) {
                    return new ObserverResolution(requested, managed.players.get(seat), seat);
                }
            } catch (NumberFormatException ignored) {
                // Fall through to exact live-principal resolution below.
            }
        }

        for (int seat = 0; seat < managed.players.size(); seat++) {
            Player player = managed.players.get(seat);
            if (requested.equals(player.getId().toString())) {
                return new ObserverResolution(requested, player, seat);
            }
        }

        throw new GameException("UNKNOWN_OBSERVER_PLAYER_ID: " + requested);
    }

    /**
     * Protocol-2 compatibility state derived from the same actor-scoped
     * redactor used by the full-game lane.
     *
     * <p>This method is a schema adapter only. Hidden-information entitlement
     * remains exclusively in {@link XmageFullGameStateRedactor#actorView}; this
     * adapter never infers visibility from card names, ownership heuristics or
     * caller wishes. Hidden zones are represented by count-preserving
     * {@code <hidden>} placeholders so public counts remain observable without
     * disclosing identity or library order.</p>
     */
    private static JsonObject buildPrincipalState(ManagedGame managed, Player actor) {
        Game game = managed.game;
        JsonObject view = XmageFullGameStateRedactor.actorView(game, actor);

        JsonObject state = new JsonObject();
        state.addProperty("game_id", managed.gameId);
        state.add("seed", JsonNull.INSTANCE);
        state.add("rng_counter", JsonNull.INSTANCE);
        state.addProperty("status", game.hasEnded() ? "completed" : "in_progress");
        state.addProperty("turn_number", view.get("turn_number").getAsInt());
        state.add("active_player_id", view.get("active_player_id").deepCopy());
        state.add("priority_player_id", view.get("priority_player_id").deepCopy());
        state.add("phase", view.get("phase").deepCopy());
        state.add("step", view.get("step").deepCopy());

        JsonArray players = new JsonArray();
        JsonArray projectedPlayers = view.getAsJsonArray("players");
        for (int seat = 0; seat < projectedPlayers.size(); seat++) {
            JsonObject projected = projectedPlayers.get(seat).getAsJsonObject();
            JsonObject player = new JsonObject();
            player.addProperty("player_id", projected.get("player_id").getAsString());
            player.addProperty("seat", projected.get("seat").getAsInt());
            player.addProperty("life", projected.get("life").getAsInt());
            player.addProperty("poison_counters", projected.get("poison_counters").getAsInt());
            player.add("commander_damage_received", new JsonObject());
            player.add("commander_cast_count", new JsonObject());

            if (projected.has("mana_pool")) {
                player.add("mana_pool", projected.getAsJsonObject("mana_pool").deepCopy());
            } else {
                player.add("mana_pool", new JsonObject());
            }

            JsonObject zones = new JsonObject();
            JsonArray grantedLibrary = projected.getAsJsonArray("granted_library");
            zones.add(
                    "library",
                    grantedLibrary.size() == 0
                            ? hiddenArray(projected.get("library_count").getAsInt())
                            : projectedIds(grantedLibrary)
            );
            zones.add(
                    "hand",
                    projected.has("hand")
                            ? projectedIds(projected.getAsJsonArray("hand"))
                            : hiddenArray(projected.get("hand_count").getAsInt())
            );
            zones.add("battlefield", projectedIds(projected.getAsJsonArray("battlefield")));
            zones.add("graveyard", projectedIds(projected.getAsJsonArray("graveyard")));
            zones.add(
                    "exile",
                    hiddenArray(projected.get("exile_count").getAsInt())
            );
            zones.add("command", projectedIds(projected.getAsJsonArray("command")));
            player.add("zones", zones);

            if (projected.has("land_plays_remaining")) {
                player.addProperty(
                        "land_plays_remaining",
                        projected.get("land_plays_remaining").getAsInt()
                );
            } else {
                Player subject = managed.players.get(seat);
                player.addProperty(
                        "land_plays_remaining",
                        Math.max(0, subject.getLandsPerTurn() - subject.getLandsPlayed())
                );
            }
            player.addProperty("has_lost", projected.get("has_lost").getAsBoolean());
            players.add(player);
        }
        state.add("players", players);

        state.add("stack", projectedIds(view.getAsJsonArray("stack")));
        state.add("legal_actions", new JsonArray());

        JsonArray winnerIds = new JsonArray();
        for (JsonElement element : projectedPlayers) {
            JsonObject projected = element.getAsJsonObject();
            if (projected.get("has_won").getAsBoolean()) {
                winnerIds.add(projected.get("player_id").getAsString());
            }
        }
        state.add("winner_ids", winnerIds);
        state.addProperty("event_sequence", managed.eventLog.latestOffset());
        return state;
    }

    private static JsonArray projectedIds(JsonArray projectedItems) {
        JsonArray result = new JsonArray();
        for (JsonElement element : projectedItems) {
            if (element.isJsonObject()) {
                JsonObject item = element.getAsJsonObject();
                if (item.has("object_id") && !item.get("object_id").isJsonNull()) {
                    result.add(item.get("object_id").getAsString());
                }
            } else if (element.isJsonPrimitive() && element.getAsJsonPrimitive().isString()) {
                result.add(element.getAsString());
            }
        }
        return result;
    }

    private static JsonArray hiddenArray(int count) {
        JsonArray result = new JsonArray();
        for (int index = 0; index < count; index++) {
            result.add("<hidden>");
        }
        return result;
    }

    /**
     * Full internal state used only as input to audit state hashing. Never emit
     * this object as an observation: it intentionally contains all engine ids
     * and hidden zone object ids so transition hashes change when hidden engine
     * state changes.
     */
    private static JsonObject buildState(ManagedGame managed) {
        Game game = managed.game;
        TurnPhase turnPhase = game.getTurnPhaseType();
        if (turnPhase == null) {
            throw new GameException("GAME_STATE_UNAVAILABLE: XMage turn phase is unavailable");
        }

        JsonObject state = new JsonObject();
        state.addProperty("game_id", managed.gameId);
        state.add("seed", JsonNull.INSTANCE);
        state.add("rng_counter", JsonNull.INSTANCE);
        state.addProperty("status", game.hasEnded() ? "completed" : "in_progress");
        state.addProperty("turn_number", game.getState().getTurnNum());
        addNullableUuid(state, "active_player_id", game.getActivePlayerId());
        addNullableUuid(state, "priority_player_id", game.getPriorityPlayerId());
        state.addProperty("phase", turnPhaseValue(turnPhase));

        PhaseStep turnStep = game.getTurnStepType();
        if (turnStep == null) {
            state.add("step", JsonNull.INSTANCE);
        } else {
            state.addProperty("step", turnStep.name().toLowerCase());
        }

        JsonArray players = new JsonArray();
        for (int seat = 0; seat < managed.players.size(); seat++) {
            players.add(playerState(game, managed.players.get(seat), seat));
        }
        state.add("players", players);

        JsonArray stack = new JsonArray();
        for (StackObject stackObject : game.getStack()) {
            stack.add(stackObject.getId().toString());
        }
        state.add("stack", stack);

        /*
         * Endpoint completeness remains false through bounded B4-C because
         * combat and choice classes are not yet globally enumerated.
         */
        state.add("legal_actions", new JsonArray());

        JsonArray winnerIds = new JsonArray();
        for (Player player : managed.players) {
            if (player.hasWon()) {
                winnerIds.add(player.getId().toString());
            }
        }
        state.add("winner_ids", winnerIds);
        state.addProperty("event_sequence", managed.eventLog.latestOffset());
        return state;
    }

    private static JsonObject playerState(Game game, Player player, int seat) {
        JsonObject state = new JsonObject();
        // Actor-safe: never disclose another seat's real principal id.
        state.addProperty("player_id", ActorSafeIdentity.forSeat(game, player, player));
        state.addProperty("seat", seat);
        state.addProperty("life", player.getLife());
        state.addProperty("poison_counters", player.getCountersCount(CounterType.POISON));

        state.add("commander_damage_received", new JsonObject());
        state.add("commander_cast_count", new JsonObject());

        JsonObject manaPool = new JsonObject();
        manaPool.addProperty("white", player.getManaPool().get(ManaType.WHITE));
        manaPool.addProperty("blue", player.getManaPool().get(ManaType.BLUE));
        manaPool.addProperty("black", player.getManaPool().get(ManaType.BLACK));
        manaPool.addProperty("red", player.getManaPool().get(ManaType.RED));
        manaPool.addProperty("green", player.getManaPool().get(ManaType.GREEN));
        manaPool.addProperty("colorless", player.getManaPool().get(ManaType.COLORLESS));
        state.add("mana_pool", manaPool);

        JsonObject zones = new JsonObject();
        zones.add("library", uuidArray(player.getLibrary().getCardList()));
        zones.add("hand", itemArray(player.getHand().getCards(game)));

        List<Permanent> battlefield = game.getBattlefield()
                .getAllPermanents()
                .stream()
                .filter(permanent -> player.getId().equals(permanent.getControllerId()))
                .toList();
        zones.add("battlefield", itemArray(battlefield));
        zones.add("graveyard", itemArray(player.getGraveyard().getCards(game)));
        zones.add("exile", itemArray(game.getExile().getCardsOwned(game, player.getId())));
        zones.add(
                "command",
                itemArray(
                        game.getCommanderCardsFromCommandZone(
                                player,
                                CommanderCardType.COMMANDER_OR_OATHBREAKER
                        )
                )
        );
        state.add("zones", zones);

        state.addProperty(
                "land_plays_remaining",
                Math.max(0, player.getLandsPerTurn() - player.getLandsPlayed())
        );
        state.addProperty("has_lost", player.hasLost());
        return state;
    }

    private static JsonArray itemArray(Collection<? extends MageItem> items) {
        JsonArray result = new JsonArray();
        for (MageItem item : items) {
            result.add(item.getId().toString());
        }
        return result;
    }

    private static JsonArray uuidArray(Collection<UUID> ids) {
        JsonArray result = new JsonArray();
        for (UUID id : ids) {
            result.add(id.toString());
        }
        return result;
    }

    private static void addNullableUuid(JsonObject object, String property, UUID value) {
        if (value == null) {
            object.add(property, JsonNull.INSTANCE);
        } else {
            object.addProperty(property, value.toString());
        }
    }

    private static String turnPhaseValue(TurnPhase turnPhase) {
        return switch (turnPhase) {
            case BEGINNING -> "beginning";
            case PRECOMBAT_MAIN -> "precombat_main";
            case COMBAT -> "combat";
            case POSTCOMBAT_MAIN -> "postcombat_main";
            case END -> "ending";
        };
    }

    private static String requireText(String value, String fieldName) {
        if (value == null || value.isBlank()) {
            throw new GameException("INVALID_FIELD: " + fieldName + " must be nonblank");
        }
        return value.trim();
    }
}

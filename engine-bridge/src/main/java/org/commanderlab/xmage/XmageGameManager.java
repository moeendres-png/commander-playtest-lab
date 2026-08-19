package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.MageItem;
import mage.cards.decks.Deck;
import mage.constants.CommanderCardType;
import mage.constants.ManaType;
import mage.constants.MultiplayerAttackOption;
import mage.constants.PhaseStep;
import mage.constants.RangeOfInfluence;
import mage.constants.TurnPhase;
import mage.counters.CounterType;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.GameOptions;
import mage.game.mulligan.MulliganType;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;

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
            boolean externalControl
    ) {
    }

    record StartResult(
            String gameHandle,
            String gameId,
            String engineGameId,
            int playerCount,
            String startingPlayerId,
            int turnNumber,
            boolean paused,
            boolean externalControl
    ) {
    }

    record StateSnapshot(
            String gameId,
            String engineGameId,
            long stateObservationOffset,
            JsonObject state
    ) {
    }

    record LegalActionsSnapshot(
            String gameId,
            String engineGameId,
            long decisionOffset,
            String decisionId,
            String actorId,
            String decisionKind,
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
        private final CommanderFreeForAll game;
        private final List<Player> players;
        private final List<String> deckHandles;
        private final int startingPlayerSeat;
        private final int startingLife;
        private final boolean externalControl;
        private final ExternalDecisionController externalDecisionController;
        private final XmageAuditEventLog eventLog;

        private Lifecycle lifecycle = Lifecycle.CREATED;
        private long stateObservationOffset = 0L;

        private ManagedGame(
                String gameId,
                CommanderFreeForAll game,
                List<Player> players,
                List<String> deckHandles,
                int startingPlayerSeat,
                int startingLife,
                boolean externalControl,
                ExternalDecisionController externalDecisionController
        ) {
            this.gameId = gameId;
            this.game = game;
            this.players = players;
            this.deckHandles = deckHandles;
            this.startingPlayerSeat = startingPlayerSeat;
            this.startingLife = startingLife;
            this.externalControl = externalControl;
            this.externalDecisionController = externalDecisionController;
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
        String validatedGameId = requireText(gameId, "game_id");

        if (requestedDeckHandles == null) {
            throw new GameException("INVALID_GAME: deck_handles must not be null");
        }

        List<String> deckHandles = new ArrayList<>(requestedDeckHandles);

        if (deckHandles.size() < 2 || deckHandles.size() > 5) {
            throw new GameException(
                    "INVALID_PLAYER_COUNT: expected 2 to 5 players; observed "
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
            CommanderFreeForAll game = new CommanderFreeForAll(
                    MultiplayerAttackOption.MULTIPLE,
                    RangeOfInfluence.ALL,
                    MulliganType.GAME_DEFAULT.getMulligan(0),
                    startingLife,
                    7
            );
            game.setNumPlayers(deckHandles.size());

            GameOptions options = new GameOptions();
            options.rollbackTurnsAllowed = false;
            game.setGameOptions(options);

            ExternalDecisionController decisionController = externalControl
                    ? new ExternalDecisionController()
                    : null;

            List<Player> players = new ArrayList<>(decks.size());
            for (int index = 0; index < decks.size(); index++) {
                Deck deck = decks.get(index);
                XmageBridgePlayer player = new XmageBridgePlayer(
                        "Bridge Seat " + (index + 1),
                        RangeOfInfluence.ALL,
                        decisionController
                );

                player.init(game);
                game.loadCards(deck.getCards(), player.getId());
                game.loadCards(deck.getSideboard(), player.getId());
                game.addPlayer(player, deck);
                players.add(player);
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
                    decisionController
            );

            String gameHandle;
            do {
                gameHandle = "xmage-game-" + UUID.randomUUID();
            } while (gamesByHandle.putIfAbsent(gameHandle, managed) != null);

            JsonObject createdPayload = new JsonObject();
            createdPayload.addProperty("player_count", game.getPlayers().size());
            createdPayload.addProperty("starting_player_seat", startingPlayerSeat);
            createdPayload.addProperty("external_control", externalControl);
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
                    externalControl
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

            GameOptions options = managed.game.getOptions();

            if (managed.externalControl) {
                /*
                 * Reach precombat main under an engine-owned stop hook first.
                 * Then clear the hook and resume until the real priority player
                 * publishes a B4-B decision and pauses from priority().
                 */
                options.stopOnTurn = 1;
                options.stopAtStep = PhaseStep.PRECOMBAT_MAIN;
            } else {
                /* Validated B3 bounded handoff. */
                options.stopOnTurn = 1;
                options.stopAtStep = PhaseStep.UPKEEP;
            }

            Player choosingPlayer = managed.players.get(managed.startingPlayerSeat);

            try {
                managed.game.start(choosingPlayer.getId());

                if (managed.externalControl) {
                    if (!managed.game.isPaused()) {
                        throw new GameException(
                                "XMAGE_EXTERNAL_CONTROL_START_FAILED: "
                                        + "precombat-main setup hook was not reached"
                        );
                    }
                    options.stopOnTurn = 0;
                    options.stopAtStep = null;
                    managed.game.resume();
                }
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
                if (!managed.externalControl && player.getHand().size() != 7) {
                    managed.lifecycle = Lifecycle.FAILED;
                    throw new GameException(
                            "XMAGE_GAME_START_FAILED: "
                                    + player.getName()
                                    + " has unexpected opening hand size "
                                    + player.getHand().size()
                    );
                }
            }

            if (managed.externalControl) {
                if (managed.externalDecisionController == null) {
                    managed.lifecycle = Lifecycle.FAILED;
                    throw new GameException(
                            "XMAGE_EXTERNAL_CONTROL_START_FAILED: controller is unavailable"
                    );
                }
                try {
                    ExternalDecisionController.Decision decision =
                            managed.externalDecisionController.requireCurrentDecision(
                                    managed.game.getId().toString()
                            );
                    if (!"priority".equals(decision.decisionKind())) {
                        throw new GameException(
                                "XMAGE_EXTERNAL_CONTROL_START_FAILED: "
                                        + "unexpected decision kind "
                                        + decision.decisionKind()
                        );
                    }
                } catch (IllegalStateException exc) {
                    managed.lifecycle = Lifecycle.FAILED;
                    throw new GameException(
                            "XMAGE_EXTERNAL_CONTROL_START_FAILED: " + exc.getMessage(),
                            exc
                    );
                }
            }

            managed.lifecycle = Lifecycle.STARTED;
            JsonObject startedPayload = new JsonObject();
            startedPayload.addProperty(
                    "starting_player_id",
                    managed.game.getStartingPlayerId().toString()
            );
            startedPayload.addProperty("turn_number", managed.game.getState().getTurnNum());
            startedPayload.addProperty("external_control", managed.externalControl);
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
                    managed.game.getState().getTurnNum(),
                    managed.game.isPaused(),
                    managed.externalControl
            );
        }
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
            if (!managed.game.isPaused()) {
                throw new GameException(
                        "LEGAL_ACTIONS_UNAVAILABLE: game is not paused at an external decision"
                );
            }

            try {
                ExternalDecisionController.Decision decision =
                        managed.externalDecisionController.requireCurrentDecision(
                                managed.game.getId().toString()
                        );
                return new LegalActionsSnapshot(
                        managed.gameId,
                        managed.game.getId().toString(),
                        decision.decisionOffset(),
                        decision.decisionId(),
                        decision.actorId(),
                        decision.decisionKind(),
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

    StateSnapshot snapshotState(String gameHandle) {
        ManagedGame managed = requireManagedGame(gameHandle);
        synchronized (managed) {
            if (managed.lifecycle != Lifecycle.STARTED) {
                throw new GameException("GAME_STATE_UNAVAILABLE: game must be started");
            }
            managed.stateObservationOffset++;
            return new StateSnapshot(
                    managed.gameId,
                    managed.game.getId().toString(),
                    managed.stateObservationOffset,
                    buildState(managed)
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
            if (managed.lifecycle == Lifecycle.STARTED) {
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

    private ManagedGame requireManagedGame(String gameHandle) {
        String validatedHandle = requireText(gameHandle, "game_handle");
        ManagedGame managed = gamesByHandle.get(validatedHandle);
        if (managed == null) {
            throw new GameException("UNKNOWN_GAME_HANDLE: " + validatedHandle);
        }
        return managed;
    }

    private static String stateHash(ManagedGame managed) {
        return XmageAuditEventLog.stateHash(buildState(managed));
    }

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
        state.addProperty("player_id", player.getId().toString());
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

package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import mage.MageItem;
import mage.cards.Card;
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
            int startingPlayerSeat
    ) {
    }

    record StartResult(
            String gameHandle,
            String gameId,
            String engineGameId,
            int playerCount,
            String startingPlayerId,
            int turnNumber,
            boolean paused
    ) {
    }

    record StateSnapshot(
            String gameId,
            String engineGameId,
            long stateObservationOffset,
            JsonObject state
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
        private final int startingPlayerSeat;
        private final int startingLife;

        private Lifecycle lifecycle =
                Lifecycle.CREATED;

        private long stateObservationOffset = 0L;

        private ManagedGame(
                String gameId,
                CommanderFreeForAll game,
                List<Player> players,
                int startingPlayerSeat,
                int startingLife
        ) {
            this.gameId = gameId;
            this.game = game;
            this.players = players;
            this.startingPlayerSeat =
                    startingPlayerSeat;
            this.startingLife =
                    startingLife;
        }
    }

    private final XmageDeckImporter deckImporter;

    private final Map<String, ManagedGame> gamesByHandle =
            new ConcurrentHashMap<>();

    /*
     * XMage Deck contains mutable concrete Card objects.
     * One imported deck handle therefore belongs to at most one game.
     */
    private final Set<String> claimedDeckHandles =
            ConcurrentHashMap.newKeySet();

    XmageGameManager(
            XmageDeckImporter deckImporter
    ) {
        if (deckImporter == null) {
            throw new IllegalArgumentException(
                    "deckImporter must not be null"
            );
        }

        this.deckImporter = deckImporter;
    }

    CreateResult createCommanderGame(
            String gameId,
            List<String> requestedDeckHandles,
            int startingPlayerSeat,
            int startingLife
    ) {
        String validatedGameId =
                requireText(gameId, "game_id");

        if (requestedDeckHandles == null) {
            throw new GameException(
                    "INVALID_GAME: deck_handles must not be null"
            );
        }

        List<String> deckHandles =
                new ArrayList<>(requestedDeckHandles);

        if (deckHandles.size() < 2
                || deckHandles.size() > 5) {
            throw new GameException(
                    "INVALID_PLAYER_COUNT: expected 2 to 5 players; observed "
                            + deckHandles.size()
            );
        }

        if (startingPlayerSeat < 0
                || startingPlayerSeat >= deckHandles.size()) {
            throw new GameException(
                    "INVALID_STARTING_PLAYER_SEAT: "
                            + startingPlayerSeat
            );
        }

        if (startingLife < 1) {
            throw new GameException(
                    "INVALID_STARTING_LIFE: "
                            + startingLife
            );
        }

        Set<String> distinct =
                new HashSet<>();

        for (int index = 0; index < deckHandles.size(); index++) {
            String handle =
                    requireText(
                            deckHandles.get(index),
                            "deck_handles[" + index + "]"
                    );

            deckHandles.set(index, handle);

            if (!distinct.add(handle)) {
                throw new GameException(
                        "DUPLICATE_DECK_HANDLE: "
                                + handle
                );
            }
        }

        /*
         * Resolve all handles before claiming any.
         */
        List<Deck> decks =
                new ArrayList<>(deckHandles.size());

        try {
            for (String handle : deckHandles) {
                decks.add(
                        deckImporter.requireDeck(handle)
                );
            }
        } catch (XmageDeckImporter.ImportException exc) {
            throw new GameException(
                    "DECK_HANDLE_RESOLUTION_FAILED: "
                            + exc.getMessage(),
                    exc
            );
        }

        synchronized (claimedDeckHandles) {
            for (String handle : deckHandles) {
                if (claimedDeckHandles.contains(handle)) {
                    throw new GameException(
                            "DECK_HANDLE_ALREADY_IN_USE: "
                                    + handle
                    );
                }
            }

            claimedDeckHandles.addAll(deckHandles);
        }

        boolean createdSuccessfully = false;

        try {
            CommanderFreeForAll game =
                    new CommanderFreeForAll(
                            MultiplayerAttackOption.MULTIPLE,
                            RangeOfInfluence.ALL,
                            MulliganType.GAME_DEFAULT
                                    .getMulligan(0),
                            startingLife,
                            7
                    );

            game.setNumPlayers(
                    deckHandles.size()
            );

            GameOptions options =
                    new GameOptions();

            options.rollbackTurnsAllowed = false;

            game.setGameOptions(options);

            List<Player> players =
                    new ArrayList<>(decks.size());

            for (int index = 0; index < decks.size(); index++) {
                Deck deck =
                        decks.get(index);

                XmageBridgePlayer player =
                        new XmageBridgePlayer(
                                "Bridge Seat "
                                        + (index + 1),
                                RangeOfInfluence.ALL
                        );

                /*
                 * XMage's own server-side tests register all concrete cards
                 * before attaching the Deck to the Player.
                 */
                player.init(game);

                game.loadCards(
                        deck.getCards(),
                        player.getId()
                );

                game.loadCards(
                        deck.getSideboard(),
                        player.getId()
                );

                game.addPlayer(
                        player,
                        deck
                );

                players.add(player);
            }

            if (game.getPlayers().size()
                    != deckHandles.size()) {
                throw new GameException(
                        "XMAGE_PLAYER_SETUP_FAILED: expected "
                                + deckHandles.size()
                                + " players but observed "
                                + game.getPlayers().size()
                );
            }

            String gameHandle;

            ManagedGame managed =
                    new ManagedGame(
                            validatedGameId,
                            game,
                            List.copyOf(players),
                            startingPlayerSeat,
                            startingLife
                    );

            do {
                gameHandle =
                        "xmage-game-"
                                + UUID.randomUUID();
            } while (
                    gamesByHandle.putIfAbsent(
                            gameHandle,
                            managed
                    ) != null
            );

            createdSuccessfully = true;

            return new CreateResult(
                    gameHandle,
                    validatedGameId,
                    game.getId().toString(),
                    game.getPlayers().size(),
                    startingPlayerSeat
            );

        } finally {
            if (!createdSuccessfully) {
                synchronized (claimedDeckHandles) {
                    claimedDeckHandles.removeAll(
                            deckHandles
                    );
                }
            }
        }
    }

    StartResult startGame(
            String gameHandle
    ) {
        ManagedGame managed =
                requireManagedGame(gameHandle);

        synchronized (managed) {
            if (managed.lifecycle
                    == Lifecycle.STARTED) {
                throw new GameException(
                        "GAME_ALREADY_STARTED: "
                                + requireText(gameHandle, "game_handle")
                );
            }

            if (managed.lifecycle
                    == Lifecycle.FAILED) {
                throw new GameException(
                        "GAME_START_PREVIOUSLY_FAILED: "
                                + requireText(gameHandle, "game_handle")
                );
            }

            GameOptions options =
                    managed.game.getOptions();

            /*
             * Do not use stopOnTurn=1 / UNTAP here.
             *
             * GameImpl handles that special case before Turn.play(), without
             * pausing. Instead use XMage's normal Phase stop hook at UPKEEP.
             * Phase.checkStopOnStepOption(...) calls game.pause(), making the
             * returned state explicitly resumable through Game.resume().
             */
            options.stopOnTurn = 1;
            options.stopAtStep = PhaseStep.UPKEEP;

            Player choosingPlayer =
                    managed.players.get(
                            managed.startingPlayerSeat
                    );

            try {
                managed.game.start(
                        choosingPlayer.getId()
                );
            } catch (RuntimeException | Error exc) {
                managed.lifecycle =
                        Lifecycle.FAILED;

                throw new GameException(
                        "XMAGE_GAME_START_FAILED: "
                                + exc.getMessage(),
                        exc
                );
            }

            if (managed.game.getTotalErrorsCount()
                    != 0) {
                managed.lifecycle =
                        Lifecycle.FAILED;

                throw new GameException(
                        "XMAGE_GAME_START_FAILED: "
                                + "XMage reported "
                                + managed.game.getTotalErrorsCount()
                                + " internal engine error(s)"
                );
            }
            if (managed.game.getStartingPlayerId()
                    == null) {
                managed.lifecycle =
                        Lifecycle.FAILED;

                throw new GameException(
                        "XMAGE_GAME_START_FAILED: "
                                + "starting player was not established"
                );
            }

            if (!managed.game.isPaused()) {
                managed.lifecycle =
                        Lifecycle.FAILED;

                throw new GameException(
                        "XMAGE_GAME_START_FAILED: "
                                + "game did not pause at the B3 handoff boundary"
                );
            }

            if (managed.game.getState()
                    .getTurnNum() != 1) {
                managed.lifecycle =
                        Lifecycle.FAILED;

                throw new GameException(
                        "XMAGE_GAME_START_FAILED: "
                                + "unexpected turn number "
                                + managed.game.getState()
                                        .getTurnNum()
                );
            }

            for (Player player
                    : managed.game.getPlayers().values()) {

                if (player.getLife()
                        != managed.startingLife) {
                    managed.lifecycle =
                            Lifecycle.FAILED;

                    throw new GameException(
                            "XMAGE_GAME_START_FAILED: "
                                    + player.getName()
                                    + " has unexpected life "
                                    + player.getLife()
                    );
                }

                if (player.getHand().size()
                        != 7) {
                    managed.lifecycle =
                            Lifecycle.FAILED;

                    throw new GameException(
                            "XMAGE_GAME_START_FAILED: "
                                    + player.getName()
                                    + " has unexpected opening hand size "
                                    + player.getHand().size()
                    );
                }
            }

            managed.lifecycle =
                    Lifecycle.STARTED;

            return new StartResult(
                    requireText(gameHandle, "game_handle"),
                    managed.gameId,
                    managed.game.getId()
                            .toString(),
                    managed.game.getPlayers()
                            .size(),
                    managed.game.getStartingPlayerId()
                            .toString(),
                    managed.game.getState()
                            .getTurnNum(),
                    managed.game.isPaused()
            );
        }
    }

    StateSnapshot snapshotState(
            String gameHandle
    ) {
        ManagedGame managed =
                requireManagedGame(gameHandle);

        synchronized (managed) {
            if (managed.lifecycle != Lifecycle.STARTED) {
                throw new GameException(
                        "GAME_STATE_UNAVAILABLE: game must be started"
                );
            }

            Game game = managed.game;
            TurnPhase turnPhase = game.getTurnPhaseType();

            if (turnPhase == null) {
                throw new GameException(
                        "GAME_STATE_UNAVAILABLE: XMage turn phase is unavailable"
                );
            }

            managed.stateObservationOffset++;

            JsonObject state = new JsonObject();
            state.addProperty("game_id", managed.gameId);
            state.add("seed", JsonNull.INSTANCE);
            state.add("rng_counter", JsonNull.INSTANCE);
            state.addProperty(
                    "status",
                    game.hasEnded()
                            ? "completed"
                            : "in_progress"
            );
            state.addProperty(
                    "turn_number",
                    game.getState().getTurnNum()
            );
            addNullableUuid(
                    state,
                    "active_player_id",
                    game.getActivePlayerId()
            );
            addNullableUuid(
                    state,
                    "priority_player_id",
                    game.getPriorityPlayerId()
            );
            state.addProperty(
                    "phase",
                    turnPhaseValue(turnPhase)
            );

            PhaseStep turnStep = game.getTurnStepType();
            if (turnStep == null) {
                state.add("step", JsonNull.INSTANCE);
            } else {
                state.addProperty(
                        "step",
                        turnStep.name().toLowerCase()
                );
            }

            JsonArray players = new JsonArray();
            for (int seat = 0; seat < managed.players.size(); seat++) {
                players.add(
                        playerState(
                                game,
                                managed.players.get(seat),
                                seat
                        )
                );
            }
            state.add("players", players);

            JsonArray stack = new JsonArray();
            for (StackObject stackObject : game.getStack()) {
                stack.add(stackObject.getId().toString());
            }
            state.add("stack", stack);

            /*
             * Legal-action completeness belongs to B4-B. An empty list here
             * is a schema placeholder only and is paired with an explicit
             * false completeness marker in the surrounding response.
             */
            state.add("legal_actions", new JsonArray());

            JsonArray winnerIds = new JsonArray();
            for (Player player : managed.players) {
                if (player.hasWon()) {
                    winnerIds.add(player.getId().toString());
                }
            }
            state.add("winner_ids", winnerIds);

            /*
             * B4-A has no exported event stream yet. Keep this at zero rather
             * than inventing event identity; state_observation_offset below is
             * deliberately a separate observation sequence.
             */
            state.addProperty("event_sequence", 0);

            return new StateSnapshot(
                    managed.gameId,
                    game.getId().toString(),
                    managed.stateObservationOffset,
                    state
            );
        }
    }

    Game requireGame(
            String gameHandle
    ) {
        return requireManagedGame(gameHandle).game;
    }

    int storedGameCount() {
        return gamesByHandle.size();
    }

    private ManagedGame requireManagedGame(
            String gameHandle
    ) {
        String validatedHandle =
                requireText(
                        gameHandle,
                        "game_handle"
                );

        ManagedGame managed =
                gamesByHandle.get(
                        validatedHandle
                );

        if (managed == null) {
            throw new GameException(
                    "UNKNOWN_GAME_HANDLE: "
                            + validatedHandle
            );
        }

        return managed;
    }

    private static JsonObject playerState(
            Game game,
            Player player,
            int seat
    ) {
        JsonObject state = new JsonObject();
        state.addProperty(
                "player_id",
                player.getId().toString()
        );
        state.addProperty("seat", seat);
        state.addProperty("life", player.getLife());
        state.addProperty(
                "poison_counters",
                player.getCountersCount(CounterType.POISON)
        );

        /*
         * Commander-damage and commander-tax visibility are not promoted in
         * B4-A. Empty maps are truthful at the bounded start-state regression;
         * their capability flags remain false until dedicated evidence exists.
         */
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
        zones.add(
                "library",
                uuidArray(player.getLibrary().getCardList())
        );
        zones.add(
                "hand",
                itemArray(player.getHand().getCards(game))
        );

        List<Permanent> battlefield =
                game.getBattlefield()
                        .getAllPermanents()
                        .stream()
                        .filter(
                                permanent -> player.getId()
                                        .equals(permanent.getControllerId())
                        )
                        .toList();
        zones.add(
                "battlefield",
                itemArray(battlefield)
        );
        zones.add(
                "graveyard",
                itemArray(player.getGraveyard().getCards(game))
        );
        zones.add(
                "exile",
                itemArray(
                        game.getExile()
                                .getCardsOwned(game, player.getId())
                )
        );
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
                Math.max(
                        0,
                        player.getLandsPerTurn()
                                - player.getLandsPlayed()
                )
        );
        state.addProperty("has_lost", player.hasLost());

        return state;
    }

    private static JsonArray itemArray(
            Collection<? extends MageItem> items
    ) {
        JsonArray result = new JsonArray();
        for (MageItem item : items) {
            result.add(item.getId().toString());
        }
        return result;
    }

    private static JsonArray uuidArray(
            Collection<UUID> ids
    ) {
        JsonArray result = new JsonArray();
        for (UUID id : ids) {
            result.add(id.toString());
        }
        return result;
    }

    private static void addNullableUuid(
            JsonObject object,
            String property,
            UUID value
    ) {
        if (value == null) {
            object.add(property, JsonNull.INSTANCE);
        } else {
            object.addProperty(property, value.toString());
        }
    }

    private static String turnPhaseValue(
            TurnPhase turnPhase
    ) {
        return switch (turnPhase) {
            case BEGINNING -> "beginning";
            case PRECOMBAT_MAIN -> "precombat_main";
            case COMBAT -> "combat";
            case POSTCOMBAT_MAIN -> "postcombat_main";
            case END -> "ending";
        };
    }

    private static String requireText(
            String value,
            String fieldName
    ) {
        if (value == null
                || value.isBlank()) {
            throw new GameException(
                    "INVALID_FIELD: "
                            + fieldName
                            + " must be nonblank"
            );
        }

        return value.trim();
    }
}

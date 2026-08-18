package org.commanderlab.xmage;

import mage.cards.decks.Deck;
import mage.constants.MultiplayerAttackOption;
import mage.constants.PhaseStep;
import mage.constants.RangeOfInfluence;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.GameOptions;
import mage.game.mulligan.MulliganType;
import mage.players.Player;

import java.util.ArrayList;
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

        synchronized (managed) {
            if (managed.lifecycle
                    == Lifecycle.STARTED) {
                throw new GameException(
                        "GAME_ALREADY_STARTED: "
                                + validatedHandle
                );
            }

            if (managed.lifecycle
                    == Lifecycle.FAILED) {
                throw new GameException(
                        "GAME_START_PREVIOUSLY_FAILED: "
                                + validatedHandle
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
                    validatedHandle,
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

    Game requireGame(
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

        return managed.game;
    }

    int storedGameCount() {
        return gamesByHandle.size();
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
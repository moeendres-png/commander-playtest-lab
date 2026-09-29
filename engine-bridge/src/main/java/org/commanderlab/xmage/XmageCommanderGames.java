package org.commanderlab.xmage;

import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.game.CommanderDuel;
import mage.game.CommanderFreeForAll;
import mage.game.GameCommanderImpl;
import mage.game.mulligan.Mulligan;

/**
 * Selects the pinned engine's own Commander game type for a table size.
 *
 * <p>The bridge used to build every table as {@link CommanderFreeForAll}. That
 * type declares {@code minPlayers = 3} ({@code CommanderFreeForAllType}) and
 * unconditionally sets {@code startingPlayerSkipsDraw = false}, so a
 * two-player table drew a card for the starting player on turn 1, against
 * CR 103.8a ("In a two-player game, the player who plays first skips the draw
 * step of their first turn"). The engine's two-player Commander type is
 * {@link CommanderDuel} ({@code minPlayers = maxPlayers = 2}); it inherits
 * {@link GameCommanderImpl}'s default {@code startingPlayerSkipsDraw = true},
 * which skips the whole draw step through the engine's own turn modification.
 *
 * <p>Nothing here implements a rule: the choice is only which engine-defined
 * game type owns the table. Both types share every other Commander rule
 * through {@link GameCommanderImpl}; neither overrides anything except
 * {@code init}'s draw-skip flag and the reported match type.</p>
 */
final class XmageCommanderGames {

    static final int STARTING_HAND_SIZE = 7;

    private XmageCommanderGames() {
    }

    static GameCommanderImpl create(int playerCount, Mulligan mulligan, int startingLife) {
        if (playerCount < 2) {
            throw new IllegalArgumentException(
                    "COMMANDER_GAME_INVALID_PLAYER_COUNT: " + playerCount);
        }
        if (playerCount == 2) {
            return new CommanderDuel(
                    MultiplayerAttackOption.MULTIPLE,
                    RangeOfInfluence.ALL,
                    mulligan,
                    startingLife,
                    STARTING_HAND_SIZE
            );
        }
        CommanderFreeForAll game = new CommanderFreeForAll(
                MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL,
                mulligan,
                startingLife,
                STARTING_HAND_SIZE
        );
        game.setNumPlayers(playerCount);
        return game;
    }
}

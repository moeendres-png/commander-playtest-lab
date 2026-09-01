package org.commanderlab.xmage;

import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.game.CommanderFreeForAll;
import mage.game.mulligan.Mulligan;

import java.util.UUID;

/** Qualification-only entry points for an already materialized native game state. */
final class XmageQualificationCommanderGame extends CommanderFreeForAll {

    XmageQualificationCommanderGame(
            MultiplayerAttackOption attackOption,
            RangeOfInfluence range,
            Mulligan mulligan,
            int startLife,
            int startHandSize
    ) {
        super(attackOption, range, mulligan, startLife, startHandSize);
    }

    void initializeForNativeStateLoad(UUID startingPlayerId) {
        setStartingPlayerId(startingPlayerId);
        super.init(startingPlayerId);
    }

    void resumeNativePriority(UUID priorityPlayerId) {
        playPriority(priorityPlayerId, false);
    }
}

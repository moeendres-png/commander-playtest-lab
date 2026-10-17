package org.commanderlab.xmage;

import mage.game.Game;
import mage.game.mulligan.LondonMulligan;

import java.util.UUID;

/**
 * The pinned engine's London mulligan, with the bottom-card choice marked as
 * such (#866).
 *
 * <p>{@link LondonMulligan#mulligan} puts the surplus cards on the bottom of
 * the library by asking the player {@code chooseTarget(Outcome.Discard,
 * TargetCardInHand, null, game)} and only afterwards calling
 * {@code putCardsOnBottomOfLibrary} with the answer. That call therefore
 * arrives without the structured {@code bottom_of_library_selection} context
 * the native {@code putCardsOnBottomOfLibrary} callback path carries, and a
 * pilot cannot tell the London bottom from any other discard-flavoured
 * choice. The marker is set here, around the engine's own call, so the pilot
 * receives it from the engine path itself, never from prompt text
 * (F-RULES-03).</p>
 *
 * <p>Nothing here changes a rule: the engine method runs unmodified between
 * the marker being set and cleared. A game copy inherits the engine's
 * {@code copy()}, which returns the plain {@link LondonMulligan}: the engine's
 * copy constructor is not visible outside its package, and game copies never
 * run the mulligan phase.</p>
 */
final class XmageLondonMulligan extends LondonMulligan {

    private static final ThreadLocal<Boolean> LONDON_BOTTOM =
            ThreadLocal.withInitial(() -> Boolean.FALSE);

    XmageLondonMulligan(int freeMulligans) {
        super(freeMulligans);
    }

    /** True while the engine's London mulligan asks for a bottom card. */
    static boolean londonBottomInProgress() {
        return LONDON_BOTTOM.get();
    }

    @Override
    public void mulligan(Game game, UUID playerId) {
        LONDON_BOTTOM.set(Boolean.TRUE);
        try {
            super.mulligan(game, playerId);
        } finally {
            LONDON_BOTTOM.set(Boolean.FALSE);
        }
    }
}

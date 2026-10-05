package org.commanderlab.xmage;

import mage.constants.WatcherScope;
import mage.game.Game;
import mage.game.events.GameEvent;
import mage.watchers.Watcher;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Counts the engine's own LIBRARY_SHUFFLED events per player for the whole
 * game (Commander-Lab #441 decision (c)).
 *
 * <p>Observation only: library shuffling stays PlayerImpl's (Rules RNG,
 * SHUFFLE_LIBRARY replacement, LIBRARY_SHUFFLED event) and is never
 * overridden. The generic lane's constructed state reads these counts so the
 * Lab can establish that each requested Rules-RNG library channel was used;
 * equal decks and hands look the same shuffled or not.</p>
 */
public final class XmageLibraryShuffleWatcher extends Watcher {

    private final Map<UUID, Integer> shuffles = new HashMap<>();

    public XmageLibraryShuffleWatcher() {
        super(WatcherScope.GAME);
    }

    @Override
    public void watch(GameEvent event, Game game) {
        if (event.getType() == GameEvent.EventType.LIBRARY_SHUFFLED && event.getPlayerId() != null) {
            shuffles.merge(event.getPlayerId(), 1, Integer::sum);
        }
    }

    @Override
    public void reset() {
        // The counts are game totals: the end-of-turn watcher reset keeps them.
        super.reset();
    }

    int shuffles(UUID playerId) {
        return shuffles.getOrDefault(playerId, 0);
    }
}

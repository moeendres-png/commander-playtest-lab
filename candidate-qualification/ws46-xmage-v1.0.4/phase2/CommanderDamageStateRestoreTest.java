package org.mage.test.cards.commander;

import mage.constants.CommanderCardType;
import mage.constants.PhaseStep;
import mage.constants.WatcherScope;
import mage.constants.Zone;
import mage.cards.Card;
import mage.game.Game;
import mage.game.GameState;
import mage.game.events.GameEvent;
import mage.players.Player;
import mage.watchers.Watcher;
import mage.watchers.common.CommanderInfoWatcher;
import org.junit.Assert;
import org.junit.Test;
import org.mage.test.serverside.base.CardTestCommander4PlayersWithAIHelps;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

public class CommanderDamageStateRestoreTest extends CardTestCommander4PlayersWithAIHelps {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    private static UUID commanderId(Game game, Player player, String name) {
        Player currentPlayer = game.getPlayer(player.getId());
        Assert.assertNotNull("Current native player must exist", currentPlayer);
        return game.getCommandersIds(currentPlayer, CommanderCardType.ANY, false)
                .stream()
                .filter(id -> {
                    Card card = game.getCard(id);
                    return card != null && name.equals(card.getName());
                })
                .findFirst()
                .orElseThrow(() -> new AssertionError("Commander not found: " + name));
    }

    private static CommanderInfoWatcher watcher(Game game, UUID commanderId) {
        CommanderInfoWatcher watcher = game.getState().getWatcher(CommanderInfoWatcher.class, commanderId);
        Assert.assertNotNull("CommanderInfoWatcher must be installed for native commander", watcher);
        return watcher;
    }

    private static void expectIllegalArgument(String message, Runnable action) {
        try {
            action.run();
            Assert.fail(message);
        } catch (IllegalArgumentException expected) {
            // expected
        }
    }

    @Test
    public void restoreReplacesNativeDamageStateCopiesAndEmitsNoHistoricalDamageEvents() {
        addCard(Zone.COMMAND, playerA, ROGRAKH, 1);

        runCode("restore commander damage", 1, PhaseStep.PRECOMBAT_MAIN, playerA, (info, player, game) -> {
            UUID id = commanderId(game, player, ROGRAKH);
            CommanderInfoWatcher watcher = watcher(game, id);
            DamageEventProbe probe = new DamageEventProbe();
            game.getState().addWatcher(probe);

            Map<UUID, Integer> restored = new LinkedHashMap<>();
            restored.put(playerB.getId(), 13);
            restored.put(playerC.getId(), 0);
            watcher.restoreDamageStateForGameLoad(restored, game);

            Assert.assertEquals("zero entries are canonicalized away", 1, watcher.getDamageToPlayer().size());
            Assert.assertEquals(Integer.valueOf(13), watcher.getDamageToPlayer().get(playerB.getId()));
            Assert.assertFalse(watcher.getDamageToPlayer().containsKey(playerC.getId()));
            Assert.assertEquals("state restoration must not replay historical damage events", 0, probe.damagedPlayerEvents);

            GameState saved = game.getState().copy();
            CommanderInfoWatcher savedWatcher = saved.getWatcher(CommanderInfoWatcher.class, id);
            Assert.assertNotNull(savedWatcher);
            Assert.assertEquals(Integer.valueOf(13), savedWatcher.getDamageToPlayer().get(playerB.getId()));

            watcher.restoreDamageStateForGameLoad(Collections.singletonMap(playerC.getId(), 7), game);
            Assert.assertFalse("restore must replace rather than merge old state", watcher.getDamageToPlayer().containsKey(playerB.getId()));
            Assert.assertEquals(Integer.valueOf(7), watcher.getDamageToPlayer().get(playerC.getId()));
            Assert.assertEquals(0, probe.damagedPlayerEvents);

            game.getState().restore(saved);
            CommanderInfoWatcher restoredWatcher = watcher(game, id);
            Assert.assertEquals(Integer.valueOf(13), restoredWatcher.getDamageToPlayer().get(playerB.getId()));
            Assert.assertFalse(restoredWatcher.getDamageToPlayer().containsKey(playerC.getId()));
        });

        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();
    }

    @Test
    public void invalidDamageRestoreFailsClosedAndLeavesPriorStateUntouched() {
        addCard(Zone.COMMAND, playerA, ROGRAKH, 1);

        runCode("invalid commander damage restore", 1, PhaseStep.PRECOMBAT_MAIN, playerA, (info, player, game) -> {
            UUID id = commanderId(game, player, ROGRAKH);
            CommanderInfoWatcher watcher = watcher(game, id);
            watcher.restoreDamageStateForGameLoad(Collections.singletonMap(playerB.getId(), 9), game);

            Map<UUID, Integer> unknownPlayer = new LinkedHashMap<>();
            unknownPlayer.put(playerB.getId(), 5);
            unknownPlayer.put(UUID.randomUUID(), 2);
            expectIllegalArgument("unknown live player identity must fail closed", () ->
                    watcher.restoreDamageStateForGameLoad(unknownPlayer, game));
            Assert.assertEquals(Integer.valueOf(9), watcher.getDamageToPlayer().get(playerB.getId()));
            Assert.assertEquals(1, watcher.getDamageToPlayer().size());

            expectIllegalArgument("negative damage must fail closed", () ->
                    watcher.restoreDamageStateForGameLoad(Collections.singletonMap(playerB.getId(), -1), game));
            Assert.assertEquals(Integer.valueOf(9), watcher.getDamageToPlayer().get(playerB.getId()));
            Assert.assertEquals(1, watcher.getDamageToPlayer().size());

            expectIllegalArgument("null state must fail closed", () ->
                    watcher.restoreDamageStateForGameLoad(null, game));
            expectIllegalArgument("null game must fail closed", () ->
                    watcher.restoreDamageStateForGameLoad(Collections.emptyMap(), null));
            Assert.assertEquals(Integer.valueOf(9), watcher.getDamageToPlayer().get(playerB.getId()));
            Assert.assertEquals(1, watcher.getDamageToPlayer().size());
        });

        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();
    }

    private static final class DamageEventProbe extends Watcher {

        private int damagedPlayerEvents;

        DamageEventProbe() {
            super(WatcherScope.GAME);
        }

        @Override
        public void watch(GameEvent event, Game game) {
            if (event.getType() == GameEvent.EventType.DAMAGED_PLAYER) {
                damagedPlayerEvents++;
            }
        }
    }
}

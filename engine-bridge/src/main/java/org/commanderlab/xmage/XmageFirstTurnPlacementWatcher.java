package org.commanderlab.xmage;

import mage.abilities.Ability;
import mage.abilities.common.SimpleStaticAbility;
import mage.abilities.effects.common.InfoEffect;
import mage.cards.Card;
import mage.constants.WatcherScope;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.events.GameEvent;
import mage.players.Player;
import mage.util.CardUtil;
import mage.watchers.Watcher;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Places the restored face-up permanents when the first turn begins.
 *
 * <p>The requested state is a checkpoint, not a history. During the
 * start-of-game procedure the battlefield is empty (CR 103.1-103.5); the
 * earliest point at which any permanent can be on the battlefield is after the
 * mulligans, before the first turn, where opening-hand actions such as a
 * Leyline's put it there (CR 103.6). A permanent held on the battlefield from
 * before game start would instead observe the vehicle's own opening-hand draws
 * and mulligans, a history no legal game can show (a restored Narset limits
 * the opponents' opening hands; a restored Psychosis Crawler triggers on every
 * opening draw).</p>
 *
 * <p>So the cards are loaded before game start (outside the game, their
 * watchers registered) and enter the battlefield at the first turn's
 * {@code BEGIN_TURN} event, which the engine fires before the beginning phase
 * marks the active player's permanents as controlled since the turn began.
 * From there on they observe the arrival exactly as a pre-start permanent did:
 * every untap, upkeep, draw and combat step of every arrival turn.</p>
 *
 * <p>The placement uses the setup primitive's own call
 * ({@code CardUtil.putCardOntoBattlefieldWithEffects} with a setup source, as
 * {@code GameImpl.cheat} does): no enters-the-battlefield event, no summoning
 * sickness, and "enters tapped" replacements apply as they did pre-start.
 * Only cards whose battlefield permanent is the card itself are deferred:
 * placing one registers no new watcher while the engine iterates its watchers.
 * The fields are plain ids, so the engine's state copies carry the watcher,
 * and the engine's post-mulligan watcher reset (base {@code reset()}) leaves
 * them untouched.</p>
 */
final class XmageFirstTurnPlacementWatcher extends Watcher {

    private List<UUID> cardIds;
    private List<UUID> ownerIds;
    private boolean placed;

    // Boxed lists only: Watcher.copy() constructs with null for every
    // non-boolean parameter before copying the fields.
    XmageFirstTurnPlacementWatcher(List<UUID> cardIds, List<UUID> ownerIds) {
        super(WatcherScope.GAME);
        this.cardIds = cardIds == null ? null : new ArrayList<>(cardIds);
        this.ownerIds = ownerIds == null ? null : new ArrayList<>(ownerIds);
    }

    /** True for a card whose battlefield permanent is the card itself (no part or face is chosen). */
    static boolean deferrable(Game game, Card card) {
        return CardUtil.getDefaultCardSideForBattlefield(game, card) == card;
    }

    @Override
    public void watch(GameEvent event, Game game) {
        if (placed || event.getType() != GameEvent.EventType.BEGIN_TURN || game.getTurnNum() != 1) {
            return;
        }
        placed = true;
        for (int index = 0; index < cardIds.size(); index++) {
            Card card = game.getCard(cardIds.get(index));
            Player owner = game.getPlayer(ownerIds.get(index));
            if (card == null || owner == null || game.getState().getZone(card.getId()) != Zone.OUTSIDE) {
                // Left for the checkpoint verification, which fails closed.
                continue;
            }
            Ability placement = new SimpleStaticAbility(Zone.OUTSIDE, new InfoEffect("restoration placement"));
            placement.setControllerId(owner.getId());
            placement.setSourceId(card.getId());
            CardUtil.putCardOntoBattlefieldWithEffects(placement, game, card, owner, false);
        }
    }

    boolean placed() {
        return placed;
    }

    List<UUID> cardIds() {
        return List.copyOf(cardIds);
    }
}

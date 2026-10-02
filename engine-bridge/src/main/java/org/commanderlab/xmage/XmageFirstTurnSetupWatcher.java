package org.commanderlab.xmage;

import mage.abilities.Ability;
import mage.abilities.common.SimpleStaticAbility;
import mage.abilities.effects.ContinuousEffect;
import mage.abilities.effects.common.InfoEffect;
import mage.cards.Card;
import mage.cards.MeldCard;
import mage.constants.WatcherScope;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.events.GameEvent;
import mage.game.permanent.PermanentCard;
import mage.players.Player;
import mage.util.CardUtil;
import mage.watchers.Watcher;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * The restoration's setup when the first turn begins: restored face-up
 * permanents enter and recorded starting life totals are set.
 *
 * <p>The requested state is a checkpoint, not a history. During the
 * start-of-game procedure the battlefield is empty (CR 103.1-103.5); the
 * earliest point at which any permanent can be on the battlefield is after the
 * mulligans, before the first turn, where opening-hand actions such as a
 * Leyline's put it there (CR 103.6a). A permanent held on the battlefield from
 * before game start would instead observe the vehicle's own opening-hand draws
 * and mulligans, a history no legal game can show.</p>
 *
 * <p>So the cards are loaded before game start (outside the game, their
 * watchers registered) and enter the battlefield at the first turn's
 * {@code BEGIN_TURN} event. The engine fires it before the beginning phase marks
 * the active player's permanents as controlled since the turn began, and that
 * engine step alone decides it: every placed permanent enters as a new object
 * (CR 302.6), so the turn-1 active player's are controlled since the turn began
 * and every other player's stay so until that player's own turn begins.</p>
 *
 * <p>A recorded starting life (CR 103.4) is set here too, at the same setup
 * point: after the start-of-game procedure, before anything in the first turn
 * can change a life total. It is set only while the player is still at the
 * table's starting life; a total the engine already changed is never
 * overwritten and is left to the checkpoint comparison.</p>
 *
 * <p>A commander requested on the battlefield is the genuine commander. Game
 * start puts it into the command zone (CR 903.6); it leaves the command zone
 * and enters here, at the same point and in the same way as every other
 * restored permanent, so its control history is the engine's too.</p>
 *
 * <p>Placement mirrors the setup primitive {@code CardUtil.putCardOntoBattlefieldWithEffects}
 * (no enters-the-battlefield event, "enters with counters" and "enters tapped"
 * replacements applied) except that it never removes summoning sickness. The
 * public event tape is muted while it runs: what the placement itself reports
 * (an entering planeswalker's loyalty counters) is setup, exactly as it was when
 * placement preceded the tape. Only cards whose battlefield permanent is the
 * card itself are deferred: placing one registers no new watcher while the
 * engine iterates its watchers. The fields are plain ids and numbers, so the
 * engine's state copies carry the watcher, and the engine's post-mulligan
 * watcher reset (base {@code reset()}) leaves them untouched.</p>
 */
final class XmageFirstTurnSetupWatcher extends Watcher {

    private List<UUID> cardIds;
    private List<UUID> ownerIds;
    private List<UUID> commanderIds;
    private List<UUID> commanderOwnerIds;
    private List<UUID> lifePlayerIds;
    private List<Integer> startingLives;
    private List<UUID> placedIds;
    private boolean applied;

    // Boxed lists only: Watcher.copy() constructs with null for every
    // non-boolean parameter before copying the fields.
    XmageFirstTurnSetupWatcher(
            List<UUID> cardIds,
            List<UUID> ownerIds,
            List<UUID> commanderIds,
            List<UUID> commanderOwnerIds,
            List<UUID> lifePlayerIds,
            List<Integer> startingLives) {
        super(WatcherScope.GAME);
        this.cardIds = cardIds == null ? null : new ArrayList<>(cardIds);
        this.ownerIds = ownerIds == null ? null : new ArrayList<>(ownerIds);
        this.commanderIds = commanderIds == null ? null : new ArrayList<>(commanderIds);
        this.commanderOwnerIds = commanderOwnerIds == null ? null : new ArrayList<>(commanderOwnerIds);
        this.lifePlayerIds = lifePlayerIds == null ? null : new ArrayList<>(lifePlayerIds);
        this.startingLives = startingLives == null ? null : new ArrayList<>(startingLives);
        this.placedIds = new ArrayList<>();
    }

    /** True for a card whose battlefield permanent is the card itself (no part, face or meld). */
    static boolean deferrable(Game game, Card card) {
        return !(card instanceof MeldCard) && CardUtil.getDefaultCardSideForBattlefield(game, card) == card;
    }

    @Override
    public void watch(GameEvent event, Game game) {
        if (applied || event.getType() != GameEvent.EventType.BEGIN_TURN || game.getTurnNum() != 1) {
            return;
        }
        applied = true;
        for (int index = 0; index < lifePlayerIds.size(); index++) {
            Player player = game.getPlayer(lifePlayerIds.get(index));
            if (player != null && player.getLife() == game.getStartingLife()) {
                player.initLife(startingLives.get(index));
            }
        }
        XmagePublicEventWatcher tape = game.getState().getWatcher(XmagePublicEventWatcher.class);
        if (tape != null) {
            tape.mute(true);
        }
        try {
            for (int index = 0; index < cardIds.size(); index++) {
                Card card = game.getCard(cardIds.get(index));
                Player owner = game.getPlayer(ownerIds.get(index));
                if (card == null || owner == null || game.getState().getZone(card.getId()) != Zone.OUTSIDE) {
                    // Left for the checkpoint verification, which fails closed.
                    continue;
                }
                place(game, card, owner);
                placedIds.add(card.getId());
            }
            for (int index = 0; index < commanderIds.size(); index++) {
                Card card = game.getCard(commanderIds.get(index));
                Player owner = game.getPlayer(commanderOwnerIds.get(index));
                if (card == null || owner == null || game.getState().getZone(card.getId()) != Zone.COMMAND
                        || !card.removeFromZone(game, Zone.COMMAND, source(card, owner))) {
                    // Left for the checkpoint verification, which fails closed.
                    continue;
                }
                place(game, card, owner);
                placedIds.add(card.getId());
            }
        } finally {
            if (tape != null) {
                tape.mute(false);
            }
        }
    }

    private static Ability source(Card card, Player owner) {
        Ability source = new SimpleStaticAbility(Zone.OUTSIDE, new InfoEffect("restoration placement"));
        source.setControllerId(owner.getId());
        source.setSourceId(card.getId());
        return source;
    }

    private static void place(Game game, Card card, Player owner) {
        Ability source = source(card, owner);
        card.setZone(Zone.BATTLEFIELD, game);
        card.setOwnerId(owner.getId());
        PermanentCard permanent = new PermanentCard(card, owner.getId(), game);
        game.getPermanentsEntering().put(permanent.getId(), permanent);
        card.applyEnterWithCounters(permanent, source, game);
        permanent.entersBattlefield(source, game, Zone.OUTSIDE, false);
        game.addPermanent(permanent, game.getState().getNextPermanentOrderNumber());
        game.getPermanentsEntering().remove(permanent.getId());
        // As the setup primitive does: initialize the new permanent's own
        // layered static effects (the game state holds copies).
        for (ContinuousEffect effect : game.getState().getContinuousEffects().getLayeredEffects(game)) {
            Optional<Ability> ability = game.getState().getContinuousEffects()
                    .getLayeredEffectAbilities(effect).stream().findFirst();
            if (ability.isPresent() && permanent.getId().equals(ability.get().getSourceId())) {
                effect.init(ability.get(), game, owner.getId());
            }
        }
    }

    boolean applied() {
        return applied;
    }

    List<UUID> placedIds() {
        return List.copyOf(placedIds);
    }
}
